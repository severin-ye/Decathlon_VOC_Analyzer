from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

import orjson
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.index import IndexedEvidence, ProductIndexSnapshot
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService


class IndexBackend(ABC):
    @abstractmethod
    def save_snapshots(self, snapshots: list[ProductIndexSnapshot]) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def load_snapshots(self) -> list[ProductIndexSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        product_id: str,
        category_slug: str | None,
        query: str,
        routes: list[str],
        top_k_per_route: int,
    ) -> list[IndexedEvidence]:
        raise NotImplementedError

    @abstractmethod
    def index_exists(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def index_location(self) -> str:
        raise NotImplementedError

    def close(self) -> None:
        return None


class LocalIndexBackend(IndexBackend):
    def __init__(self, path: Path, embedding_service: EmbeddingService) -> None:
        self.path = path
        self.embedding_service = embedding_service

    def save_snapshots(self, snapshots: list[ProductIndexSnapshot]) -> str | None:
        payload = [snapshot.model_dump(mode="json") for snapshot in snapshots]
        self.path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        return str(self.path)

    def load_snapshots(self) -> list[ProductIndexSnapshot]:
        if not self.path.exists():
            return []
        payload = orjson.loads(self.path.read_bytes())
        return [ProductIndexSnapshot.model_validate(item) for item in payload]

    def search(
        self,
        product_id: str,
        category_slug: str | None,
        query: str,
        routes: list[str],
        top_k_per_route: int,
    ) -> list[IndexedEvidence]:
        snapshots = self.load_snapshots()
        snapshot = next(
            (
                item
                for item in snapshots
                if item.product_id == product_id and (category_slug is None or item.category_slug == category_slug)
            ),
            None,
        )
        if snapshot is None:
            return []
        ranked: dict[str, list[tuple[float, IndexedEvidence]]] = {"text": [], "image": []}
        for route in routes:
            query_vector = self.embedding_service.embed_query_for_route(query, route)
            for evidence in snapshot.evidence:
                if evidence.route != route:
                    continue
                score = self.embedding_service.similarity(query_vector, evidence.vector)
                ranked[evidence.route].append((score, evidence))

        results: list[IndexedEvidence] = []
        for route in routes:
            hits = sorted(ranked.get(route, []), key=lambda item: item[0], reverse=True)[:top_k_per_route]
            for score, evidence in hits:
                results.append(IndexedEvidence.model_validate({**evidence.model_dump(mode="json"), "score": score}))
        return results

    def index_exists(self) -> bool:
        return self.path.exists()

    def index_location(self) -> str:
        return str(self.path)


class QdrantIndexBackend(IndexBackend):
    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.settings = get_settings()
        self.embedding_service = embedding_service
        self.settings.qdrant_path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(self.settings.qdrant_path))
        self.collection_name = self.settings.qdrant_collection_name

    def save_snapshots(self, snapshots: list[ProductIndexSnapshot]) -> str | None:
        points_by_route: dict[str, list[PointStruct]] = {"text": [], "image": []}
        point_id = 1
        for snapshot in snapshots:
            for evidence in snapshot.evidence:
                payload = evidence.model_dump(mode="json")
                payload["product_id"] = snapshot.product_id
                payload["category_slug"] = snapshot.category_slug
                points_by_route[evidence.route].append(PointStruct(id=point_id, vector=evidence.vector, payload=payload))
                point_id += 1

        collections = {item.name for item in self.client.get_collections().collections}
        for route in ("text", "image"):
            collection_name = self._collection_name_for_route(route)
            if collection_name in collections:
                self.client.delete_collection(collection_name=collection_name)
            self._ensure_collection(route)
            route_points = points_by_route[route]
            if route_points:
                self.client.upsert(collection_name=collection_name, points=route_points)
        manifest_path = self.settings.qdrant_path / "manifest.json"
        manifest_path.write_bytes(
            orjson.dumps(
                [snapshot.model_dump(mode="json") for snapshot in snapshots],
                option=orjson.OPT_INDENT_2,
            )
        )
        return str(self.settings.qdrant_path)

    def load_snapshots(self) -> list[ProductIndexSnapshot]:
        manifest_path = self.settings.qdrant_path / "manifest.json"
        if not manifest_path.exists():
            return []
        payload = orjson.loads(manifest_path.read_bytes())
        return [ProductIndexSnapshot.model_validate(item) for item in payload]

    def search(
        self,
        product_id: str,
        category_slug: str | None,
        query: str,
        routes: list[str],
        top_k_per_route: int,
    ) -> list[IndexedEvidence]:
        results: list[IndexedEvidence] = []
        for route in routes:
            collection_name = self._collection_name_for_route(route)
            if collection_name not in {item.name for item in self.client.get_collections().collections}:
                continue
            query_vector = self.embedding_service.embed_query_for_route(query, route)
            conditions = [
                FieldCondition(key="product_id", match=MatchValue(value=product_id)),
                FieldCondition(key="route", match=MatchValue(value=route)),
            ]
            if category_slug:
                conditions.append(FieldCondition(key="category_slug", match=MatchValue(value=category_slug)))
            response = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k_per_route,
                query_filter=Filter(must=conditions),
            )
            for point in response.points:
                payload = dict(point.payload or {})
                payload["score"] = max(0.0, min(1.0, float(point.score)))
                results.append(IndexedEvidence.model_validate(payload))
        return results

    def index_exists(self) -> bool:
        return (self.settings.qdrant_path / "manifest.json").exists()

    def index_location(self) -> str:
        return str(self.settings.qdrant_path)

    def close(self) -> None:
        self.client.close()

    def _ensure_collection(self) -> None:
        raise NotImplementedError

    def _ensure_collection(self, route: str) -> None:
        collection_name = self._collection_name_for_route(route)
        collections = {item.name for item in self.client.get_collections().collections}
        if collection_name in collections:
            return
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=self.embedding_service.vector_size_for_route(route), distance=Distance.COSINE),
        )

    def _collection_name_for_route(self, route: str) -> str:
        return f"{self.collection_name}_{route}"


@lru_cache(maxsize=4)
def create_index_backend() -> IndexBackend:
    settings = get_settings()
    embedding_service = EmbeddingService()
    if settings.retrieval_backend == "qdrant":
        return QdrantIndexBackend(embedding_service=embedding_service)
    return LocalIndexBackend(
        path=settings.indexes_output_dir / "local_evidence_index.json",
        embedding_service=embedding_service,
    )


def dispose_index_backend() -> None:
    backend = create_index_backend()
    backend.close()
    create_index_backend.cache_clear()