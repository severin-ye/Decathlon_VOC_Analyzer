from decathlon_voc_analyzer.schemas.analysis import ImprovementSuggestion, InsightItem, ProductAnalysisReport, SupportingEvidence


class ReportRefinementService:
    def refine(self, report: ProductAnalysisReport) -> ProductAnalysisReport:
        strengths = self._deduplicate_insights(report.strengths)
        weaknesses = self._deduplicate_insights(report.weaknesses)
        controversies = self._deduplicate_insights(report.controversies)
        suggestions = self._deduplicate_suggestions(report.suggestions)

        strengths = [self._classify_insight_owner(item, kind="strength") for item in strengths]
        weaknesses = [self._classify_insight_owner(item, kind="weakness") for item in weaknesses]
        controversies = [self._classify_insight_owner(item, kind="controversy") for item in controversies]
        suggestions = [self._classify_suggestion_owner(item) for item in suggestions]

        supporting_product_evidence = self._merge_supporting_evidence(
            [item.supporting_evidence for item in strengths + weaknesses + controversies + suggestions]
        )

        return report.model_copy(
            update={
                "strengths": strengths,
                "weaknesses": weaknesses,
                "controversies": controversies,
                "suggestions": suggestions,
                "supporting_product_evidence": supporting_product_evidence,
            }
        )

    def _deduplicate_insights(self, items: list[InsightItem]) -> list[InsightItem]:
        deduplicated: list[InsightItem] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.label.strip().lower(), self._compact(item.summary))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    def _deduplicate_suggestions(self, items: list[ImprovementSuggestion]) -> list[ImprovementSuggestion]:
        deduplicated: list[ImprovementSuggestion] = []
        seen: set[str] = set()
        for item in items:
            key = self._compact(item.suggestion)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    def _classify_insight_owner(self, item: InsightItem, kind: str) -> InsightItem:
        evidence = item.supporting_evidence
        has_text = bool(evidence.product_text_block_ids)
        has_image = bool(evidence.product_image_ids)
        has_review = bool(evidence.review_ids)
        if kind == "strength":
            if not has_text and not has_image:
                owner = "expectation_mismatch" if has_review else "evidence_gap"
            elif has_text != has_image:
                owner = "content_presentation"
            else:
                owner = "product_issue"
        else:
            if not has_text and not has_image:
                owner = "evidence_gap"
            elif has_text != has_image:
                owner = "content_presentation"
            elif kind == "controversy":
                owner = "expectation_mismatch"
            else:
                owner = "product_issue"
        return item.model_copy(update={"owner": owner})

    def _classify_suggestion_owner(self, item: ImprovementSuggestion) -> ImprovementSuggestion:
        evidence = item.supporting_evidence
        has_text = bool(evidence.product_text_block_ids)
        has_image = bool(evidence.product_image_ids)
        if not has_text and not has_image:
            owner = "content_presentation"
        elif item.suggestion_type == "perception":
            owner = "content_presentation"
        elif has_text and has_image:
            owner = "product_issue"
        else:
            owner = "content_presentation"
        return item.model_copy(update={"owner": owner})

    def _merge_supporting_evidence(self, evidences: list[SupportingEvidence]) -> SupportingEvidence:
        return SupportingEvidence(
            review_ids=list(dict.fromkeys(review_id for evidence in evidences for review_id in evidence.review_ids))[:10],
            product_text_block_ids=list(dict.fromkeys(text_id for evidence in evidences for text_id in evidence.product_text_block_ids))[:10],
            product_image_ids=list(dict.fromkeys(image_id for evidence in evidences for image_id in evidence.product_image_ids))[:10],
        )

    def _compact(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())