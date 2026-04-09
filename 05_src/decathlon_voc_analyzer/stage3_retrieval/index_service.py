from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.index import (
    IndexBuildRequest,
    IndexBuildResponse,
    IndexBuildStats,
    IndexedEvidence,
    IndexOverview,
    ProductIndexSnapshot,
)
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService
from decathlon_voc_analyzer.stage3_retrieval.embedding_service import EmbeddingService
from decathlon_voc_analyzer.stage3_retrieval.index_backends import create_index_backend


class IndexService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dataset_service = DatasetService()
        self.embedding_service = EmbeddingService()
        self.backend = create_index_backend()

    def build_index(self, request: IndexBuildRequest) -> IndexBuildResponse:
        products = self.dataset_service._select_product_directories(
            categories=request.categories,
            product_ids=request.product_ids,
            max_products=request.max_products,
        )
        snapshots: list[ProductIndexSnapshot] = []
        stats = IndexBuildStats()

        for directory in products:
            package = self.dataset_service.load_product_package(
                product_id=directory.product_id,
                category_slug=directory.category_slug,
            )
            evidence = self._build_evidence_for_package(package)
            text_count = sum(1 for item in evidence if item.route == "text")
            image_count = sum(1 for item in evidence if item.route == "image")
            snapshots.append(
                ProductIndexSnapshot(
                    product_id=package.product_id,
                    category_slug=package.category_slug,
                    text_count=text_count,
                    image_count=image_count,
                    evidence=evidence,
                )
            )
            stats.indexed_products += 1
            stats.indexed_text_blocks += text_count
            stats.indexed_images += image_count

        index_path = self.backend.save_snapshots(snapshots) if request.persist_artifact else None

        return IndexBuildResponse(
            backend=self.settings.retrieval_backend,
            stats=stats,
            index_path=index_path,
            product_ids=[snapshot.product_id for snapshot in snapshots],
        )

    def get_overview(self) -> IndexOverview:
        snapshots = self.backend.load_snapshots()
        return IndexOverview(
            backend=self.settings.retrieval_backend,
            index_exists=self.backend.index_exists(),
            indexed_products=len(snapshots),
            indexed_text_blocks=sum(snapshot.text_count for snapshot in snapshots),
            indexed_images=sum(snapshot.image_count for snapshot in snapshots),
            index_path=self.backend.index_location(),
        )

    def get_or_create_product_snapshot(self, product_id: str, category_slug: str | None = None) -> ProductIndexSnapshot:
        snapshots = self.backend.load_snapshots()
        for snapshot in snapshots:
            if snapshot.product_id == product_id and (category_slug is None or snapshot.category_slug == category_slug):
                return snapshot

        package = self.dataset_service.load_product_package(product_id=product_id, category_slug=category_slug)
        snapshot = ProductIndexSnapshot(
            product_id=package.product_id,
            category_slug=package.category_slug,
            text_count=len(package.text_blocks),
            image_count=len(package.images),
            evidence=self._build_evidence_for_package(package),
        )
        snapshots.append(snapshot)
        self.backend.save_snapshots(snapshots)
        return snapshot

    def search(
        self,
        product_id: str,
        query: str,
        routes: list[str],
        top_k_per_route: int,
        category_slug: str | None = None,
    ) -> list[IndexedEvidence]:
        self.get_or_create_product_snapshot(product_id=product_id, category_slug=category_slug)
        return self.backend.search(
            product_id=product_id,
            category_slug=category_slug,
            query=query,
            routes=routes,
            top_k_per_route=top_k_per_route,
        )

    def _build_evidence_for_package(self, package) -> list[IndexedEvidence]:
        evidence: list[IndexedEvidence] = []
        for text_block in package.text_blocks:
            evidence.append(
                IndexedEvidence(
                    evidence_id=text_block.text_block_id,
                    product_id=package.product_id,
                    category_slug=package.category_slug,
                    route="text",
                    text_block_id=text_block.text_block_id,
                    source_section=text_block.source_section,
                    content=text_block.content,
                    vector=self.embedding_service.embed_text(text_block.content),
                )
            )
        for image in package.images:
            proxy_text = " ".join(
                part for part in [package.product_name, package.category_text, package.model_description, image.variant, image.image_path] if part
            )
            evidence.append(
                IndexedEvidence(
                    evidence_id=image.image_id,
                    product_id=package.product_id,
                    category_slug=package.category_slug,
                    route="image",
                    image_id=image.image_id,
                    image_path=image.image_path,
                    variant=image.variant,
                    content=proxy_text,
                    vector=self.embedding_service.embed_image_proxy_text(proxy_text),
                )
            )
        return evidence