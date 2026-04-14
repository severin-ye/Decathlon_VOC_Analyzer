from decathlon_voc_analyzer.schemas.review import ReviewAspect


class ReviewDeduplicationService:
    def deduplicate(self, aspects: list[ReviewAspect]) -> list[ReviewAspect]:
        deduplicated: list[ReviewAspect] = []
        seen_keys: set[tuple[str, str, str, str]] = set()
        for aspect in aspects:
            key = (
                aspect.review_id,
                aspect.aspect.strip().lower(),
                aspect.sentiment,
                self._normalize_text(aspect.evidence_span),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduplicated.append(aspect)
        return deduplicated

    def _normalize_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())