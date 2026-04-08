import hashlib
import re

from decathlon_voc_analyzer.models.analysis import RetrievedEvidence, RetrievalQuestion, RetrievalRecord
from decathlon_voc_analyzer.models.dataset import ProductEvidencePackage
from decathlon_voc_analyzer.services.index_service import IndexService


TOKEN_RE = re.compile(r"[\w\-\u4e00-\u9fff가-힣]+", re.UNICODE)


class RetrievalService:
    def __init__(self) -> None:
        self.index_service = IndexService()

    def retrieve_for_package(
        self,
        package: ProductEvidencePackage,
        questions: list[RetrievalQuestion],
        top_k_per_route: int = 2,
    ) -> list[RetrievalRecord]:
        return [
            self._retrieve_for_question(package=package, question=question, top_k_per_route=top_k_per_route)
            for question in questions
        ]

    def _retrieve_for_question(
        self,
        package: ProductEvidencePackage,
        question: RetrievalQuestion,
        top_k_per_route: int,
    ) -> RetrievalRecord:
        query = question.question
        indexed_hits = self.index_service.search(
            product_id=package.product_id,
            category_slug=package.category_slug,
            query=query,
            routes=question.expected_evidence_routes,
            top_k_per_route=top_k_per_route,
        )
        retrieved = [self._to_retrieved_evidence(hit) for hit in indexed_hits]

        return RetrievalRecord(
            retrieval_id=self._make_retrieval_id(question.source_review_id, question.source_aspect, query),
            product_id=package.product_id,
            query=query,
            source_review_id=question.source_review_id,
            source_aspect=question.source_aspect,
            source_question_id=question.question_id,
            source_question=question.question,
            source_evidence_span=question.rationale,
            retrieved=retrieved,
        )

    def _to_retrieved_evidence(self, evidence) -> RetrievedEvidence:
        return RetrievedEvidence(
            product_id=evidence.product_id,
            route=evidence.route,
            text_block_id=evidence.text_block_id,
            image_id=evidence.image_id,
            source_section=evidence.source_section,
            image_path=evidence.image_path,
            content_preview=evidence.content[:200],
            embedding_score=self._extract_score(evidence),
            rerank_score=self._extract_score(evidence),
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