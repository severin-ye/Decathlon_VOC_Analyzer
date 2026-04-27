import hashlib
import re

from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.analysis import RetrievalQuestion
from decathlon_voc_analyzer.schemas.review import ReviewAspect
from decathlon_voc_analyzer.prompts import get_prompt_template, get_prompt_variant


class QuestionGenerationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.chat_gateway = QwenChatGateway()

    def generate_questions(
        self,
        aspects: list[ReviewAspect],
        questions_per_aspect: int = 2,
        use_llm: bool = True,
    ) -> tuple[list[RetrievalQuestion], list[str], str]:
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

        return questions, warnings, mode

    def _generate_with_llm(self, aspect: ReviewAspect, questions_per_aspect: int) -> list[RetrievalQuestion]:
        payload = {
            "aspect": aspect.aspect,
            "opinion": aspect.opinion,
            "evidence_span": aspect.evidence_span,
            "usage_scene": aspect.usage_scene,
            "sentiment": aspect.sentiment,
            "questions_per_aspect": questions_per_aspect,
        }
        parsed = self.chat_gateway.invoke_json(
            prompt_template=get_prompt_template("question_generation_system"),
            variables={"payload": payload},
        )
        raw_questions = parsed.get("questions") or []
        questions: list[RetrievalQuestion] = []
        for index, item in enumerate(raw_questions[:questions_per_aspect], start=1):
            if not isinstance(item, dict):
                continue
            routes = item.get("expected_evidence_routes")
            if not isinstance(routes, list) or not routes:
                routes = ["text", "image"]
            routes = [route for route in routes if route in {"text", "image"}]
            question, rationale, routes = self._normalize_generated_question(
                aspect=aspect,
                question=str(item.get("question") or ""),
                rationale=str(item.get("rationale") or aspect.opinion),
                routes=routes or ["text", "image"],
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
        if get_prompt_variant() == "main":
            candidates = [
                (
                    f"Does the product text explicitly support the experience claim related to '{aspect.aspect}'?",
                    "This checks whether the product page text directly supports the review claim.",
                    ["text"],
                ),
                (
                    f"Do the product images provide structural or visual evidence for the '{aspect.aspect}' judgment?",
                    "This checks whether visual evidence supports the experience described in the review.",
                    ["image"],
                ),
                (
                    f"For '{aspect.aspect}', do the product text and images support a real product issue or an expectation mismatch?",
                    "This requires combining textual and visual evidence before interpreting the feedback.",
                    ["text", "image"],
                ),
            ]
        else:
            candidates = [
                (
                    f"商品文案中是否存在能解释“{aspect.aspect}”相关体验的明确描述？",
                    "需要先确认商品页文本是否直接支持该评论观点。",
                    ["text"],
                ),
                (
                    f"商品图片中是否存在能支撑“{aspect.aspect}”判断的结构或外观证据？",
                    "需要检查视觉证据能否支撑评论中的体验判断。",
                    ["image"],
                ),
                (
                    f"围绕“{aspect.aspect}”，商品图文证据更支持真实问题还是使用预期偏差？",
                    "需要综合图像与文本判断该反馈的解释方向。",
                    ["text", "image"],
                ),
            ]
        selected = candidates[:questions_per_aspect]
        return [
            RetrievalQuestion(
                question_id=f"{aspect.aspect_id}_q_{index:02d}",
                source_review_id=aspect.review_id,
                source_aspect=aspect.aspect,
                source_aspect_id=aspect.aspect_id,
                question=self._normalize_generated_question(aspect, question, rationale, routes)[0],
                rationale=self._normalize_generated_question(aspect, question, rationale, routes)[1],
                expected_evidence_routes=self._normalize_generated_question(aspect, question, rationale, routes)[2],
                confidence=0.66 if len(routes) == 1 else 0.72,
            )
            for index, (question, rationale, routes) in enumerate(selected, start=1)
        ]

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
            "cushioned",
            "breathable fabric",
        )
        return any(token in question_text for token in unrealistic_tokens)

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))