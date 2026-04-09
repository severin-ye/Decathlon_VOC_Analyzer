import json
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

USER_PROMPT_TEMPLATES = {
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
}


@lru_cache(maxsize=None)
def _load_prompt_file(file_name: str) -> str:
        prompt_path = PROMPTS_DIR / file_name
        return prompt_path.read_text(encoding="utf-8").strip()


def get_prompt(name: str) -> str:
        return _load_prompt_file(PROMPT_FILES[name])


@lru_cache(maxsize=None)
def get_prompt_template(name: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=get_prompt(name)),
            ("human", USER_PROMPT_TEMPLATES[name]),
        ]
    )


def _format_user_prompt(name: str, payload: dict[str, object]) -> str:
    return USER_PROMPT_TEMPLATES[name].format(payload=json.dumps(payload, ensure_ascii=False))


def build_review_extraction_user_prompt(payload: dict[str, object]) -> str:
    return _format_user_prompt("review_extraction_system", payload)


def build_question_generation_user_prompt(payload: dict[str, object]) -> str:
    return _format_user_prompt("question_generation_system", payload)


def build_report_generation_user_prompt(payload: dict[str, object]) -> str:
    return _format_user_prompt("report_generation_system", payload)


def build_product_translation_user_prompt(payload: dict[str, object]) -> str:
    return _format_user_prompt("product_translation_system", payload)


def build_review_translation_user_prompt(payload: dict[str, object]) -> str:
    return _format_user_prompt("review_translation_system", payload)


def build_review_cleanup_user_prompt(payload: dict[str, object]) -> str:
    return _format_user_prompt("review_cleanup_system", payload)