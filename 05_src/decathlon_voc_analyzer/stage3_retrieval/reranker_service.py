import base64
from io import BytesIO
import json
from pathlib import Path
from urllib import request

from openai import OpenAI
from PIL import Image

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.index import IndexedEvidence


class RerankerService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: OpenAI | None = None

    def rerank(self, query: str, candidates: list[IndexedEvidence], use_llm: bool) -> list[IndexedEvidence]:
        if not candidates:
            return []
        text_candidates = [candidate for candidate in candidates if candidate.route == "text"]
        image_candidates = [candidate for candidate in candidates if candidate.route == "image"]

        reranked: list[IndexedEvidence] = []
        if text_candidates:
            reranked.extend(self._rerank_text_candidates(query, text_candidates, use_llm))
        if image_candidates:
            reranked.extend(self._rerank_image_candidates(query, image_candidates, use_llm))
        return sorted(reranked, key=lambda item: item.score or 0.0, reverse=True)

    def _rerank_text_candidates(self, query: str, candidates: list[IndexedEvidence], use_llm: bool) -> list[IndexedEvidence]:
        if use_llm and self.settings.reranker_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                return self._rerank_with_api(query, candidates)
            except Exception:
                return self._rerank_heuristic(candidates)
        return self._rerank_heuristic(candidates)

    def _rerank_image_candidates(self, query: str, candidates: list[IndexedEvidence], use_llm: bool) -> list[IndexedEvidence]:
        if use_llm and self.settings.multimodal_reranker_backend in {"api", "qwen_vl"} and self.settings.qwen_plus_api_key:
            try:
                return self._rerank_image_candidates_with_vl(query, candidates)
            except Exception:
                pass
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

    def _rerank_image_candidates_with_vl(self, query: str, candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    "You are a multimodal reranker. Score each candidate image from 0.0 to 1.0 against the query. "
                    "Return strict JSON with this shape: {\"results\":[{\"index\":0,\"relevance_score\":0.0}]}. "
                    "Use image content as the primary signal and candidate text as auxiliary context."
                ),
            },
            {"type": "text", "text": f"Query: {query}"},
        ]
        for index, candidate in enumerate(candidates):
            content.append(
                {
                    "type": "text",
                    "text": f"Candidate {index}: evidence_id={candidate.evidence_id}; text_hint={candidate.content}",
                }
            )
            image_url = self._candidate_image_data_url(candidate)
            if image_url is not None:
                content.append({"type": "image_url", "image_url": {"url": image_url}})

        response = self._get_openai_client().chat.completions.create(
            model=self.settings.qwen_vl_reranker_model,
            temperature=0,
            max_tokens=400,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": content}],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        rerank_scores = {
            candidates[int(item.get("index", -1))].evidence_id: self._normalize_score(item.get("relevance_score", 0.0))
            for item in payload.get("results", [])
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

    def _candidate_image_data_url(self, candidate: IndexedEvidence) -> str | None:
        if not candidate.image_path:
            return None
        image_path = Path(self.settings.dataset_root) / candidate.category_slug / candidate.product_id / candidate.image_path
        if not image_path.exists():
            return None
        if candidate.region_box is not None:
            try:
                with Image.open(image_path) as image:
                    cropped = image.convert("RGB").crop(tuple(candidate.region_box))
                    buffer = BytesIO()
                    cropped.save(buffer, format="PNG")
                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                return f"data:image/png;base64,{encoded}"
            except Exception:
                return None
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _get_openai_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.qwen_plus_api_key,
                base_url=self.settings.qwen_base_url,
            )
        return self._client

    def _normalize_score(self, score: float | int) -> float:
        return max(0.0, min(1.0, float(score)))