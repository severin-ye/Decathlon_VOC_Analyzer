import re

from decathlon_voc_analyzer.prompts import get_prompt_variant
from decathlon_voc_analyzer.schemas.analysis import ImprovementSuggestion, InsightItem, ProductAnalysisReport, SupportingEvidence


class ReportRefinementService:
    def refine(self, report: ProductAnalysisReport) -> ProductAnalysisReport:
        strengths = self._deduplicate_insights(report.strengths)
        weaknesses = self._deduplicate_insights(report.weaknesses)
        controversies = self._deduplicate_insights(report.controversies)
        suggestions = self._deduplicate_suggestions(report.suggestions)

        strengths = [self._calibrate_insight_summary(self._classify_insight_owner(item, kind="strength"), kind="strength") for item in strengths]
        weaknesses = [self._calibrate_insight_summary(self._classify_insight_owner(item, kind="weakness"), kind="weakness") for item in weaknesses]
        controversies = [self._classify_insight_owner(item, kind="controversy") for item in controversies]
        controversies = [item for item in controversies if not self._looks_like_relation_controversy(item)]
        controversies = [self._calibrate_insight_summary(item, kind="controversy") for item in controversies]
        suggestions = [self._calibrate_suggestion(self._classify_suggestion_owner(item)) for item in suggestions]

        supporting_review_evidence = self._merge_review_evidence(
            [item.supporting_evidence for item in strengths + weaknesses + controversies + suggestions]
        )
        supporting_product_evidence = self._merge_product_evidence(
            [item.supporting_evidence for item in strengths + weaknesses + controversies + suggestions]
        )

        return report.model_copy(
            update={
                "strengths": strengths,
                "weaknesses": weaknesses,
                "controversies": controversies,
                "suggestions": suggestions,
                "supporting_review_evidence": supporting_review_evidence,
                "supporting_product_evidence": supporting_product_evidence,
            }
        )

    def _uses_main_prompt_variant(self) -> bool:
        return get_prompt_variant() == "main"

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
                evidence_level = "review_only"
            elif has_text != has_image:
                owner = "content_presentation"
                evidence_level = "partial_product_support"
            else:
                owner = "product_issue"
                evidence_level = "product_supported"
        else:
            if not has_text and not has_image:
                owner = "product_issue"
                evidence_level = "review_only"
            elif has_text != has_image:
                owner = "content_presentation"
                evidence_level = "partial_product_support"
            elif kind == "controversy":
                owner = "expectation_mismatch"
                evidence_level = "product_supported"
            else:
                owner = "product_issue"
                evidence_level = "product_supported"
        return item.model_copy(update={"owner": owner, "evidence_level": evidence_level})

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
        return item.model_copy(update={"owner": owner, "confidence": min(item.confidence, 0.9)})

    def _calibrate_insight_summary(self, item: InsightItem, kind: str) -> InsightItem:
        evidence = item.supporting_evidence
        has_text = bool(evidence.product_text_block_ids)
        has_image = bool(evidence.product_image_ids)
        summary = item.summary or ""
        if has_text and has_image:
            return item

        lower_summary = summary.lower()
        mentions_text = any(token in lower_summary for token in ("product page", "product-page", "text evidence", "specification", "specifications", "copy"))
        mentions_image = any(token in lower_summary for token in ("image", "images", "imagery", "visual", "visually", "photo", "photos"))
        mentions_corroboration = any(token in lower_summary for token in ("corroborated", "confirmed", "supported", "validated", "verification"))

        should_rewrite = not has_text and not has_image
        should_rewrite = should_rewrite or (not has_image and mentions_image) or (not has_text and mentions_text)
        should_rewrite = should_rewrite or (mentions_corroboration and not (has_text and has_image))
        if not should_rewrite:
            return item

        label = item.label
        if self._uses_main_prompt_variant():
            if kind == "strength":
                if has_text and not has_image:
                    summary = f"Positive feedback on {label} is only partially supported by product-page text; no reliable image evidence was retrieved."
                elif has_image and not has_text:
                    summary = f"Positive feedback on {label} is only partially supported by product images; no confirming product-page text was retrieved."
                else:
                    summary = f"Positive feedback on {label} comes from user reviews, but no direct product-page text or reliable image evidence was retrieved."
            elif kind == "weakness":
                if has_text and not has_image:
                    summary = f"Concerns about {label} are clear in user reviews, and product-page text offers partial context, but no confirming image evidence was retrieved."
                elif has_image and not has_text:
                    summary = f"Concerns about {label} are clear in user reviews, and product images offer partial context, but no confirming product-page text was retrieved."
                else:
                    summary = f"Concerns about {label} are clear in user reviews, but retrieval did not find direct product-page text or image evidence to independently corroborate them."
            else:
                if has_text and not has_image:
                    summary = f"The mixed signal around {label} is only partially grounded by product-page text; no reliable image evidence was retrieved."
                elif has_image and not has_text:
                    summary = f"The mixed signal around {label} is only partially grounded by product images; no confirming product-page text was retrieved."
                else:
                    summary = f"Current evidence is insufficient to confirm or refute the mixed feedback around {label}; the signal mainly comes from user reviews."
        else:
            if kind == "strength":
                if has_text and not has_image:
                    summary = f"关于 {label} 的正向反馈仅获得了部分商品页文本支持，暂未检索到可靠的图像证据。"
                elif has_image and not has_text:
                    summary = f"关于 {label} 的正向反馈仅获得了部分商品图片支持，暂未检索到对应的商品页文本证据。"
                else:
                    summary = f"关于 {label} 的正向反馈主要来自用户评论，暂未检索到直接的商品页文本或可靠图像证据。"
            elif kind == "weakness":
                if has_text and not has_image:
                    summary = f"关于 {label} 的负向反馈在用户评论中较明确，商品页文本只能提供部分背景，暂未检索到可确认的图像证据。"
                elif has_image and not has_text:
                    summary = f"关于 {label} 的负向反馈在用户评论中较明确，商品图片只能提供部分背景，暂未检索到可确认的商品页文本证据。"
                else:
                    summary = f"关于 {label} 的负向反馈在用户评论中较明确，但当前检索未找到可独立佐证的商品页文本或图像证据。"
            else:
                if has_text and not has_image:
                    summary = f"围绕 {label} 的混合反馈仅获得了部分商品页文本支撑，暂未检索到可靠的图像证据。"
                elif has_image and not has_text:
                    summary = f"围绕 {label} 的混合反馈仅获得了部分商品图片支撑，暂未检索到对应的商品页文本证据。"
                else:
                    summary = f"当前证据不足以确认或反驳 {label} 的混合反馈，现有信号主要来自用户评论。"
        return item.model_copy(update={"summary": summary})

    def _looks_like_relation_controversy(self, item: InsightItem) -> bool:
        text = f"{item.label} {item.summary}".lower()
        relation_markers = (" vs ", "vs.", "versus", "linked to", "link to", "drives", "drive", "causal", "root cause", "co-occurrence", "co-occurs")
        return any(marker in text for marker in relation_markers)

    def _calibrate_suggestion(self, item: ImprovementSuggestion) -> ImprovementSuggestion:
        text = " ".join([item.suggestion] + item.reason).lower()
        if any(token in text for token in ("comfort", "fit", "nose-pad", "nose pad", "temple-tip", "hinge flexibility", "pressure-distribution", "silicone-grip", "silicone grip")):
            suggestion = (
                "Clarify the fit and comfort-related design cues on the product page, and add close-up visuals of the features that help users judge wear comfort."
                if self._uses_main_prompt_variant()
                else "在商品页中补充佩戴贴合度与舒适性相关设计说明，并增加帮助用户判断佩戴舒适性的局部特写。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="comfort")})

        if any(token in text for token in ("optical-grade polycarbonate", "ab-rated", "ab rated", "brown for contrast", "gray for true color", "grey for true color")):
            suggestion = (
                "Add product-page optical verification notes and publish the measured distortion or prism-control results before making strong visual-performance claims."
                if self._uses_main_prompt_variant()
                else "补充商品页中的光学核验说明，并在作出强视觉性能表述前公开实际的畸变或棱镜控制测试结果。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="optical")})

        if any(token in text for token in ("price", "msrp", "discount", "value")):
            suggestion = (
                "State the current selling price and any active discount or list-price reference directly in the primary product metadata so the value claim can be checked quickly."
                if self._uses_main_prompt_variant()
                else "在商品主信息中直接标明当前售价，以及任何生效中的折扣或划线价参考，方便用户快速核验价值表述。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="price")})

        if any(token in text for token in ("tint", "tinting", "hue", "gradient", "mirrored", "uniformity", "lens color")):
            suggestion = (
                "State the exact lens tint in the primary product copy and include a clear front-facing lens image so the tint claim can be checked visually."
                if self._uses_main_prompt_variant()
                else "在商品主文案中明确标注镜片色调，并提供清晰的正面镜片图片，方便用户直观核验染色相关表述。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="tint")})

        if any(token in text for token in ("durability", "rubber", "insert", "warranty", "2-year", "2 year", "2+ years", "daily wear")):
            suggestion = (
                "Add durability-validation notes and warranty scope for the rubber ear insert, and describe the actual material and test scope without claiming unsupported lifetime thresholds."
                if self._uses_main_prompt_variant()
                else "补充橡胶耳托的耐久性核验说明与保修范围，并说明实际材料与测试范围，不要给出缺乏证据支撑的寿命阈值。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="durability")})

        if any(token in text for token in ("optical", "distortion", "magnification", "lens", "prism", "visual")) and any(token in text for token in ("third-party", "certified", "compliance", "ansi", "iso")):
            suggestion = (
                "Add product-page optical verification notes and publish the measured distortion or prism-control results before making strong visual-performance claims."
                if self._uses_main_prompt_variant()
                else "补充商品页中的光学核验说明，并在作出强视觉性能表述前公开实际的畸变或棱镜控制测试结果。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="optical")})

        if not any(token in text for token in ("iso", "ansi", "astm", "z80", "4892", "diopter", "prism deviation", "2000-hour", "2000 hour", "12-24 month", "12–24 month")):
            return item
        if any(token in text for token in ("optical", "distortion", "magnification", "lens", "prism", "visual")):
            suggestion = (
                "Add product-page optical verification notes and publish the measured distortion or prism-control results before making strong visual-performance claims."
                if self._uses_main_prompt_variant()
                else "补充商品页中的光学核验说明，并在作出强视觉性能表述前公开实际的畸变或棱镜控制测试结果。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="optical")})
        elif any(token in text for token in ("durability", "rubber", "insert", "aging", "uv", "elastomer")):
            suggestion = (
                "Add durability-validation notes for the rubber components and publish the actual test scope, duration, and pass/fail criteria instead of generic quality claims."
                if self._uses_main_prompt_variant()
                else "补充橡胶部件的耐久性核验说明，并公开实际测试范围、时长与通过标准，而不是只给出泛化质量表述。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="durability")})
        else:
            suggestion = (
                "Replace unsupported external-standard references with a simpler, evidence-grounded explanation of what was tested and what the current product-page evidence can confirm."
                if self._uses_main_prompt_variant()
                else "将缺乏证据支撑的外部标准表述改为更简单、基于当前证据的测试说明，明确现有商品页证据究竟能确认什么。"
            )
            return item.model_copy(update={"suggestion": suggestion, "reason": self._sanitize_suggestion_reasons(item.reason, category="generic")})

    def _sanitize_suggestion_reasons(self, reasons: list[str], category: str) -> list[str]:
        sanitized: list[str] = []
        for reason in reasons:
            lower_reason = reason.lower()
            if any(token in lower_reason for token in ("optical-grade polycarbonate", "ab-rated", "ab rated", "brown for contrast", "gray for true color", "grey for true color", "ansi", "iso", "astm", "z80", "third-party", "compliance")):
                if self._uses_main_prompt_variant():
                    if category == "optical":
                        sanitized.append("No product-page claims or test data about optical clarity, distortion control, non-prescription status, or measured visual performance were retrieved.")
                    elif category == "price":
                        sanitized.append("No on-page pricing context or value anchor was retrieved to substantiate the price claim.")
                    elif category == "durability":
                        sanitized.append("No product-page durability note, warranty scope, or material-validation detail was retrieved for this component.")
                    elif category == "comfort":
                        sanitized.append("No product-page fit details, frame-weight information, or comfort-related design cues were retrieved.")
                    elif category == "tint":
                        sanitized.append("Current product-page evidence does not clearly specify the lens tint or provide enough visual context to verify the tint claim.")
                    else:
                        sanitized.append("Current product-page evidence does not provide the validation detail needed to support this claim.")
                else:
                    if category == "optical":
                        sanitized.append("当前商品页未检索到关于光学清晰度、畸变控制、非处方属性或可量化视觉表现的说明。")
                    elif category == "price":
                        sanitized.append("当前页面未检索到可支撑价格判断的定价上下文或价值锚点。")
                    elif category == "durability":
                        sanitized.append("当前未检索到该部件的耐久性说明、保修范围或材料核验细节。")
                    elif category == "comfort":
                        sanitized.append("当前未检索到关于贴合度、重量或舒适性设计线索的商品页说明。")
                    elif category == "tint":
                        sanitized.append("当前商品页未明确标注镜片色调，也缺少足够的视觉线索来核验染色相关表述。")
                    else:
                        sanitized.append("当前商品页证据不足以提供支撑该判断所需的核验细节。")
            elif category == "tint" and any(token in lower_reason for token in ("gray-green", "grey-green", "uniform non-gradient", "full-surface uniform tint", "color fidelity", "contrast suitability")):
                if self._uses_main_prompt_variant():
                    sanitized.append("Current product-page evidence does not clearly specify the lens tint or provide enough visual context to verify the tint claim.")
                else:
                    sanitized.append("当前商品页未明确标注镜片色调，也缺少足够的视觉线索来核验染色相关表述。")
            elif category == "durability" and any(token in lower_reason for token in ("confirm zero mention", "confirms zero mention", "all examined text blocks", "all examined image regions")):
                if self._uses_main_prompt_variant():
                    sanitized.append("Retrieval did not identify valid material, reinforcement, or warranty evidence in the examined text blocks or image regions.")
                else:
                    sanitized.append("在已检查的文本块和图像区域中，检索未识别到有效的材料、强化结构或保修信息。")
            else:
                sanitized.append(reason)
        return sanitized

    def _merge_review_evidence(self, evidences: list[SupportingEvidence]) -> SupportingEvidence:
        return SupportingEvidence(
            review_ids=list(dict.fromkeys(review_id for evidence in evidences for review_id in evidence.review_ids))[:10],
            product_text_block_ids=[],
            product_image_ids=[],
        )

    def _merge_product_evidence(self, evidences: list[SupportingEvidence]) -> SupportingEvidence:
        return SupportingEvidence(
            review_ids=[],
            product_text_block_ids=list(dict.fromkeys(text_id for evidence in evidences for text_id in evidence.product_text_block_ids))[:10],
            product_image_ids=list(dict.fromkeys(image_id for evidence in evidences for image_id in evidence.product_image_ids))[:10],
        )

    def _compact(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())