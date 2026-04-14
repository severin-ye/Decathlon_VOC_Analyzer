from pathlib import Path

import orjson

from decathlon_voc_analyzer.app.core.config import get_settings


class ArtifactSidecarService:
    def __init__(self) -> None:
        self.settings = get_settings()

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
        replay_path = replay_dir / f"{product_id}_replay.json"

        feedback_payload = {
            "product_id": product_id,
            "category_slug": category_slug,
            "analysis_mode": analysis_mode,
            "slots": self._build_feedback_slots(report, retrieval_quality),
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