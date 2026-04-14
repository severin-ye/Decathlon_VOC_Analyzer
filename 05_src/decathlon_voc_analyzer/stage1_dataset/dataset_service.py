import os
import hashlib
import json
import re
from pathlib import Path

import orjson
from pydantic import BaseModel

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.prompts import get_prompt_template
from decathlon_voc_analyzer.schemas.dataset import (
    CategoryOverview,
    DatasetNormalizationResult,
    DatasetNormalizeRequest,
    DatasetOverview,
    ImageEvidence,
    NormalizationStats,
    ProductDirectory,
    ProductEvidencePackage,
    ReviewRecord,
    TextEvidence,
)


class ProductProjectionPayload(BaseModel):
    product_name: str = ""
    model_description: str = ""
    category: str = ""


class DatasetService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.chat_gateway = QwenChatGateway()

    def build_overview(self) -> DatasetOverview:
        categories: list[CategoryOverview] = []
        total_products = 0
        total_reviews = 0
        total_images = 0
        warnings: list[str] = []

        for category_dir in self._iter_category_dirs():
            product_dirs = [path for path in category_dir.iterdir() if path.is_dir()]
            product_count = len(product_dirs)
            products_with_product_json = 0
            products_with_reviews_json = 0
            category_reviews = 0
            category_images = 0

            for product_dir in product_dirs:
                product_json = product_dir / "product.json"
                reviews_json = product_dir / "reviews.json"
                image_count = self._count_images(product_dir / "images")
                category_images += image_count

                if product_json.exists():
                    products_with_product_json += 1
                if reviews_json.exists():
                    products_with_reviews_json += 1
                    category_reviews += self._count_reviews(reviews_json)

            if products_with_product_json != product_count:
                warnings.append(
                    f"{category_dir.name}: {product_count - products_with_product_json} products missing product.json"
                )
            if products_with_reviews_json != product_count:
                warnings.append(
                    f"{category_dir.name}: {product_count - products_with_reviews_json} products missing reviews.json"
                )

            categories.append(
                CategoryOverview(
                    category=category_dir.name,
                    product_count=product_count,
                    products_with_product_json=products_with_product_json,
                    products_with_reviews_json=products_with_reviews_json,
                    total_reviews=category_reviews,
                    total_images=category_images,
                )
            )
            total_products += product_count
            total_reviews += category_reviews
            total_images += category_images

        return DatasetOverview(
            dataset_root=str(self.settings.dataset_root),
            category_count=len(categories),
            total_products=total_products,
            total_reviews=total_reviews,
            total_images=total_images,
            categories=sorted(categories, key=lambda item: item.category),
            warnings=warnings,
        )

    def normalize_dataset(self, request: DatasetNormalizeRequest) -> DatasetNormalizationResult:
        stats = NormalizationStats()
        warnings: list[str] = []
        normalized_files: list[str] = []

        product_directories = self._select_product_directories(
            categories=request.categories,
            product_ids=request.product_ids,
            max_products=request.max_products,
        )

        for directory in product_directories:
            stats.scanned_products += 1
            package = self._normalize_product(directory)
            stats.normalized_products += 1
            stats.total_reviews += len(package.reviews)
            stats.total_images += len(package.images)
            stats.empty_reviews += sum(1 for review in package.reviews if review.is_empty)
            stats.products_missing_product_json += int(any(
                warning == "missing product.json" for warning in package.warnings
            ))
            stats.products_missing_reviews_json += int(any(
                warning == "missing reviews.json" for warning in package.warnings
            ))
            warnings.extend(f"{package.product_id}: {warning}" for warning in package.warnings)

            if request.persist_artifacts:
                output_path = self._persist_package(package)
                normalized_files.append(str(output_path))

        report_path: str | None = None
        if request.persist_artifacts:
            report_path = str(self._persist_report(stats, warnings))

        return DatasetNormalizationResult(
            stats=stats,
            normalized_files=normalized_files,
            warnings=warnings,
            report_path=report_path,
        )

    def load_product_package(self, product_id: str, category_slug: str | None = None) -> ProductEvidencePackage:
        directory = self._find_product_directory(product_id=product_id, category_slug=category_slug)
        return self._normalize_product(directory)

    def _iter_category_dirs(self) -> list[Path]:
        if not self.settings.dataset_root.exists():
            return []
        return sorted(path for path in self.settings.dataset_root.iterdir() if path.is_dir())

    def _select_product_directories(
        self,
        categories: list[str] | None,
        product_ids: list[str] | None,
        max_products: int | None,
    ) -> list[ProductDirectory]:
        requested_categories = set(categories or [])
        requested_products = set(product_ids or [])
        directories: list[ProductDirectory] = []

        for category_dir in self._iter_category_dirs():
            if requested_categories and category_dir.name not in requested_categories:
                continue
            for product_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
                product_id = product_dir.name
                if requested_products and product_id not in requested_products:
                    continue
                directories.append(
                    ProductDirectory(
                        category_slug=category_dir.name,
                        product_dir=product_dir,
                        product_id=product_id,
                    )
                )

        if max_products is not None:
            directories = directories[:max_products]
        return directories

    def _find_product_directory(self, product_id: str, category_slug: str | None) -> ProductDirectory:
        categories = [category_slug] if category_slug else None
        for directory in self._select_product_directories(categories=categories, product_ids=[product_id], max_products=1):
            return directory
        raise ValueError(f"Product not found: {product_id}")

    def _normalize_product(self, directory: ProductDirectory) -> ProductEvidencePackage:
        product_json_path = directory.product_dir / "product.json"
        reviews_json_path = directory.product_dir / "reviews.json"
        warnings: list[str] = []

        product_payload: dict[str, object] = {}
        if product_json_path.exists():
            product_payload = self._load_json(product_json_path)
        else:
            warnings.append("missing product.json")

        reviews_payload: dict[str, object] = {}
        if reviews_json_path.exists():
            reviews_payload = self._load_json(reviews_json_path)
        else:
            warnings.append("missing reviews.json")

        product_name = self._clean_text(product_payload.get("product_name"))
        model_description = self._clean_text(product_payload.get("model_description"))
        category_text = self._clean_text(product_payload.get("category"))

        if self._should_project_main_to_english():
            product_name, model_description, category_text = self._project_product_fields_to_english(
                product_name,
                model_description,
                category_text,
            )

        text_blocks = self._build_text_blocks(
            product_id=directory.product_id,
            product_name=product_name,
            model_description=model_description,
            category_text=category_text,
        )
        images = self._build_images(directory.product_id, product_payload)
        reviews = self._build_reviews(directory.product_id, reviews_payload)

        if not images:
            warnings.append("no images discovered")

        return ProductEvidencePackage(
            product_id=directory.product_id,
            category_slug=directory.category_slug,
            product_name=product_name,
            category_text=category_text,
            model_description=model_description,
            source_dir=str(directory.product_dir),
            text_blocks=text_blocks,
            images=images,
            reviews=reviews,
            warnings=warnings,
        )

    def _should_project_main_to_english(self) -> bool:
        return os.getenv("PROMPT_VARIANT", "main") == "main" and bool(self.settings.qwen_plus_api_key)

    def _project_product_fields_to_english(
        self,
        product_name: str | None,
        model_description: str | None,
        category_text: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        payload = {
            "product_name": product_name,
            "model_description": model_description,
            "category": category_text,
        }
        try:
            parsed = self.chat_gateway.invoke_json(
                prompt_template=get_prompt_template("product_translation_system"),
                variables={"payload": payload},
                schema=ProductProjectionPayload,
                temperature=0,
            )
        except Exception:
            return product_name, model_description, category_text

        return (
            self._clean_text(parsed.get("product_name") or product_name),
            self._clean_text(parsed.get("model_description") or model_description),
            self._clean_text(parsed.get("category") or category_text),
        )

    def _build_text_blocks(
        self,
        product_id: str,
        product_name: str | None,
        model_description: str | None,
        category_text: str | None,
    ) -> list[TextEvidence]:
        candidates = [
            ("title", "product_name", product_name),
            ("description", "model_description", model_description),
            ("category", "category", category_text),
        ]
        blocks: list[TextEvidence] = []
        for text_type, source_section, content in candidates:
            if not content:
                continue
            blocks.append(
                TextEvidence(
                    text_block_id=self._make_id(product_id, source_section, content),
                    product_id=product_id,
                    text_type=text_type,
                    source_section=source_section,
                    content=content,
                )
            )
        return blocks

    def _build_images(self, product_id: str, product_payload: dict[str, object]) -> list[ImageEvidence]:
        variants = product_payload.get("variants") or []
        images: list[ImageEvidence] = []
        for variant_payload in variants:
            if not isinstance(variant_payload, dict):
                continue
            variant = str(variant_payload.get("color") or "") or None
            image_paths = variant_payload.get("image_paths") or []
            for image_path in image_paths:
                if not isinstance(image_path, str):
                    continue
                images.append(
                    ImageEvidence(
                        image_id=self._make_id(product_id, variant or "default", image_path),
                        product_id=product_id,
                        variant=variant,
                        image_path=image_path,
                    )
                )
        return images

    def _build_reviews(self, product_id: str, reviews_payload: dict[str, object]) -> list[ReviewRecord]:
        review_items = reviews_payload.get("reviews") or []
        reviews: list[ReviewRecord] = []
        for index, item in enumerate(review_items, start=1):
            if not isinstance(item, dict):
                continue
            raw_text = self._clean_text(item.get("content")) or ""
            reviews.append(
                ReviewRecord(
                    review_id=f"{product_id}_review_{index:04d}",
                    product_id=product_id,
                    rating=self._coerce_int(item.get("rating")),
                    review_text=raw_text,
                    language_hint=self._guess_language(raw_text),
                    is_empty=not bool(raw_text.strip()),
                )
            )
        return reviews

    def _persist_package(self, package: ProductEvidencePackage) -> Path:
        output_dir = self.settings.normalized_output_dir / package.category_slug
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{package.product_id}.json"
        output_path.write_bytes(orjson.dumps(package.model_dump(mode="json"), option=orjson.OPT_INDENT_2))
        return output_path

    def _persist_report(self, stats: NormalizationStats, warnings: list[str]) -> Path:
        report = {
            "stats": stats.model_dump(mode="json"),
            "warnings": warnings,
        }
        report_path = self.settings.reports_output_dir / "dataset_normalization_report.json"
        report_path.write_bytes(orjson.dumps(report, option=orjson.OPT_INDENT_2))
        return report_path

    def _count_reviews(self, reviews_path: Path) -> int:
        payload = self._load_json(reviews_path)
        reviews = payload.get("reviews") or []
        return len(reviews) if isinstance(reviews, list) else 0

    def _count_images(self, images_dir: Path) -> int:
        if not images_dir.exists():
            return 0
        count = 0
        for file_path in images_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                count += 1
        return count

    def _load_json(self, path: Path) -> dict[str, object]:
        with path.open("rb") as handle:
            return json.load(handle)

    def _clean_text(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def _make_id(self, product_id: str, namespace: str, raw_value: str) -> str:
        digest = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()[:12]
        return f"{product_id}_{namespace}_{digest}"

    def _coerce_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def _guess_language(self, text: str) -> str | None:
        if not text:
            return None
        if re.search(r"[ㄱ-ㅎ가-힣]", text):
            return "ko"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[Α-Ωα-ω]", text):
            return "el"
        if re.search(r"[а-яА-Я]", text):
            return "ru"
        return "latin"