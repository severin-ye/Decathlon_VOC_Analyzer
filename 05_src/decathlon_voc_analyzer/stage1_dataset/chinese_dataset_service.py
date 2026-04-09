import json
import re
import shutil
from pathlib import Path

from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.prompts import (
    get_prompt_template,
)
from pydantic import BaseModel, Field


class ProductTranslationPayload(BaseModel):
    product_name: str = ""
    model_description: str = ""
    category: str = ""


class ReviewTranslationItem(BaseModel):
    user_id: str | None = None
    rating: int | None = None
    content: str = ""


class ReviewTranslationPayload(BaseModel):
    reviews: list[ReviewTranslationItem] = Field(default_factory=list)


class CleanupPayload(BaseModel):
    text: str = ""


class ChineseDatasetService:
    NEEDS_CLEANUP_PATTERN = re.compile(r"<[^>]+>|[A-Za-z]+")

    def __init__(self) -> None:
        self.settings = get_settings()
        self.chat_gateway = QwenChatGateway()

    def export_single_product_dataset(
        self,
        source_product_dir: Path,
        output_product_dir: Path,
        batch_size: int = 25,
    ) -> dict[str, object]:
        product_payload = json.loads((source_product_dir / "product.json").read_text(encoding="utf-8"))
        reviews_payload = json.loads((source_product_dir / "reviews.json").read_text(encoding="utf-8"))

        translated_product = self._translate_product_payload(product_payload)
        translated_reviews = self._translate_reviews_payload(reviews_payload, batch_size=batch_size)

        output_product_dir.mkdir(parents=True, exist_ok=True)
        images_source = source_product_dir / "images"
        images_target = output_product_dir / "images"
        if images_target.exists():
            shutil.rmtree(images_target)
        shutil.copytree(images_source, images_target)

        output_product = {
            **product_payload,
            "product_name": translated_product["product_name"],
            "model_description": translated_product["model_description"],
            "category": translated_product["category"],
        }
        output_reviews = {
            "product_id": reviews_payload.get("product_id"),
            "reviews": translated_reviews,
        }

        (output_product_dir / "product.json").write_text(
            json.dumps(output_product, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        (output_product_dir / "reviews.json").write_text(
            json.dumps(output_reviews, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        return {
            "product_id": output_product.get("product_id"),
            "output_dir": str(output_product_dir),
            "review_count": len(output_reviews["reviews"]),
            "image_count": sum(
                len(item.get("image_paths") or [])
                for item in output_product.get("variants") or []
                if isinstance(item, dict)
            ),
        }

    def _translate_product_payload(self, product_payload: dict[str, object]) -> dict[str, str]:
        input_payload = {
            "product_id": product_payload.get("product_id"),
            "product_name": product_payload.get("product_name"),
            "model_description": product_payload.get("model_description"),
            "category": product_payload.get("category"),
        }
        parsed = self.chat_gateway.invoke_json(
            prompt_template=get_prompt_template("product_translation_system"),
            variables={"payload": input_payload},
            schema=ProductTranslationPayload,
            temperature=0,
        )
        return {
            "product_name": self._cleanup_text(str(parsed.get("product_name") or input_payload.get("product_name") or "")),
            "model_description": self._cleanup_text(str(parsed.get("model_description") or input_payload.get("model_description") or "")),
            "category": self._cleanup_text(str(parsed.get("category") or input_payload.get("category") or "")),
        }

    def _translate_reviews_payload(self, reviews_payload: dict[str, object], batch_size: int) -> list[dict[str, object]]:
        review_items = reviews_payload.get("reviews") or []
        translated_reviews: list[dict[str, object]] = []
        for start in range(0, len(review_items), batch_size):
            batch = review_items[start:start + batch_size]
            parsed = self.chat_gateway.invoke_json(
                prompt_template=get_prompt_template("review_translation_system"),
                variables={
                    "payload": {
                        "product_id": reviews_payload.get("product_id"),
                        "start_index": start,
                        "reviews": batch,
                    }
                },
                schema=ReviewTranslationPayload,
                temperature=0,
            )
            translated_batch = parsed.get("reviews") or []
            if len(translated_batch) != len(batch):
                raise ValueError(f"translated review batch length mismatch at start={start}")
            normalized_batch: list[dict[str, object]] = []
            for source_item, translated_item in zip(batch, translated_batch, strict=True):
                normalized_batch.append(
                    {
                        "user_id": source_item.get("user_id"),
                        "rating": source_item.get("rating"),
                        "content": self._cleanup_text(str(translated_item.get("content") or source_item.get("content") or "")),
                    }
                )
            translated_reviews.extend(normalized_batch)
        return translated_reviews

    def _cleanup_text(self, text: str) -> str:
        normalized = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").strip()
        if not normalized:
            return normalized
        if not self.NEEDS_CLEANUP_PATTERN.search(normalized):
            return normalized

        cleaned = normalized
        for _ in range(2):
            if not self.NEEDS_CLEANUP_PATTERN.search(cleaned):
                break
            parsed = self.chat_gateway.invoke_json(
                prompt_template=get_prompt_template("review_cleanup_system"),
                variables={"payload": {"text": cleaned}},
                schema=CleanupPayload,
                temperature=0,
            )
            cleaned = str(parsed.get("text") or cleaned).strip()
            cleaned = cleaned.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").strip()
        return cleaned