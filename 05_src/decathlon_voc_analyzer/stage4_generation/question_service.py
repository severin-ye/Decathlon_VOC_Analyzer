import hashlib
import re

from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.analysis import QuestionIntent, RetrievalQuestion
from decathlon_voc_analyzer.schemas.review import ReviewAspect
from decathlon_voc_analyzer.prompts import get_prompt_template, get_prompt_variant
from decathlon_voc_analyzer.runtime_progress import get_workflow_progress


class QuestionGenerationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.chat_gateway = QwenChatGateway()

    def generate_questions(
        self,
        aspects: list[ReviewAspect],
        questions_per_aspect: int = 2,
        use_llm: bool = True,
    ) -> tuple[list[QuestionIntent], list[RetrievalQuestion], list[str], str]:
        progress = get_workflow_progress()
        progress.start_count_step("analyze", "questions", total=len(aspects), detail=f"规划 {len(aspects)} 个方面的问题")
        intents = self.plan_question_intents(aspects, questions_per_aspect)
        questions: list[RetrievalQuestion] = []
        warnings: list[str] = []
        llm_requested = use_llm and bool(self.settings.qwen_plus_api_key)
        mode = "llm" if llm_requested else "heuristic"

        for aspect in aspects:
            if llm_requested:
                try:
                    generated = self._generate_with_llm(aspect, questions_per_aspect)
                except Exception as exc:
                    mode = "heuristic"
                    warnings.append(f"{aspect.aspect_id}: question generation failed, fallback to heuristic ({exc})")
                    generated = self._generate_with_heuristic(aspect, questions_per_aspect)
            else:
                generated = self._generate_with_heuristic(aspect, questions_per_aspect)
            questions.extend(generated)
            progress.advance_step("analyze", "questions", detail=aspect.aspect)

        progress.complete_step("analyze", "questions")
        return intents, questions, warnings, mode

    def plan_question_intents(
        self,
        aspects: list[ReviewAspect],
        questions_per_aspect: int,
    ) -> list[QuestionIntent]:
        intents: list[QuestionIntent] = []
        for aspect in aspects:
            intents.extend(self._build_intents_for_aspect(aspect, questions_per_aspect))
        return intents

    def _generate_with_llm(self, aspect: ReviewAspect, questions_per_aspect: int) -> list[RetrievalQuestion]:
        intents = self._build_intents_for_aspect(aspect, questions_per_aspect)
        questions: list[RetrievalQuestion] = []
        for index, intent in enumerate(intents, start=1):
            payload = {
                "aspect": aspect.aspect,
                "opinion": aspect.opinion,
                "evidence_span": aspect.evidence_span,
                "usage_scene": aspect.usage_scene,
                "sentiment": aspect.sentiment,
                "intent_type": intent.intent_type,
                "expected_evidence_routes": intent.expected_evidence_routes,
                "forbidden_concepts": intent.forbidden_concepts,
                "specificity_bound": intent.specificity_bound,
                "questions_per_aspect": 1,
            }
            parsed = self.chat_gateway.invoke_json(
                prompt_template=get_prompt_template("question_generation_system"),
                variables={"payload": payload},
            )
            raw_questions = parsed.get("questions") or []
            item = raw_questions[0] if raw_questions else {}
            if not isinstance(item, dict):
                item = {}
            question, rationale, routes = self._validate_question_candidate(
                aspect=aspect,
                intent=intent,
                question=str(item.get("question") or ""),
                rationale=str(item.get("rationale") or intent.rationale),
                routes=item.get("expected_evidence_routes"),
            )
            questions.append(
                RetrievalQuestion(
                    question_id=f"{aspect.aspect_id}_q_{index:02d}",
                    source_review_id=aspect.review_id,
                    source_aspect=aspect.aspect,
                    source_aspect_id=aspect.aspect_id,
                    question=question,
                    rationale=rationale,
                    expected_evidence_routes=routes,
                    confidence=self._clamp_confidence(item.get("confidence"), 0.78),
                )
            )
        questions = self._deduplicate_questions(aspect, questions, questions_per_aspect)
        return questions or self._generate_with_heuristic(aspect, questions_per_aspect)

    def _generate_with_heuristic(self, aspect: ReviewAspect, questions_per_aspect: int) -> list[RetrievalQuestion]:
        intents = self._build_intents_for_aspect(aspect, questions_per_aspect)
        questions: list[RetrievalQuestion] = []
        for index, intent in enumerate(intents, start=1):
            question, rationale, routes = self._heuristic_candidate_for_intent(aspect, intent)
            question, rationale, routes = self._validate_question_candidate(
                aspect=aspect,
                intent=intent,
                question=question,
                rationale=rationale,
                routes=routes,
            )
            questions.append(
                RetrievalQuestion(
                    question_id=f"{aspect.aspect_id}_q_{index:02d}",
                    source_review_id=aspect.review_id,
                    source_aspect=aspect.aspect,
                    source_aspect_id=aspect.aspect_id,
                    question=question,
                    rationale=rationale,
                    expected_evidence_routes=routes,
                    confidence=0.66 if len(routes) == 1 else 0.72,
                )
            )
        return questions

    def _build_intents_for_aspect(self, aspect: ReviewAspect, questions_per_aspect: int) -> list[QuestionIntent]:
        intent_specs = [
            ("explicit_support", ["text"], self._intent_rationale(aspect, "explicit_support")),
            ("visual_confirmation", ["image"], self._intent_rationale(aspect, "visual_confirmation")),
            ("cross_modal_resolution", ["text", "image"], self._intent_rationale(aspect, "cross_modal_resolution")),
            ("spec_check", ["text"], self._intent_rationale(aspect, "spec_check")),
            ("visual_detail", ["image"], self._intent_rationale(aspect, "visual_detail")),
        ]
        intents: list[QuestionIntent] = []
        for index, (intent_type, routes, rationale) in enumerate(intent_specs[:questions_per_aspect], start=1):
            intent = QuestionIntent(
                intent_id=f"{aspect.aspect_id}_intent_{index:02d}",
                source_review_id=aspect.review_id,
                source_aspect=aspect.aspect,
                source_aspect_id=aspect.aspect_id,
                intent_type=intent_type,
                rationale=rationale,
                expected_evidence_routes=routes,
                forbidden_concepts=self._forbidden_concepts_for_aspect(aspect.aspect),
                specificity_bound=self._specificity_bound_for_aspect(),
            )
            intents.append(self._validate_question_intent(intent))
        return intents

    def _intent_rationale(self, aspect: ReviewAspect, intent_type: str) -> str:
        if get_prompt_variant() == "main":
            templates = {
                "explicit_support": f"Check whether product-page text directly substantiates the review claim about '{aspect.aspect}'.",
                "visual_confirmation": f"Check whether product images provide concrete visual evidence for '{aspect.aspect}'.",
                "cross_modal_resolution": f"Combine text and image evidence to interpret whether '{aspect.aspect}' reflects a real product issue or an expectation mismatch.",
                "spec_check": f"Look for measurable specifications, warranty scope, or explicit claims tied to '{aspect.aspect}'.",
                "visual_detail": f"Look for close-up structural cues in product imagery that relate to '{aspect.aspect}'.",
            }
        else:
            templates = {
                "explicit_support": f"确认商品页文本是否直接支撑“{aspect.aspect}”相关评论观点。",
                "visual_confirmation": f"确认商品图片是否提供与“{aspect.aspect}”相关的具体视觉证据。",
                "cross_modal_resolution": f"结合图文证据判断“{aspect.aspect}”更像真实商品问题还是预期偏差。",
                "spec_check": f"优先查找与“{aspect.aspect}”相关的规格、保修范围或明确声明。",
                "visual_detail": f"优先查找商品局部特写里与“{aspect.aspect}”相关的结构细节。",
            }
        return templates[intent_type]

    def _validate_question_intent(self, intent: QuestionIntent) -> QuestionIntent:
        routes = [route for route in intent.expected_evidence_routes if route in {"text", "image"}]
        if not routes:
            routes = ["text"]
        forbidden = [item.strip() for item in intent.forbidden_concepts if item and item.strip()]
        return intent.model_copy(
            update={
                "expected_evidence_routes": list(dict.fromkeys(routes)),
                "forbidden_concepts": list(dict.fromkeys(forbidden)),
            }
        )

    def _heuristic_candidate_for_intent(
        self,
        aspect: ReviewAspect,
        intent: QuestionIntent,
    ) -> tuple[str, str, list[str]]:
        if get_prompt_variant() == "main":
            templates = {
                "explicit_support": (
                    f"Does the product text explicitly support the experience claim related to '{aspect.aspect}'?",
                    "This checks whether the product page text directly supports the review claim.",
                    ["text"],
                ),
                "visual_confirmation": (
                    f"Do the product images provide structural or visual evidence for the '{aspect.aspect}' judgment?",
                    "This checks whether visual evidence supports the experience described in the review.",
                    ["image"],
                ),
                "cross_modal_resolution": (
                    f"For '{aspect.aspect}', do the product text and images support a real product issue or an expectation mismatch?",
                    "This requires combining textual and visual evidence before interpreting the feedback.",
                    ["text", "image"],
                ),
                "spec_check": (
                    f"Which product-page specifications, warranty notes, or explicit claims are relevant to '{aspect.aspect}'?",
                    "This narrows retrieval toward measurable or explicitly stated evidence.",
                    ["text"],
                ),
                "visual_detail": (
                    f"Do close-up product images reveal structural details that help verify '{aspect.aspect}'?",
                    "This focuses on local visual details that can realistically appear in retail imagery.",
                    ["image"],
                ),
            }
        else:
            templates = {
                "explicit_support": (
                    f"商品文案中是否存在能解释“{aspect.aspect}”相关体验的明确描述？",
                    "需要先确认商品页文本是否直接支持该评论观点。",
                    ["text"],
                ),
                "visual_confirmation": (
                    f"商品图片中是否存在能支撑“{aspect.aspect}”判断的结构或外观证据？",
                    "需要检查视觉证据能否支撑评论中的体验判断。",
                    ["image"],
                ),
                "cross_modal_resolution": (
                    f"围绕“{aspect.aspect}”，商品图文证据更支持真实问题还是使用预期偏差？",
                    "需要综合图像与文本判断该反馈的解释方向。",
                    ["text", "image"],
                ),
                "spec_check": (
                    f"商品页中有哪些规格参数、保修说明或明确声明与“{aspect.aspect}”相关？",
                    "需要把检索收紧到可核验的显式说明。",
                    ["text"],
                ),
                "visual_detail": (
                    f"商品局部特写中是否存在有助于验证“{aspect.aspect}”的结构细节？",
                    "需要关注零售图片里现实可见的局部视觉线索。",
                    ["image"],
                ),
            }
        return templates[intent.intent_type]

    def _validate_question_candidate(
        self,
        *,
        aspect: ReviewAspect,
        intent: QuestionIntent,
        question: str,
        rationale: str,
        routes: object,
    ) -> tuple[str, str, list[str]]:
        normalized_routes = routes if isinstance(routes, list) else intent.expected_evidence_routes
        normalized_routes = [route for route in normalized_routes if route in {"text", "image"}] or list(intent.expected_evidence_routes)
        if not question.strip():
            question, rationale, normalized_routes = self._heuristic_candidate_for_intent(aspect, intent)
        question, rationale, normalized_routes = self._normalize_generated_question(
            aspect=aspect,
            question=question,
            rationale=rationale,
            routes=normalized_routes,
        )
        lower_question = question.lower()
        if any(token.lower() in lower_question for token in intent.forbidden_concepts):
            question, rationale, normalized_routes = self._heuristic_candidate_for_intent(aspect, intent)
            question, rationale, normalized_routes = self._normalize_generated_question(
                aspect=aspect,
                question=question,
                rationale=rationale,
                routes=normalized_routes,
            )
        return question, rationale, normalized_routes

    def _forbidden_concepts_for_aspect(self, aspect: str) -> list[str]:
        aspect_text = (aspect or "").lower()
        if any(token in aspect_text for token in ("durability", "aging", "rubber", "insert", "material")):
            return [
                "12-24 month",
                "long-term wear",
                "time-lapse",
                "show wear over time",
                "ear cups",
                "stitching",
                "seams",
            ]
        if any(token in aspect_text for token in ("optical", "lens", "distortion", "magnification", "visual")):
            return [
                "demonstration video",
                "diopter",
                "1:1 visual scaling",
                "plano",
                "convex geometry",
            ]
        if "comfort" in aspect_text:
            return ["strap", "ear cup", "memory foam", "breathable mesh", "soft lining"]
        return []

    def _specificity_bound_for_aspect(self) -> str:
        if get_prompt_variant() == "main":
            return "Only ask for evidence that can plausibly appear on a normal retail product page."
        return "只允许请求普通零售商品页现实可能提供的证据。"

    def _deduplicate_questions(
        self,
        aspect: ReviewAspect,
        questions: list[RetrievalQuestion],
        questions_per_aspect: int,
    ) -> list[RetrievalQuestion]:
        deduplicated: list[RetrievalQuestion] = []
        seen: set[str] = set()

        for question in questions:
            key = self._normalize_question_key(question.question)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(question)

        if len(deduplicated) < questions_per_aspect:
            for fallback in self._generate_with_heuristic(aspect, questions_per_aspect):
                key = self._normalize_question_key(fallback.question)
                if key in seen:
                    continue
                seen.add(key)
                deduplicated.append(fallback)
                if len(deduplicated) >= questions_per_aspect:
                    break

        resequenced: list[RetrievalQuestion] = []
        for index, question in enumerate(deduplicated[:questions_per_aspect], start=1):
            resequenced.append(
                question.model_copy(update={"question_id": f"{aspect.aspect_id}_q_{index:02d}"})
            )
        return resequenced

    def _normalize_question_key(self, question: str) -> str:
        return " ".join((question or "").strip().lower().split())

    def _normalize_generated_question(
        self,
        aspect: ReviewAspect,
        question: str,
        rationale: str,
        routes: list[str],
    ) -> tuple[str, list[str] | str, list[str]]:
        aspect_text = (aspect.aspect or "").lower()
        question_text = (question or "").lower()
        if self._looks_like_unrealistic_durability_question(aspect_text, question_text):
            if get_prompt_variant() == "main":
                return (
                    "Does the product page provide material specifications, durability-validation notes, warranty terms, or close-up imagery that can realistically support the durability claim for this component?",
                    "Prefer evidence types that a normal product page can actually provide, rather than requiring long-term wear imagery or time-lapse proof.",
                    ["text", "image"],
                )
            return (
                "商品页是否提供了材料规格、耐久性核验说明、保修信息或局部特写图片，以现实地支撑该部件的耐久性判断？",
                "优先使用普通商品页通常能够提供的证据类型，而不是要求长期磨损图片或时间跨度证明。",
                ["text", "image"],
            )
        if any(token in question_text for token in ("rubber insert", "rubber inserts", "earpiece", "earpieces")) and any(token in question_text for token in ("stitching", "stitch", "seam", "seams")):
            if get_prompt_variant() == "main":
                return (
                    "Do close-up product images show the rubber insert's thickness, surface texture, attachment method, or anti-slip structure near the ear?",
                    "Prefer visual cues that realistically apply to a sunglasses rubber insert instead of apparel-style stitching or seam assumptions.",
                    ["image"],
                )
            return (
                "商品局部特写中是否展示了耳侧橡胶件的厚度、表面纹理、连接方式或防滑结构？",
                "优先使用真正适用于太阳镜橡胶部件的视觉线索，而不是服饰类的缝线或接缝假设。",
                ["image"],
            )
        if self._looks_like_unrealistic_optical_question(aspect_text, question_text):
            if get_prompt_variant() == "main":
                return (
                    "Does the product page provide any optical clarity, distortion-free, or non-prescription lens information that can help evaluate the reported magnification effect?",
                    "Prefer ordinary product-page claims or technical notes that could realistically appear on a retail page, rather than highly specialized lens terminology or off-page demonstrations.",
                    ["text"],
                )
            return (
                "商品页是否提供了光学清晰度、无畸变或非处方镜片相关信息，可用于评估用户反馈的轻微放大问题？",
                "优先要求零售商品页现实可能提供的普通光学说明，而不是高度专业的镜片术语或站外演示。",
                ["text"],
            )
        if self._looks_like_unrealistic_comfort_question(aspect_text, question_text):
            if get_prompt_variant() == "main":
                return (
                    "Does the product description list frame weight, nose-pad design, temple-tip material, hinge flexibility, or other fit details that realistically support long-wear comfort?",
                    "Prefer comfort cues that a sunglasses product page can realistically show, rather than cross-category features such as straps or ear cups.",
                    ["text", "image"],
                )
            return (
                "商品描述是否列出了镜框重量、鼻托设计、镜腿末端材质、铰链灵活度等可现实支撑长时间佩戴舒适性的细节？",
                "优先使用墨镜商品页现实可展示的舒适性线索，而不是跨品类的肩带或耳罩等特征。",
                ["text", "image"],
            )
        return question, rationale, routes

    def _looks_like_unrealistic_durability_question(self, aspect_text: str, question_text: str) -> bool:
        if not any(token in aspect_text for token in ("durability", "aging", "rubber", "insert", "strap", "material")):
            return False
        unrealistic_tokens = (
            "12-24 month",
            "12–24 month",
            "long-term wear",
            "after less than two years",
            "time-lapse",
            "showing wear",
            "show wear over time",
            "ear cup",
            "ear cups",
        )
        return any(token in question_text for token in unrealistic_tokens)

    def _looks_like_unrealistic_optical_question(self, aspect_text: str, question_text: str) -> bool:
        if not any(token in aspect_text for token in ("optical", "lens", "distortion", "magnification", "visual")):
            return False
        unrealistic_tokens = (
            "distance to the ground",
            "demonstration video",
            "demonstration videos",
            "walking or outdoor navigation",
            "live demo",
            "real-world demonstration",
            "plano",
            "positive diopter",
            "diopter value",
            "1:1 optical accuracy",
            "1:1 visual scaling",
            "1:1 scale vision",
            "true optical accuracy",
            "zero magnification",
            "true-to-life vision",
            "base curve",
            "front/rear surface profile",
            "lens thickness gradient",
            "convex geometry",
            "optical scaling",
        )
        return any(token in question_text for token in unrealistic_tokens)

    def _looks_like_unrealistic_comfort_question(self, aspect_text: str, question_text: str) -> bool:
        if "comfort" not in aspect_text:
            return False
        unrealistic_tokens = (
            "strap",
            "straps",
            "ear cup",
            "ear cups",
            "soft lining",
            "soft fabric",
            "cushioned",
            "memory foam",
            "breathable fabric",
            "breathable mesh",
        )
        return any(token in question_text for token in unrealistic_tokens)

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))