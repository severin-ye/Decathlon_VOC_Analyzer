import hashlib
import re
from collections import defaultdict

from decathlon_voc_analyzer.schemas.analysis import RetrievedEvidence, RetrievalQuestion, RetrievalRecord
from decathlon_voc_analyzer.schemas.dataset import ProductEvidencePackage
from decathlon_voc_analyzer.runtime_progress import get_workflow_progress
from decathlon_voc_analyzer.stage3_retrieval.index_service import IndexService
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService


TOKEN_RE = re.compile(r"[\w\-\u4e00-\u9fff가-힣]+", re.UNICODE)


class RetrievalService:
    _PROGRESS_UNITS_PER_QUESTION = 4

    def __init__(self) -> None:
        self.index_service = IndexService()
        self.reranker_service = RerankerService()

    def retrieve_for_package(
        self,
        package: ProductEvidencePackage,
        questions: list[RetrievalQuestion],
        top_k_per_route: int = 2,
        use_llm: bool = True,
    ) -> list[RetrievalRecord]:
        progress = get_workflow_progress()
        total_questions = len(questions)
        progress.start_count_step(
            "analyze",
            "retrieve",
            total=total_questions * self._PROGRESS_UNITS_PER_QUESTION,
            detail=f"准备检索 {total_questions} 个问题",
        )
        records: list[RetrievalRecord] = []
        for index, question in enumerate(questions, start=1):
            records.append(
                self._retrieve_for_question(
                    package=package,
                    question=question,
                    top_k_per_route=top_k_per_route,
                    use_llm=use_llm,
                    question_index=index,
                    total_questions=total_questions,
                )
            )
        progress.complete_step("analyze", "retrieve")
        return records

    def _retrieve_for_question(
        self,
        package: ProductEvidencePackage,
        question: RetrievalQuestion,
        top_k_per_route: int,
        use_llm: bool,
        question_index: int | None = None,
        total_questions: int | None = None,
    ) -> RetrievalRecord:
        progress = get_workflow_progress()

        def advance(detail: str) -> None:
            if question_index is None or total_questions is None:
                return
            progress.advance_step(
                "analyze",
                "retrieve",
                detail=f"[{question_index}/{total_questions}] {detail} · {question.question_id}",
            )

        query = question.question
        indexed_hits = self.index_service.search(
            product_id=package.product_id,
            category_slug=package.category_slug,
            query=query,
            routes=question.expected_evidence_routes,
            top_k_per_route=max(top_k_per_route * 6, 6),
            use_llm=use_llm,
        )
        indexed_hits = self._build_language_balanced_candidate_pool(
            indexed_hits=indexed_hits,
            expected_routes=question.expected_evidence_routes,
            top_k_per_route=top_k_per_route,
        )
        advance(f"召回候选 {len(indexed_hits)} 条")
        embedding_scores = {
            hit.evidence_id: self._extract_score(hit)
            for hit in indexed_hits
        }
        reranked_hits = self.reranker_service.rerank(
            query=query,
            candidates=indexed_hits,
            use_llm=use_llm,
            progress_callback=advance,
        )
        selected_hits = self._select_hits_with_route_coverage(
            reranked_hits=reranked_hits,
            expected_routes=question.expected_evidence_routes,
            top_k_per_route=top_k_per_route,
        )
        retrieved = [
            self._to_retrieved_evidence(hit, embedding_scores.get(hit.evidence_id, 0.0))
            for hit in selected_hits
        ]
        advance(f"汇总证据 {len(retrieved)} 条")

        return RetrievalRecord(
            retrieval_id=self._make_retrieval_id(question.source_review_id, question.source_aspect, query),
            product_id=package.product_id,
            query=query,
            source_review_id=question.source_review_id,
            source_aspect=question.source_aspect,
            source_question_id=question.question_id,
            source_question=question.question,
            source_evidence_span=question.rationale,
            expected_evidence_routes=list(question.expected_evidence_routes),
            retrieved=retrieved,
        )

    def _select_hits_with_route_coverage(
        self,
        reranked_hits: list,
        expected_routes: list[str],
        top_k_per_route: int,
    ) -> list:
        if not reranked_hits:
            return []

        normalized_routes = list(dict.fromkeys(route for route in expected_routes if route))
        if not normalized_routes:
            normalized_routes = list(dict.fromkeys(getattr(hit, "route", None) for hit in reranked_hits if getattr(hit, "route", None)))
        target_count = max(1, len(normalized_routes)) * top_k_per_route
        selected: list = []
        selected_ids: set[str] = set()

        for route in normalized_routes:
            route_hits = [hit for hit in reranked_hits if getattr(hit, "route", None) == route and hit.evidence_id not in selected_ids]
            selected.extend(self._take_language_diverse_hits(route_hits, top_k_per_route, selected_ids))

        for hit in reranked_hits:
            if hit.evidence_id in selected_ids:
                continue
            selected.append(hit)
            selected_ids.add(hit.evidence_id)
            if len(selected) >= target_count:
                break

        return selected[:target_count]

    def _build_language_balanced_candidate_pool(
        self,
        indexed_hits: list,
        expected_routes: list[str],
        top_k_per_route: int,
    ) -> list:
        if not indexed_hits:
            return []
        normalized_routes = list(dict.fromkeys(route for route in expected_routes if route))
        if not normalized_routes:
            normalized_routes = list(dict.fromkeys(getattr(hit, "route", None) for hit in indexed_hits if getattr(hit, "route", None)))
        pooled: list = []
        seen_ids: set[str] = set()
        candidate_limit = max(top_k_per_route * 3, top_k_per_route)

        for route in normalized_routes:
            route_hits = [hit for hit in indexed_hits if getattr(hit, "route", None) == route]
            for hit in self._take_language_diverse_hits(route_hits, candidate_limit, seen_ids):
                pooled.append(hit)

        for hit in indexed_hits:
            if hit.evidence_id in seen_ids:
                continue
            pooled.append(hit)
            seen_ids.add(hit.evidence_id)

        return pooled

    def _take_language_diverse_hits(
        self,
        route_hits: list,
        limit: int,
        selected_ids: set[str],
    ) -> list:
        if limit <= 0 or not route_hits:
            return []

        language_groups: dict[str, list] = defaultdict(list)
        for hit in route_hits:
            language = getattr(hit, "language", None) or "unknown"
            language_groups[language].append(hit)

        ordered_languages = [language for language, _ in sorted(
            language_groups.items(),
            key=lambda entry: max(self._extract_score(hit) for hit in entry[1]),
            reverse=True,
        )]

        selected: list = []
        while len(selected) < limit:
            advanced = False
            for language in ordered_languages:
                bucket = language_groups[language]
                while bucket and bucket[0].evidence_id in selected_ids:
                    bucket.pop(0)
                if not bucket:
                    continue
                hit = bucket.pop(0)
                selected.append(hit)
                selected_ids.add(hit.evidence_id)
                advanced = True
                if len(selected) >= limit:
                    break
            if not advanced:
                break

        return selected

    def _to_retrieved_evidence(self, evidence, embedding_score: float) -> RetrievedEvidence:
        rerank_score = self._extract_score(evidence)
        content_original = getattr(evidence, "content_original", None) or evidence.content
        content_normalized = getattr(evidence, "content_normalized", None) or evidence.content
        return RetrievedEvidence(
            product_id=evidence.product_id,
            route=evidence.route,
            doc_type=getattr(evidence, "doc_type", None),
            text_block_id=evidence.text_block_id,
            image_id=evidence.image_id,
            region_id=getattr(evidence, "region_id", None),
            region_label=getattr(evidence, "region_label", None),
            region_box=getattr(evidence, "region_box", None),
            source_section=evidence.source_section,
            image_path=evidence.image_path,
            content_preview=content_original[:200],
            language=getattr(evidence, "language", None),
            content_original=content_original,
            content_normalized=content_normalized,
            embedding_score=embedding_score,
            rerank_score=rerank_score,
        )

    def _tokenize(self, text: str) -> list[str]:
        if not text:
            return []
        return [token.lower() for token in TOKEN_RE.findall(text.lower()) if len(token) > 1]

    def _extract_score(self, evidence) -> float:
        if hasattr(evidence, "score"):
            return max(0.0, min(1.0, float(getattr(evidence, "score"))))
        payload = evidence.model_dump(mode="json") if hasattr(evidence, "model_dump") else {}
        return max(0.0, min(1.0, float(payload.get("score", 0.0))))

    def _make_retrieval_id(self, review_id: str, aspect: str, query: str) -> str:
        digest = hashlib.sha1(f"{review_id}:{aspect}:{query}".encode("utf-8")).hexdigest()[:12]
        return f"retrieval_{digest}"