import math
import re
from collections import Counter, OrderedDict
from functools import lru_cache
from pathlib import Path

from openai import OpenAI
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.retrieval_cache import QueryEmbeddingCacheSignature
from decathlon_voc_analyzer.stage3_retrieval.retrieval_cache_service import RetrievalCacheService


TOKEN_RE = re.compile(r"[\w\-\u4e00-\u9fff가-힣]+", re.UNICODE)


class EmbeddingService:
    VECTOR_DIMENSION = 64
    QUERY_EMBEDDING_CACHE_SIZE = 256

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: OpenAI | None = None
        self._vector_size: int | None = None
        self._clip_model: CLIPModel | None = None
        self._clip_processor: CLIPProcessor | None = None
        self._clip_vector_size: int | None = None
        self._query_embedding_cache: OrderedDict[str, list[float]] = OrderedDict()
        self.cache_service = RetrievalCacheService()

    def embed_text(self, text: str) -> list[float]:
        if self.settings.embedding_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                return self._api_embedding(text)
            except Exception:
                return self._hashed_embedding(text)
        return self._hashed_embedding(text)

    def embed_image_proxy_text(self, text: str) -> list[float]:
        return self.embed_text(text)

    def embed_image(
        self,
        image_path: Path,
        text_hint: str | None = None,
        crop_box: tuple[int, int, int, int] | None = None,
    ) -> list[float]:
        if self.settings.image_embedding_backend == "clip":
            try:
                return self._clip_image_embedding(image_path, crop_box=crop_box)
            except Exception:
                return self.embed_image_proxy_text(text_hint or image_path.name)
        return self.embed_image_proxy_text(text_hint or image_path.name)

    def embed_query_for_route(self, text: str, route: str) -> list[float]:
        if route == "image" and self.settings.image_embedding_backend == "clip":
            signature = QueryEmbeddingCacheSignature(
                route="image",
                query=text,
                backend_kind="clip",
                model_name=self.settings.clip_vl_embedding_model,
            )
            cached = self._load_cached_query_embedding(signature)
            if cached is not None:
                return cached
            try:
                vector = self._clip_text_embedding(text)
                return self._store_query_embedding(signature, vector)
            except Exception:
                return self._embed_text_query(text=text, route=route, allow_cache=False)
        return self._embed_text_query(text=text, route=route)

    def similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        score = sum(a * b for a, b in zip(left, right))
        return max(0.0, min(1.0, float(score)))

    def vector_size(self) -> int:
        return self.vector_size_for_route("text")

    def vector_size_for_route(self, route: str) -> int:
        if route == "image" and self.settings.image_embedding_backend == "clip":
            if self._clip_vector_size is not None:
                return self._clip_vector_size
            try:
                self._clip_vector_size = len(self._clip_text_embedding("dimension probe"))
            except Exception:
                self._clip_vector_size = self.VECTOR_DIMENSION
            return self._clip_vector_size
        if self._vector_size is not None:
            return self._vector_size
        if self.settings.embedding_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                self._vector_size = len(self._api_embedding("dimension probe"))
                return self._vector_size
            except Exception:
                self._vector_size = self.VECTOR_DIMENSION
                return self._vector_size
        self._vector_size = self.VECTOR_DIMENSION
        return self._vector_size

    def _api_embedding(self, text: str) -> list[float]:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.qwen_plus_api_key,
                base_url=self.settings.qwen_base_url,
            )
        response = self._client.embeddings.create(
            model=self.settings.qwen_embedding_model,
            input=text,
        )
        vector = list(response.data[0].embedding)
        self._vector_size = len(vector)
        return vector

    def _embed_text_query(self, text: str, route: str, allow_cache: bool = True) -> list[float]:
        signature = self._text_query_cache_signature(text=text, route=route)
        if allow_cache:
            cached = self._load_cached_query_embedding(signature)
            if cached is not None:
                return cached

        if self.settings.embedding_backend == "api" and self.settings.qwen_plus_api_key:
            try:
                vector = self._api_embedding(text)
            except Exception:
                return self._hashed_embedding(text)
        else:
            vector = self._hashed_embedding(text)

        if not allow_cache:
            return vector
        return self._store_query_embedding(signature, vector)

    def _text_query_cache_signature(self, text: str, route: str) -> QueryEmbeddingCacheSignature:
        if self.settings.embedding_backend == "api" and self.settings.qwen_plus_api_key:
            return QueryEmbeddingCacheSignature(
                route=route,
                query=text,
                backend_kind="api",
                model_name=self.settings.qwen_embedding_model,
                base_url=self.settings.qwen_base_url,
            )
        return QueryEmbeddingCacheSignature(
            route=route,
            query=text,
            backend_kind="hash",
            model_name=f"hash-{self.VECTOR_DIMENSION}",
        )

    def _load_cached_query_embedding(self, signature: QueryEmbeddingCacheSignature) -> list[float] | None:
        cache_key = self.cache_service.signature_token(signature)
        cached = self._query_embedding_cache.get(cache_key)
        if cached is None:
            cached = self.cache_service.load_query_embedding(signature)
            if cached is None:
                return None
            self._query_embedding_cache[cache_key] = list(cached)
        self._query_embedding_cache.move_to_end(cache_key)
        return list(self._query_embedding_cache[cache_key])

    def _store_query_embedding(self, signature: QueryEmbeddingCacheSignature, vector: list[float]) -> list[float]:
        cache_key = self.cache_service.signature_token(signature)
        cached_vector = list(vector)
        self._query_embedding_cache[cache_key] = cached_vector
        self._query_embedding_cache.move_to_end(cache_key)
        while len(self._query_embedding_cache) > self.QUERY_EMBEDDING_CACHE_SIZE:
            self._query_embedding_cache.popitem(last=False)
        self.cache_service.save_query_embedding(signature, cached_vector)
        return list(cached_vector)

    def _hashed_embedding(self, text: str) -> list[float]:
        tokens = [token.lower() for token in TOKEN_RE.findall(text.lower()) if len(token) > 1]
        counts = Counter(tokens)
        vector = [0.0] * self.VECTOR_DIMENSION
        for token, count in counts.items():
            bucket = hash(token) % self.VECTOR_DIMENSION
            vector[bucket] += float(count)
        return self._normalize_vector(vector)

    def _clip_text_embedding(self, text: str) -> list[float]:
        model, processor = self._get_clip_resources()
        inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            features = self._to_feature_vector(model.get_text_features(**inputs))
        self._clip_vector_size = len(features)
        return self._normalize_vector(features)

    def _clip_image_embedding(
        self,
        image_path: Path,
        crop_box: tuple[int, int, int, int] | None = None,
    ) -> list[float]:
        model, processor = self._get_clip_resources()
        with Image.open(image_path) as image:
            rgb_image = image.convert("RGB")
            if crop_box is not None:
                rgb_image = rgb_image.crop(crop_box)
            inputs = processor(images=rgb_image, return_tensors="pt")
        with torch.no_grad():
            features = self._to_feature_vector(model.get_image_features(**inputs))
        self._clip_vector_size = len(features)
        return self._normalize_vector(features)

    def _get_clip_resources(self) -> tuple[CLIPModel, CLIPProcessor]:
        if self._clip_model is None or self._clip_processor is None:
            self._clip_model, self._clip_processor = _load_clip_resources(self.settings.clip_vl_embedding_model)
        return self._clip_model, self._clip_processor

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _to_feature_vector(self, output: object) -> list[float]:
        if isinstance(output, torch.Tensor):
            return output.detach().cpu().reshape(-1).tolist()
        for attribute in ("text_embeds", "image_embeds", "pooler_output", "last_hidden_state"):
            value = getattr(output, attribute, None)
            if isinstance(value, torch.Tensor):
                return value.detach().cpu().reshape(-1).tolist()
        raise TypeError(f"Unsupported CLIP output type: {type(output).__name__}")


@lru_cache(maxsize=2)
def _load_clip_resources(model_name: str) -> tuple[CLIPModel, CLIPProcessor]:
    model = CLIPModel.from_pretrained(model_name, use_safetensors=False)
    model.eval()
    processor = CLIPProcessor.from_pretrained(model_name)
    return model, processor