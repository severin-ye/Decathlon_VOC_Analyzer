from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.index import (
    IndexBuildRequest,
    IndexBuildResponse,
    IndexBuildStats,
    IndexedEvidence,
    IndexOverview,
    ProductIndexSnapshot,
)
from decathlon_voc_analyzer.runtime_progress import get_workflow_progress
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
        progress = get_workflow_progress()
        products = self.dataset_service._select_product_directories(
            categories=request.categories,
            product_ids=request.product_ids,
            max_products=request.max_products,
        )
        snapshots: list[ProductIndexSnapshot] = []
        stats = IndexBuildStats()

        progress.start_count_step("index", "load_packages", total=len(products), detail=f"准备加载 {len(products)} 个商品包")

        for directory in products:
            package = self.dataset_service.load_product_package(
                product_id=directory.product_id,
                category_slug=directory.category_slug,
            )
            evidence = self._build_evidence_for_package(package)
            progress.advance_step("index", "load_packages", detail=package.product_id)
            text_count = sum(1 for item in evidence if item.route == "text")
            image_count = len(package.images)
            image_region_count = sum(len(image.regions) for image in package.images)
            snapshots.append(
                ProductIndexSnapshot(
                    product_id=package.product_id,
                    category_slug=package.category_slug,
                    text_count=text_count,
                    image_count=image_count,
                    image_region_count=image_region_count,
                    evidence=evidence,
                )
            )
            stats.indexed_products += 1
            stats.indexed_text_blocks += text_count
            stats.indexed_images += image_count
            stats.indexed_image_regions += image_region_count

        progress.complete_step("index", "load_packages")
        progress.start_count_step("index", "persist", total=1, detail="保存索引快照")
        index_path = self.backend.save_snapshots(snapshots) if request.persist_artifact else None
        progress.complete_step("index", "persist", detail=index_path or "no index artifact")
        progress.complete_module("index")

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
            indexed_image_regions=sum(snapshot.image_region_count for snapshot in snapshots),
            index_path=self.backend.index_location(),
        )

    def get_or_create_product_snapshot(self, product_id: str, category_slug: str | None = None) -> ProductIndexSnapshot:
        progress = get_workflow_progress()
        snapshots = self.backend.load_snapshots()
        for snapshot in snapshots:
            if snapshot.product_id == product_id and (category_slug is None or snapshot.category_slug == category_slug):
                return snapshot

        progress.activate_module("index", detail=f"按需为 {product_id} 构建索引")
        progress.start_count_step("index", "load_packages", total=1, detail=f"加载 {product_id} 商品包")
        package = self.dataset_service.load_product_package(product_id=product_id, category_slug=category_slug)
        progress.complete_step("index", "load_packages", detail=package.product_id)
        snapshot = ProductIndexSnapshot(
            product_id=package.product_id,
            category_slug=package.category_slug,
            text_count=len(package.text_blocks),
            image_count=len(package.images),
            image_region_count=sum(len(image.regions) for image in package.images),
            evidence=self._build_evidence_for_package(package),
        )
        snapshots.append(snapshot)
        progress.start_count_step("index", "persist", total=1, detail="保存索引快照")
        self.backend.save_snapshots(snapshots)
        progress.complete_step("index", "persist", detail=self.backend.index_location())
        progress.complete_module("index", detail=f"按需索引完成: {product_id}")
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
        progress = get_workflow_progress()
        evidence: list[IndexedEvidence] = []
        progress.start_count_step("index", "embed_text", total=len(package.text_blocks), detail=f"{package.product_id} 文本向量")
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
            progress.advance_step("index", "embed_text", detail=text_block.text_block_id)
        progress.complete_step("index", "embed_text")

        total_image_units = len(package.images) + sum(len(image.regions) for image in package.images)
        progress.start_count_step("index", "embed_image", total=total_image_units, detail=f"{package.product_id} 图像/局部向量")
        for image in package.images:
            proxy_text = " ".join(
                part for part in [package.product_name, package.category_text, package.model_description, image.variant, image.image_path] if part
            )
            image_source_path = self.dataset_service.settings.dataset_root / package.category_slug / package.product_id / image.image_path
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
                    vector=self.embedding_service.embed_image(image_path=image_source_path, text_hint=proxy_text),
                )
            )
            progress.advance_step("index", "embed_image", detail=image.image_id)
            for region in image.regions:
                region_box = tuple(region.region_box)
                region_text = " ".join(
                    part
                    for part in [
                        package.product_name,
                        package.category_text,
                        package.model_description,
                        image.variant,
                        region.region_label,
                        image.image_path,
                    ]
                    if part
                )
                evidence.append(
                    IndexedEvidence(
                        evidence_id=region.region_id,
                        product_id=package.product_id,
                        category_slug=package.category_slug,
                        route="image",
                        image_id=image.image_id,
                        image_path=image.image_path,
                        variant=image.variant,
                        region_id=region.region_id,
                        region_label=region.region_label,
                        region_box=region.region_box,
                        content=region_text,
                        vector=self.embedding_service.embed_image(
                            image_path=image_source_path,
                            text_hint=region_text,
                            crop_box=region_box,
                        ),
                    )
                )
                progress.advance_step("index", "embed_image", detail=region.region_id)
        progress.complete_step("index", "embed_image")
        return evidence