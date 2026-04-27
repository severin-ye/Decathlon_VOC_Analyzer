from decathlon_voc_analyzer.prompts import get_prompt_template
from decathlon_voc_analyzer.schemas.review import ReviewAspect
from decathlon_voc_analyzer.stage4_generation.question_service import QuestionGenerationService


def _build_aspect() -> ReviewAspect:
    return ReviewAspect(
        aspect_id="a1",
        review_id="r1",
        product_id="p1",
        aspect="收纳容量",
        sentiment="positive",
        opinion="装得下日常通勤物品",
        evidence_span="It fits all my daily commute items.",
        usage_scene="通勤",
        confidence=0.91,
        extraction_mode="llm",
    )


def test_question_prompt_template_formats_payload() -> None:
    prompt = get_prompt_template("question_generation_system", variant="CN")

    messages = prompt.format_messages(payload={"aspect": "收纳容量"})

    assert len(messages) == 2
    assert "问题生成器" in messages[0].content
    assert "收纳容量" in str(messages[1].content)


def test_question_service_uses_gateway_payload(monkeypatch) -> None:
    service = QuestionGenerationService()
    seen: dict[str, object] = {}

    def fake_invoke_json(*, prompt_template, variables):
        seen["messages"] = prompt_template.format_messages(**variables)
        return {
            "questions": [
                {
                    "question": "商品文案是否明确说明了收纳容量？",
                    "rationale": "需要判断文本证据是否支撑评论观点。",
                    "expected_evidence_routes": ["text"],
                    "confidence": 0.84,
                }
            ]
        }

    monkeypatch.setattr(service.chat_gateway, "invoke_json", fake_invoke_json)

    questions = service._generate_with_llm(_build_aspect(), questions_per_aspect=1)

    assert questions[0].question == "商品文案是否明确说明了收纳容量？"
    assert questions[0].expected_evidence_routes == ["text"]
    assert "收纳容量" in str(seen["messages"][1].content)


def test_question_service_normalizes_prompt_variant_alias_for_heuristic(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")
    service = QuestionGenerationService()

    questions = service._generate_with_heuristic(_build_aspect(), questions_per_aspect=1)

    assert questions[0].question.startswith("Does the product text explicitly support")


def test_question_service_rewrites_unrealistic_durability_question(monkeypatch) -> None:
    service = QuestionGenerationService()
    aspect = _build_aspect().model_copy(update={"aspect": "rubber insert durability"})

    def fake_invoke_json(*, prompt_template, variables):
        return {
            "questions": [
                {
                    "question": "Do the product images show long-term wear on the rubber insert after less than two years of use?",
                    "rationale": "Need time-lapse proof of durability.",
                    "expected_evidence_routes": ["image"],
                    "confidence": 0.84,
                }
            ]
        }

    monkeypatch.setattr(service.chat_gateway, "invoke_json", fake_invoke_json)

    questions = service._generate_with_llm(aspect, questions_per_aspect=1)

    assert "long-term wear" not in questions[0].question.lower()
    assert "material specifications" in questions[0].question.lower()
    assert questions[0].expected_evidence_routes == ["text", "image"]


def test_question_service_rewrites_unrealistic_optical_question(monkeypatch) -> None:
    service = QuestionGenerationService()
    aspect = _build_aspect().model_copy(update={"aspect": "optical accuracy"})

    def fake_invoke_json(*, prompt_template, variables):
        return {
            "questions": [
                {
                    "question": "Do demonstration videos or product images show whether the lenses distort the distance to the ground while walking outdoors?",
                    "rationale": "Need a real-world navigation demonstration.",
                    "expected_evidence_routes": ["image"],
                    "confidence": 0.84,
                }
            ]
        }

    monkeypatch.setattr(service.chat_gateway, "invoke_json", fake_invoke_json)

    questions = service._generate_with_llm(aspect, questions_per_aspect=1)

    assert "demonstration" not in questions[0].question.lower()
    assert "distortion-free" in questions[0].question.lower()
    assert questions[0].expected_evidence_routes == ["text"]


def test_question_service_rewrites_overly_technical_optical_question(monkeypatch) -> None:
    service = QuestionGenerationService()
    aspect = _build_aspect().model_copy(update={"aspect": "optical accuracy"})

    def fake_invoke_json(*, prompt_template, variables):
        return {
            "questions": [
                {
                    "question": "Do close-up product images or official lens diagrams show a plano base curve, a positive diopter value, or any 1:1 visual scaling statement?",
                    "rationale": "Need highly technical lens geometry details.",
                    "expected_evidence_routes": ["image", "text"],
                    "confidence": 0.84,
                }
            ]
        }

    monkeypatch.setattr(service.chat_gateway, "invoke_json", fake_invoke_json)

    questions = service._generate_with_llm(aspect, questions_per_aspect=1)

    assert "plano" not in questions[0].question.lower()
    assert "1:1" not in questions[0].question.lower()
    assert "non-prescription lens information" in questions[0].question.lower()
    assert questions[0].expected_evidence_routes == ["text"]


def test_question_service_deduplicates_normalized_questions(monkeypatch) -> None:
    service = QuestionGenerationService()
    aspect = _build_aspect().model_copy(update={"aspect": "optical accuracy"})

    def fake_invoke_json(*, prompt_template, variables):
        return {
            "questions": [
                {
                    "question": "Does the product page mention 1:1 visual scaling or true optical accuracy?",
                    "rationale": "Technical optical language.",
                    "expected_evidence_routes": ["text"],
                    "confidence": 0.82,
                },
                {
                    "question": "Do the specs mention zero magnification or a plano base curve?",
                    "rationale": "More technical optical language.",
                    "expected_evidence_routes": ["text"],
                    "confidence": 0.8,
                },
            ]
        }

    monkeypatch.setattr(service.chat_gateway, "invoke_json", fake_invoke_json)

    questions = service._generate_with_llm(aspect, questions_per_aspect=2)

    assert len(questions) == 2
    assert questions[0].question != questions[1].question


def test_question_service_rewrites_unrealistic_comfort_question(monkeypatch) -> None:
    service = QuestionGenerationService()
    aspect = _build_aspect().model_copy(update={"aspect": "comfort"})

    def fake_invoke_json(*, prompt_template, variables):
        return {
            "questions": [
                {
                    "question": "Do product images show padded straps, soft lining textures, or cushioned ear cups that support comfort?",
                    "rationale": "Need visual comfort cues.",
                    "expected_evidence_routes": ["image"],
                    "confidence": 0.84,
                }
            ]
        }

    monkeypatch.setattr(service.chat_gateway, "invoke_json", fake_invoke_json)

    questions = service._generate_with_llm(aspect, questions_per_aspect=1)

    assert "ear cups" not in questions[0].question.lower()
    assert "nose-pad" in questions[0].question.lower()
    assert questions[0].expected_evidence_routes == ["text", "image"]