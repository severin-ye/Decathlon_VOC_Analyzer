import hashlib
import json

from openai import OpenAI

from decathlon_voc_analyzer.core.config import get_settings
from decathlon_voc_analyzer.models.analysis import RetrievalQuestion
from decathlon_voc_analyzer.models.review import ReviewAspect
from decathlon_voc_analyzer.prompts import build_question_generation_user_prompt, get_prompt


class QuestionGenerationService:
    def __init__(self) -> None:
        self.settings = get_settings()

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
        client = OpenAI(api_key=self.settings.qwen_plus_api_key, base_url=self.settings.qwen_base_url)
        payload = {
            "aspect": aspect.aspect,
            "opinion": aspect.opinion,
            "evidence_span": aspect.evidence_span,
            "usage_scene": aspect.usage_scene,
            "sentiment": aspect.sentiment,
            "questions_per_aspect": questions_per_aspect,
        }
        response = client.chat.completions.create(
            model=self.settings.qwen_plus_model,
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": get_prompt("question_generation_system")},
                {"role": "user", "content": build_question_generation_user_prompt(payload)},
            ],
        )
        content = response.choices[0].message.content or "{\"questions\": []}"
        parsed = json.loads(content)
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