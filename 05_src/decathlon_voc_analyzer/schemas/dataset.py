from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ImageRegion(BaseModel):
    region_id: str
    region_label: str
    region_box: list[int] = Field(default_factory=list, min_length=4, max_length=4)


class ImageEvidence(BaseModel):
    image_id: str
    product_id: str
    variant: str | None = None
    image_type: str = "product"
    image_path: str
    aux_text: str | None = None
    language_hint: str | None = None
    width: int | None = None
    height: int | None = None
    regions: list[ImageRegion] = Field(default_factory=list)


class TextEvidence(BaseModel):
    text_block_id: str
    product_id: str
    text_type: Literal["title", "description", "category"]
    source_section: str
    content: str
    language: str | None = None
    content_original: str | None = None
    content_normalized: str | None = None


class ReviewRecord(BaseModel):
    review_id: str
    product_id: str
    rating: int | None = None
    review_text: str
    language_hint: str | None = None
    is_empty: bool = False


class ProductEvidencePackage(BaseModel):
    product_id: str
    category_slug: str
    product_name: str | None = None
    category_text: str | None = None
    model_description: str | None = None
    primary_language: str | None = None
    source_dir: str
    text_blocks: list[TextEvidence] = Field(default_factory=list)
    images: list[ImageEvidence] = Field(default_factory=list)
    reviews: list[ReviewRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CategoryOverview(BaseModel):
    category: str
    product_count: int
    products_with_product_json: int
    products_with_reviews_json: int
    total_reviews: int
    total_images: int


class DatasetOverview(BaseModel):
    dataset_root: str
    category_count: int
    total_products: int
    total_reviews: int
    total_images: int
    categories: list[CategoryOverview]
    warnings: list[str] = Field(default_factory=list)


class DatasetNormalizeRequest(BaseModel):
    categories: list[str] | None = None
    product_ids: list[str] | None = None
    max_products: int | None = Field(default=None, ge=1)
    persist_artifacts: bool = True
    use_llm: bool = True


class NormalizationStats(BaseModel):
    scanned_products: int = 0
    normalized_products: int = 0
    total_reviews: int = 0
    total_images: int = 0
    products_missing_product_json: int = 0
    products_missing_reviews_json: int = 0
    empty_reviews: int = 0


class DatasetNormalizationResult(BaseModel):
    stats: NormalizationStats
    normalized_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    report_path: str | None = None


class ProductDirectory(BaseModel):
    category_slug: str
    product_dir: Path
    product_id: str