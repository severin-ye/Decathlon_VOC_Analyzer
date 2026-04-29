from typing import Literal

from pydantic import BaseModel, Field


IndexRoute = Literal["text", "image"]


class IndexedEvidence(BaseModel):
    evidence_id: str
    product_id: str
    category_slug: str
    route: IndexRoute
    doc_type: str | None = None
    text_block_id: str | None = None
    image_id: str | None = None
    source_section: str | None = None
    image_path: str | None = None
    variant: str | None = None
    region_id: str | None = None
    region_label: str | None = None
    region_box: list[int] | None = Field(default=None, min_length=4, max_length=4)
    content: str
    language: str | None = None
    content_original: str | None = None
    content_normalized: str | None = None
    vector: list[float] = Field(default_factory=list)
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class ProductIndexSnapshot(BaseModel):
    product_id: str
    category_slug: str
    text_count: int
    image_count: int
    image_region_count: int = 0
    evidence: list[IndexedEvidence] = Field(default_factory=list)


class IndexBuildRequest(BaseModel):
    categories: list[str] | None = None
    product_ids: list[str] | None = None
    max_products: int | None = Field(default=None, ge=1)
    persist_artifact: bool = True
    use_llm: bool = True


class IndexBuildStats(BaseModel):
    indexed_products: int = 0
    indexed_text_blocks: int = 0
    indexed_images: int = 0
    indexed_image_regions: int = 0


class IndexBuildResponse(BaseModel):
    backend: str
    stats: IndexBuildStats
    index_path: str | None = None
    product_ids: list[str] = Field(default_factory=list)


class IndexOverview(BaseModel):
    backend: str
    index_exists: bool
    indexed_products: int
    indexed_text_blocks: int
    indexed_images: int
    indexed_image_regions: int = 0
    index_path: str