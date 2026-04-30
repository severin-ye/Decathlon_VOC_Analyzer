import base64
from io import BytesIO
import json
from pathlib import Path
from typing import Callable
from urllib import request

from openai import OpenAI
from PIL import Image

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.app.core.runtime_policy import RuntimePolicyError, get_runtime_execution_policy, should_forbid_degradation
from decathlon_voc_analyzer.schemas.index import IndexedEvidence
from decathlon_voc_analyzer.schemas.retrieval_cache import RerankCacheSignature
from decathlon_voc_analyzer.stage3_retrieval.retrieval_cache_service import RetrievalCacheService
from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import (
    get_reranker_model,
    get_multimodal_reranker_model,
)


class RerankerService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: OpenAI | None = None
        self.cache_service = RetrievalCacheService()

    def rerank(
        self,
        query: str,
        candidates: list[IndexedEvidence],
        use_llm: bool,
        progress_callback: Callable[[str], None] | None = None,
        progress_status_callback: Callable[[str], None] | None = None,
    ) -> list[IndexedEvidence]:
        if not candidates:
            if progress_status_callback is not None:
                progress_status_callback("当前问题没有可重排候选")
            if progress_callback is not None:
                progress_callback("文本重排完成: 无候选")
                progress_callback("图像重排完成: 无候选")
            return []
        text_candidates = [candidate for candidate in candidates if candidate.route == "text"]
        image_candidates = [candidate for candidate in candidates if candidate.route == "image"]

        reranked: list[IndexedEvidence] = []
        if progress_status_callback is not None:
            progress_status_callback("正在检查文本候选")
        if text_candidates:
            if progress_status_callback is not None:
                progress_status_callback(f"正在进行文本重排（{len(text_candidates)} 条候选）")
            reranked.extend(self._rerank_text_candidates(query, text_candidates, use_llm))
            if progress_callback is not None:
                progress_callback(f"文本重排完成: {len(text_candidates)} 条候选")
        elif progress_callback is not None:
            progress_callback("文本重排完成: 无候选")
        if progress_status_callback is not None:
            progress_status_callback("正在检查图像候选")
        if image_candidates:
            if progress_status_callback is not None:
                progress_status_callback(f"正在进行图像重排（{len(image_candidates)} 条候选）")
            reranked.extend(self._rerank_image_candidates(query, image_candidates, use_llm))
            if progress_callback is not None:
                progress_callback(f"图像重排完成: {len(image_candidates)} 条候选")
        elif progress_callback is not None:
            progress_callback("图像重排完成: 无候选")
        return sorted(reranked, key=lambda item: item.score or 0.0, reverse=True)

    def _rerank_text_candidates(self, query: str, candidates: list[IndexedEvidence], use_llm: bool) -> list[IndexedEvidence]:
        # 优先尝试本地推理
        if use_llm and self.settings.reranker_backend == "local_qwen3":
            try:
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="text",
                    use_llm=use_llm,
                    backend_kind="local_qwen3",
                    compute=lambda: self._rerank_text_candidates_with_local(query, candidates),
                )
            except Exception as exc:
                self._raise_if_degradation_forbidden(
                    component="text_rerank",
                    exc=exc,
                    action="检查本地 Qwen3-Reranker 模型加载或推理后重试。",
                )
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="text",
                    use_llm=use_llm,
                    backend_kind="heuristic",
                    compute=lambda: self._rerank_heuristic(candidates),
                )
        # 其次尝试 API 推理
        if use_llm and self.settings.reranker_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="text",
                    use_llm=use_llm,
                    backend_kind="api",
                    compute=lambda: self._rerank_with_api(query, candidates),
                )
            except Exception as exc:
                self._raise_if_degradation_forbidden(
                    component="text_rerank",
                    exc=exc,
                    action="检查文本 reranker 服务状态、账户配额或网络后重试。",
                )
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="text",
                    use_llm=use_llm,
                    backend_kind="heuristic",
                    compute=lambda: self._rerank_heuristic(candidates),
                )
        return self._rerank_with_cache(
            query=query,
            candidates=candidates,
            route="text",
            use_llm=use_llm,
            backend_kind="heuristic",
            compute=lambda: self._rerank_heuristic(candidates),
        )

    def _rerank_image_candidates(self, query: str, candidates: list[IndexedEvidence], use_llm: bool) -> list[IndexedEvidence]:
        # 优先尝试本地多模态推理
        if use_llm and self.settings.multimodal_reranker_backend == "local_qwen3_vl":
            try:
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="image",
                    use_llm=use_llm,
                    backend_kind="local_qwen3_vl",
                    compute=lambda: self._rerank_image_candidates_with_local_vl(query, candidates),
                )
            except Exception as exc:
                self._raise_if_degradation_forbidden(
                    component="image_rerank",
                    exc=exc,
                    action="检查本地 Qwen3-VL-2B 模型加载或推理后重试。",
                )
        # 其次尝试 API VL 推理
        if use_llm and self.settings.multimodal_reranker_backend in {"api", "qwen_vl"} and self.settings.qwen_plus_api_key:
            try:
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="image",
                    use_llm=use_llm,
                    backend_kind="qwen_vl" if self.settings.multimodal_reranker_backend == "qwen_vl" else "api",
                    compute=lambda: self._rerank_image_candidates_with_vl(query, candidates),
                )
            except Exception as exc:
                self._raise_if_degradation_forbidden(
                    component="image_rerank",
                    exc=exc,
                    action="检查多模态 reranker 服务状态、账户配额或网络后重试。",
                )
        # 第三选项：尝试文本 API 推理
        if use_llm and self.settings.reranker_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="image",
                    use_llm=use_llm,
                    backend_kind="api",
                    compute=lambda: self._rerank_with_api(query, candidates),
                )
            except Exception as exc:
                self._raise_if_degradation_forbidden(
                    component="image_rerank",
                    exc=exc,
                    action="检查文本 reranker 服务状态、账户配额或网络后重试。",
                )
                return self._rerank_with_cache(
                    query=query,
                    candidates=candidates,
                    route="image",
                    use_llm=use_llm,
                    backend_kind="heuristic",
                    compute=lambda: self._rerank_heuristic(candidates),
                )
        return self._rerank_with_cache(
            query=query,
            candidates=candidates,
            route="image",
            use_llm=use_llm,
            backend_kind="heuristic",
            compute=lambda: self._rerank_heuristic(candidates),
        )

    def _rerank_with_cache(
        self,
        query: str,
        candidates: list[IndexedEvidence],
        route: str,
        use_llm: bool,
        backend_kind: str,
        compute,
    ) -> list[IndexedEvidence]:
        signature = self._build_rerank_cache_signature(
            query=query,
            candidates=candidates,
            route=route,
            use_llm=use_llm,
            backend_kind=backend_kind,
        )
        cached = self.cache_service.load_rerank(signature)
        if cached is not None:
            return cached
        reranked = compute()
        self.cache_service.save_rerank(signature, reranked)
        return reranked

    def _raise_if_degradation_forbidden(self, component: str, exc: Exception, action: str) -> None:
        policy = get_runtime_execution_policy(self.settings)
        if not should_forbid_degradation(policy):
            return
        raise RuntimePolicyError(
            component=component,
            problem=f"重排链路调用失败，当前策略不允许静默回退。原始错误: {exc}",
            action=action,
        ) from exc

    def _build_rerank_cache_signature(
        self,
        query: str,
        candidates: list[IndexedEvidence],
        route: str,
        use_llm: bool,
        backend_kind: str,
    ) -> RerankCacheSignature:
        return RerankCacheSignature(
            route=route,
            query=query,
            use_llm=use_llm,
            backend_kind=backend_kind,
            candidate_count=len(candidates),
            candidate_digest=self.cache_service.build_candidate_digest(candidates),
            base_url=self.settings.qwen_base_url if backend_kind in {"api", "qwen_vl"} else None,
            reranker_model=self.settings.qwen_reranker_model if backend_kind == "api" else (
                self.settings.local_reranker_model_name if backend_kind == "local_qwen3" else None
            ),
            multimodal_reranker_model=(
                self.settings.qwen_vl_reranker_model if backend_kind == "qwen_vl" else (
                    self.settings.local_multimodal_reranker_model_name if backend_kind == "local_qwen3_vl" else None
                )
            ),
        )

    def _rerank_with_api(self, query: str, candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        payload = {
            "model": self.settings.qwen_reranker_model,
            "input": {
                "query": query,
                "documents": [self._candidate_text(candidate) for candidate in candidates],
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
        with request.urlopen(api_request, timeout=self.settings.text_reranker_timeout_seconds) as response:
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

    def _rerank_text_candidates_with_local(self, query: str, candidates: list[IndexedEvidence]) -> list[IndexedEvidence]:
        """使用本地 Qwen3-Reranker-0.6B 模型进行文本重排"""
        model = get_reranker_model(self.settings.local_reranker_model_name)
        model.device = self.settings.local_model_device
        
        documents = [self._candidate_text(candidate) for candidate in candidates]
        results = model.rerank(query=query, documents=documents, top_n=len(candidates))
        
        rerank_scores = {
            candidates[item.get("index", -1)].evidence_id: self._normalize_score(item.get("relevance_score", 0.0))
            for item in results
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

    def _rerank_image_candidates_with_local_vl(
        self,
        query: str,
        candidates: list[IndexedEvidence],
    ) -> list[IndexedEvidence]:
        """使用本地 Qwen3-VL-2B 模型进行多模态图像重排"""
        model = get_multimodal_reranker_model(self.settings.local_multimodal_reranker_model_name)
        model.device = self.settings.local_model_device
        
        candidate_data = []
        for index, candidate in enumerate(candidates):
            image_path = None
            if candidate.image_path:
                image_path = Path(self.settings.dataset_root) / candidate.category_slug / candidate.product_id / candidate.image_path
                if not image_path.exists():
                    image_path = None
            
            candidate_data.append({
                "index": index,
                "text": self._candidate_text(candidate),
                "image_path": str(image_path) if image_path else None,
            })
        
        results = model.rerank(query=query, candidates=candidate_data, top_n=len(candidates))
        
        rerank_scores = {
            candidates[item.get("index", -1)].evidence_id: self._normalize_score(item.get("relevance_score", 0.0))
            for item in results
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
                    "text": f"Candidate {index}: evidence_id={candidate.evidence_id}; text_hint={self._candidate_text(candidate)}",
                }
            )
            image_url = self._candidate_image_data_url(candidate)
            if image_url is not None:
                content.append({"type": "image_url", "image_url": {"url": image_url}})

        client = self._get_openai_client().with_options(
            timeout=self.settings.multimodal_reranker_timeout_seconds,
            max_retries=self.settings.multimodal_reranker_max_retries,
        )
        response = client.chat.completions.create(
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

    def _candidate_text(self, candidate: IndexedEvidence) -> str:
        return candidate.content_normalized or candidate.content_original or candidate.content