import json
from urllib import request

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.index import IndexedEvidence


class RerankerService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def rerank(self, query: str, candidates: list[IndexedEvidence], use_llm: bool) -> list[IndexedEvidence]:
        if not candidates:
            return []
        if use_llm and self.settings.reranker_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                return self._rerank_with_api(query, candidates)
            except Exception:
                return self._rerank_heuristic(candidates)
        return self._rerank_heuristic(candidates)

    def _rerank_with_api(self, query: str, candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        payload = {
            "model": self.settings.qwen_reranker_model,
            "input": {
                "query": query,
                "documents": [candidate.content for candidate in candidates],
            },
            "parameters": {
                "top_n": len(candidates),
                "return_documents": False,
            },
        }
        api_request = request.Request(
            self.settings.dashscope_rerank_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.qwen_plus_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(api_request, timeout=60) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        rerank_scores = {
            candidates[int(item.get("index", -1))].evidence_id: self._normalize_score(item.get("relevance_score", 0.0))
            for item in parsed.get("output", {}).get("results", [])
            if isinstance(item, dict) and isinstance(item.get("index"), int) and 0 <= int(item.get("index")) < len(candidates)
        }
        ranked = [
            IndexedEvidence.model_validate(
                {
                    **candidate.model_dump(mode="json"),
                    "score": rerank_scores.get(candidate.evidence_id, candidate.score),
                }
            )
            for candidate in candidates
        ]
        return sorted(ranked, key=lambda item: item.score or 0.0, reverse=True)

    def _rerank_heuristic(self, candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        return sorted(candidates, key=lambda item: item.score or 0.0, reverse=True)

    def _normalize_score(self, score: float | int) -> float:
        return max(0.0, min(1.0, float(score)))