from pathlib import Path
from typing import Any

import orjson

from decathlon_voc_analyzer.app.core.config import get_settings


class ArtifactSidecarService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def load_feedback_payload(self, product_id: str, category_slug: str | None) -> dict[str, Any] | None:
        feedback_path = self._feedback_path(product_id=product_id, category_slug=category_slug)
        if not feedback_path.exists():
            return None
        payload = orjson.loads(feedback_path.read_bytes())
        if not isinstance(payload, dict):
            return None
        payload["feedback_path"] = str(feedback_path)
        return payload

    def load_replay_payload(self, product_id: str, category_slug: str | None) -> dict[str, Any] | None:
        replay_path = self._replay_path(product_id=product_id, category_slug=category_slug)
        if not replay_path.exists():
            return None
        payload = orjson.loads(replay_path.read_bytes())
        if not isinstance(payload, dict):
            return None
        payload["replay_path"] = str(replay_path)
        return payload

    def persist_sidecars(
        self,
        product_id: str,
        category_slug: str | None,
        analysis_mode: str,
        report,
        trace,
        retrieval_quality,
        warnings: list[str],
    ) -> dict[str, str]:
        category = category_slug or "adhoc"
        feedback_dir = self.settings.feedback_output_dir / category
        replay_dir = self.settings.replay_output_dir / category
        feedback_dir.mkdir(parents=True, exist_ok=True)
        replay_dir.mkdir(parents=True, exist_ok=True)

        feedback_path = feedback_dir / f"{product_id}_feedback_slots.json"
        replay_path = self._replay_path(product_id=product_id, category_slug=category_slug)
        existing_feedback_payload = self.load_feedback_payload(product_id=product_id, category_slug=category_slug)
        existing_feedback_slots = (existing_feedback_payload or {}).get("slots") or []

        feedback_payload = {
            "product_id": product_id,
            "category_slug": category_slug,
            "analysis_mode": analysis_mode,
            "slots": self._merge_feedback_slots(
                existing_slots=existing_feedback_slots,
                new_slots=self._build_feedback_slots(report, retrieval_quality),
            ),
            "warnings": warnings,
        }
        replay_payload = {
            "product_id": product_id,
            "category_slug": category_slug,
            "analysis_mode": analysis_mode,
            "report": report.model_dump(mode="json"),
            "trace": [item.model_dump(mode="json") for item in trace],
            "retrieval_quality": [item.model_dump(mode="json") for item in retrieval_quality],
            "warnings": warnings,
        }
        feedback_path.write_bytes(orjson.dumps(feedback_payload, option=orjson.OPT_INDENT_2))
        replay_path.write_bytes(orjson.dumps(replay_payload, option=orjson.OPT_INDENT_2))
        return {
            "feedback_path": str(feedback_path),
            "replay_path": str(replay_path),
        }

    def _replay_path(self, product_id: str, category_slug: str | None) -> Path:
        category = category_slug or "adhoc"
        return self.settings.replay_output_dir / category / f"{product_id}_replay.json"

    def _feedback_path(self, product_id: str, category_slug: str | None) -> Path:
        category = category_slug or "adhoc"
        return self.settings.feedback_output_dir / category / f"{product_id}_feedback_slots.json"

    def _merge_feedback_slots(
        self,
        existing_slots: list[dict[str, object]],
        new_slots: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        existing_by_key = {
            self._feedback_slot_key(slot): slot
            for slot in existing_slots
            if isinstance(slot, dict)
        }
        existing_by_slot_id = {
            str(slot.get("slot_id")): slot
            for slot in existing_slots
            if isinstance(slot, dict) and slot.get("slot_id")
        }
        merged: list[dict[str, object]] = []
        for slot in new_slots:
            previous = None
            slot_id = slot.get("slot_id")
            if slot_id is not None:
                previous = existing_by_slot_id.get(str(slot_id))
            if previous is None:
                key = self._feedback_slot_key(slot)
                previous = existing_by_key.get(key)
            if previous is None:
                merged.append(slot)
                continue
            merged.append(
                {
                    **slot,
                    "status": previous.get("status") or slot.get("status") or "pending_review",
                    "reviewer_note": previous.get("reviewer_note"),
                }
            )
        return merged

    def _feedback_slot_key(self, slot: dict[str, object]) -> tuple[str, str]:
        return (str(slot.get("item_type") or "unknown"), str(slot.get("label") or ""))

    def _build_feedback_slots(self, report, retrieval_quality) -> list[dict[str, object]]:
        slots: list[dict[str, object]] = []
        items = report.weaknesses + report.controversies
        for index, item in enumerate(items, start=1):
            slots.append(
                {
                    "slot_id": f"issue_{index:02d}",
                    "item_type": "insight",
                    "label": item.label,
                    "summary": item.summary,
                    "owner": item.owner,
                    "status": "pending_review",
                    "confidence_breakdown": item.confidence_breakdown.model_dump(mode="json") if item.confidence_breakdown else None,
                    "reviewer_note": None,
                }
            )
        for index, item in enumerate(report.suggestions, start=1):
            slots.append(
                {
                    "slot_id": f"suggestion_{index:02d}",
                    "item_type": "suggestion",
                    "label": item.suggestion,
                    "summary": "; ".join(item.reason),
                    "owner": item.owner,
                    "status": "pending_review",
                    "confidence_breakdown": item.confidence_breakdown.model_dump(mode="json") if item.confidence_breakdown else None,
                    "reviewer_note": None,
                }
            )
        for index, item in enumerate(retrieval_quality, start=1):
            slots.append(
                {
                    "slot_id": f"retrieval_{index:02d}",
                    "item_type": "retrieval_quality",
                    "label": item.source_aspect,
                    "summary": f"coverage={item.evidence_coverage:.2f}, drift={item.score_drift:.2f}, conflict={item.conflict_risk:.2f}",
                    "owner": "evidence_gap" if item.conflict_risk >= 0.6 else "product_issue",
                    "status": "pending_review",
                    "confidence_breakdown": None,
                    "reviewer_note": None,
                }
            )
        return slots