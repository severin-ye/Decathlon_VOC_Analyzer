import hashlib
import re

from decathlon_voc_analyzer.schemas.analysis import RetrievedEvidence, RetrievalQuestion, RetrievalRecord
from decathlon_voc_analyzer.schemas.dataset import ProductEvidencePackage
from decathlon_voc_analyzer.stage3_retrieval.index_service import IndexService
from decathlon_voc_analyzer.stage3_retrieval.reranker_service import RerankerService


TOKEN_RE = re.compile(r"[\w\-\u4e00-\u9fff가-힣]+", re.UNICODE)


class RetrievalService:
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
        return [
            self._retrieve_for_question(
                package=package,
                question=question,
                top_k_per_route=top_k_per_route,
                use_llm=use_llm,
            )
            for question in questions
        ]

    def _retrieve_for_question(
        self,
        package: ProductEvidencePackage,
        question: RetrievalQuestion,
        top_k_per_route: int,
        use_llm: bool,
    ) -> RetrievalRecord:
        query = question.question
        indexed_hits = self.index_service.search(
            product_id=package.product_id,
            category_slug=package.category_slug,
            query=query,
            routes=question.expected_evidence_routes,
            top_k_per_route=max(top_k_per_route * 3, top_k_per_route),
        )
        embedding_scores = {
            hit.evidence_id: self._extract_score(hit)
            for hit in indexed_hits
        }
        reranked_hits = self.reranker_service.rerank(query=query, candidates=indexed_hits, use_llm=use_llm)
        selected_hits = self._select_hits_with_route_coverage(
            reranked_hits=reranked_hits,
            expected_routes=question.expected_evidence_routes,
            top_k_per_route=top_k_per_route,
        )
        retrieved = [
            self._to_retrieved_evidence(hit, embedding_scores.get(hit.evidence_id, 0.0))
            for hit in selected_hits
        ]

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
        target_count = max(1, len(normalized_routes)) * top_k_per_route
        selected: list = []
        selected_ids: set[str] = set()

        for route in normalized_routes:
            route_hit = next(
                (hit for hit in reranked_hits if getattr(hit, "route", None) == route and hit.evidence_id not in selected_ids),
                None,
            )
            if route_hit is None:
                continue
            selected.append(route_hit)
            selected_ids.add(route_hit.evidence_id)

        for hit in reranked_hits:
            if hit.evidence_id in selected_ids:
                continue
            selected.append(hit)
            selected_ids.add(hit.evidence_id)
            if len(selected) >= target_count:
                break

        return selected[:target_count]

    def _to_retrieved_evidence(self, evidence, embedding_score: float) -> RetrievedEvidence:
        rerank_score = self._extract_score(evidence)
        return RetrievedEvidence(
            product_id=evidence.product_id,
            route=evidence.route,
            text_block_id=evidence.text_block_id,
            image_id=evidence.image_id,
            region_id=getattr(evidence, "region_id", None),
            region_label=getattr(evidence, "region_label", None),
            region_box=getattr(evidence, "region_box", None),
            source_section=evidence.source_section,
            image_path=evidence.image_path,
            content_preview=evidence.content[:200],
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