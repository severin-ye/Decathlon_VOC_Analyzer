from decathlon_voc_analyzer.prompts import (
    build_question_generation_user_prompt,
    build_report_generation_user_prompt,
    build_review_extraction_user_prompt,
    get_prompt,
)


def test_prompt_registry_contains_main_review_prompt() -> None:
    prompt = get_prompt("review_extraction_system", variant="main")

    assert "review structure extractor" in prompt
    assert "JSON" in prompt


def test_prompt_registry_contains_cn_review_prompt() -> None:
    prompt = get_prompt("review_extraction_system", variant="CN")

    assert "评论结构化抽取器" in prompt
    assert "JSON" in prompt


def test_prompt_builders_embed_payload() -> None:
    review_prompt = build_review_extraction_user_prompt({"review_text": "Great product"}, variant="main")
    question_prompt = build_question_generation_user_prompt({"aspect": "storage capacity"}, variant="main")
    report_prompt = build_report_generation_user_prompt({"product_id": "backpack_010"}, variant="main")

    assert "Great product" in review_prompt
    assert "storage capacity" in question_prompt
    assert "backpack_010" in report_prompt