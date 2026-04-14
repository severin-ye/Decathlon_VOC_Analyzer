import os
import hashlib

from decathlon_voc_analyzer.llm import QwenChatGateway
from decathlon_voc_analyzer.app.core.config import get_settings
from decathlon_voc_analyzer.schemas.analysis import RetrievalQuestion
from decathlon_voc_analyzer.schemas.review import ReviewAspect
from decathlon_voc_analyzer.prompts import get_prompt_template


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
            questions.append(
                RetrievalQuestion(
                    question_id=f"{aspect.aspect_id}_q_{index:02d}",
                    source_review_id=aspect.review_id,
                    source_aspect=aspect.aspect,
                    source_aspect_id=aspect.aspect_id,
                    question=str(item.get("question") or ""),
                    rationale=str(item.get("rationale") or aspect.opinion),
                    expected_evidence_routes=routes or ["text", "image"],
                    confidence=self._clamp_confidence(item.get("confidence"), 0.78),
                )
            )
        return questions or self._generate_with_heuristic(aspect, questions_per_aspect)

    def _generate_with_heuristic(self, aspect: ReviewAspect, questions_per_aspect: int) -> list[RetrievalQuestion]:
        if os.getenv("PROMPT_VARIANT", "main") == "main":
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
                question=question,
                rationale=rationale,
                expected_evidence_routes=routes,
                confidence=0.66 if len(routes) == 1 else 0.72,
            )
            for index, (question, rationale, routes) in enumerate(selected, start=1)
        ]

    def _clamp_confidence(self, value: object, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))