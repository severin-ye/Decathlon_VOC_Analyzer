import json
import os
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate


PROMPT_FILES = {
    "product_translation_system": "1_商品信息翻译系统提示词.md",
    "review_translation_system": "2_评论翻译系统提示词.md",
    "review_cleanup_system": "3_评论清洗系统提示词.md",
    "review_extraction_system": "4_评论结构化抽取系统提示词.md",
    "question_generation_system": "5_核验问题生成系统提示词.md",
    "report_generation_system": "6_VOC报告生成系统提示词.md",
}


PROMPTS_DIR = Path(__file__).resolve().parent
PROMPT_VARIANT_DIRS = {
    "main": PROMPTS_DIR / "main",
    "CN": PROMPTS_DIR / "CN",
}
PROMPT_VARIANT_ALIASES = {
    "main": "main",
    "default": "main",
    "en": "main",
    "cn": "CN",
    "zh": "CN",
    "zh-cn": "CN",
    "CN": "CN",
}

USER_PROMPT_TEMPLATES = {
    "main": {
        "review_extraction_system": "Extract structured aspects from the following review input and return JSON only.\n{payload}",
        "question_generation_system": "Generate evidence-checking questions from the following aspect input and return JSON only.\n{payload}",
        "report_generation_system": "Generate an evidence-grounded VOC report from the following aggregated evidence input and return JSON only.\n{payload}",
        "product_translation_system": (
            "Translate the following single-product information into English and return strict JSON using this structure: "
            "{{\"product_name\": \"string\", \"model_description\": \"string\", \"category\": \"string\"}}.\n"
            "{payload}"
        ),
        "review_translation_system": (
            "Translate the following batch of reviews into English and return strict JSON using this structure: "
            "{{\"reviews\": [{{\"user_id\": \"string\", \"rating\": 5, \"content\": \"English review\"}}]}}.\n"
            "{payload}"
        ),
        "review_cleanup_system": "Clean the following text into reviewer-friendly English and return strict JSON.\n{payload}",
    },
    "CN": {
        "review_extraction_system": "请基于以下评论输入完成结构化抽取，并按要求返回 JSON。\n{payload}",
        "question_generation_system": "请基于以下 aspect 输入生成中文核验问题，并按要求返回 JSON。\n{payload}",
        "report_generation_system": "请基于以下证据聚合输入生成中文 VOC 报告，并按要求返回 JSON。\n{payload}",
        "product_translation_system": (
            "请把以下单产品信息翻译成中文，并返回严格 JSON，结构如下："
            "{{\"product_name\": \"字符串\", \"model_description\": \"字符串\", \"category\": \"字符串\"}}。\n"
            "{payload}"
        ),
        "review_translation_system": (
            "请把以下评论批次翻译成中文，并返回严格 JSON，结构如下："
            "{{\"reviews\": [{{\"user_id\": \"字符串\", \"rating\": 5, \"content\": \"中文评论\"}}]}}。\n"
            "{payload}"
        ),
        "review_cleanup_system": "请把以下文本清洗为适合人工审核的中文版本，并返回严格 JSON。\n{payload}",
    },
}


def get_prompt_variant() -> str:
    variant = normalize_prompt_variant(os.getenv("PROMPT_VARIANT", "main"))
    if variant not in PROMPT_VARIANT_DIRS:
        return "main"
    return variant


def normalize_prompt_variant(variant: str | None) -> str:
    if variant is None:
        return "main"
    return PROMPT_VARIANT_ALIASES.get(str(variant), "main")


@lru_cache(maxsize=None)
def _load_prompt_file(file_name: str, variant: str) -> str:
    prompt_path = PROMPT_VARIANT_DIRS[variant] / file_name
    return prompt_path.read_text(encoding="utf-8").strip()


def get_prompt(name: str, variant: str | None = None) -> str:
    resolved_variant = normalize_prompt_variant(variant) if variant is not None else get_prompt_variant()
    return _load_prompt_file(PROMPT_FILES[name], resolved_variant)


@lru_cache(maxsize=None)
def get_prompt_template(name: str, variant: str | None = None) -> ChatPromptTemplate:
    resolved_variant = normalize_prompt_variant(variant) if variant is not None else get_prompt_variant()
    return ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=get_prompt(name, resolved_variant)),
            ("human", USER_PROMPT_TEMPLATES[resolved_variant][name]),
        ]
    )


def _format_user_prompt(name: str, payload: dict[str, object], variant: str | None = None) -> str:
    resolved_variant = normalize_prompt_variant(variant) if variant is not None else get_prompt_variant()
    return USER_PROMPT_TEMPLATES[resolved_variant][name].format(
        payload=json.dumps(payload, ensure_ascii=False)
    )


def build_review_extraction_user_prompt(payload: dict[str, object], variant: str | None = None) -> str:
    return _format_user_prompt("review_extraction_system", payload, variant)


def build_question_generation_user_prompt(payload: dict[str, object], variant: str | None = None) -> str:
    return _format_user_prompt("question_generation_system", payload, variant)


def build_report_generation_user_prompt(payload: dict[str, object], variant: str | None = None) -> str:
    return _format_user_prompt("report_generation_system", payload, variant)


def build_product_translation_user_prompt(payload: dict[str, object], variant: str | None = None) -> str:
    return _format_user_prompt("product_translation_system", payload, variant)


def build_review_translation_user_prompt(payload: dict[str, object], variant: str | None = None) -> str:
    return _format_user_prompt("review_translation_system", payload, variant)


def build_review_cleanup_user_prompt(payload: dict[str, object], variant: str | None = None) -> str:
    return _format_user_prompt("review_cleanup_system", payload, variant)