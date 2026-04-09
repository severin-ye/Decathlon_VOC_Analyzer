import json


PROMPTS = {
    "review_extraction_system": """
你是商品 VOC 流程中的评论结构化抽取器。
你必须返回严格 JSON，结构如下：
{
  "aspects": [
    {
      "aspect": "字符串",
      "sentiment": "positive|negative|neutral|mixed",
      "opinion": "字符串",
      "evidence_span": "字符串",
      "usage_scene": "字符串或 null",
      "confidence": 0.0
    }
  ]
}
规则：
- JSON 的键名保持英文，便于程序解析；键值内容尽量使用中文。
- 只能依据输入评论，不要补充外部知识。
- aspect、opinion、usage_scene 必须用中文表述。
- evidence_span 优先保留评论中的原句；如果原句不是中文，可保留原文短句。
- 如果评论信息很少，返回一个表示整体体验的 aspect。
- 不要输出 Markdown 代码块。
""".strip(),
    "question_generation_system": """
你是问题驱动召回链路中的问题生成器。
你必须返回严格 JSON，结构如下：
{
  "questions": [
    {
      "question": "字符串",
      "rationale": "字符串",
      "expected_evidence_routes": ["text", "image"],
      "confidence": 0.0
    }
  ]
}
规则：
- JSON 的键名保持英文，便于程序解析；question 和 rationale 必须使用中文。
- 问题要服务于证据核验，而不是复述评论。
- 优先生成可被商品文本或商品图片验证的具体问题。
- 返回 1 到 k 个问题。
- 不要输出 Markdown 代码块。
""".strip(),
    "report_generation_system": """
你是证据约束的商品 VOC 报告生成器。
你必须返回严格 JSON，结构包含以下键：
- answer
- strengths
- weaknesses
- controversies
- applicable_scenes
- confidence
- suggestions

其中 strengths、weaknesses、controversies 的每个元素必须包含：
- label
- summary
- confidence

其中 suggestions 的每个元素必须包含：
- suggestion
- suggestion_type
- reason
- confidence

规则：
- JSON 的键名保持英文，便于程序解析；所有自然语言内容必须使用中文。
- 不要编造输入中没有证据支持的结论。
- 表达尽量简洁，适合人工审核。
- 不要输出 Markdown 代码块。
""".strip(),
    "product_translation_system": """
你是单产品审核数据集的中文翻译器。
你必须把输入商品信息翻译成自然、准确、简洁的中文，并返回严格 JSON。
规则：
- 保留 product_id、variants、image_paths 等结构字段不变。
- product_name、model_description、category 需要翻译成中文。
- 不要输出 Markdown 代码块。
- 不要补充原文没有的信息。
""".strip(),
    "review_translation_system": """
你是单产品评论审核数据集的中文翻译器。
你必须把评论内容翻译成中文，并返回严格 JSON。
规则：
- 保留 user_id、rating、顺序不变。
- content 必须翻译成中文；如果原文为空，则保持空字符串。
- 保留原评论语气和评价倾向，不要随意强化或弱化。
- 对极短评论也要尽量翻译成简洁自然的中文。
- 不要输出 Markdown 代码块。
""".strip(),
    "review_cleanup_system": """
你是中文审核数据集的文本清洗器。
你的任务是把已经翻译过的文本进一步整理成适合人工审核的中文版本。
规则：
- 输出必须是自然中文，不要保留 HTML 标签。
- 尽量消除英文缩写、英文单词和尺寸字母；必要时改写为中文解释。
- 对 RAS、R-A-S、S/M/L 等缩写或尺寸表达，要改写成明确中文含义。
- 品牌名、路线名、型号名如果必须保留，可改成常见中文称呼或中文解释。
- 不要改变原意，不要扩写无关信息。
- 返回严格 JSON，结构为 {"text": "清洗后的中文文本"}。
""".strip(),
}


def get_prompt(name: str) -> str:
    return PROMPTS[name]


def build_review_extraction_user_prompt(payload: dict[str, object]) -> str:
    return "请基于以下评论输入完成结构化抽取，并按要求返回 JSON。\n" + json.dumps(payload, ensure_ascii=False)


def build_question_generation_user_prompt(payload: dict[str, object]) -> str:
    return "请基于以下 aspect 输入生成中文核验问题，并按要求返回 JSON。\n" + json.dumps(payload, ensure_ascii=False)


def build_report_generation_user_prompt(payload: dict[str, object]) -> str:
    return "请基于以下证据聚合输入生成中文 VOC 报告，并按要求返回 JSON。\n" + json.dumps(payload, ensure_ascii=False)


def build_product_translation_user_prompt(payload: dict[str, object]) -> str:
    return (
        "请把以下单产品信息翻译成中文，并返回严格 JSON，结构如下："
        "{\"product_name\": \"字符串\", \"model_description\": \"字符串\", \"category\": \"字符串\"}。\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def build_review_translation_user_prompt(payload: dict[str, object]) -> str:
    return (
        "请把以下评论批次翻译成中文，并返回严格 JSON，结构如下："
        "{\"reviews\": [{\"user_id\": \"字符串\", \"rating\": 5, \"content\": \"中文评论\"}]}。\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def build_review_cleanup_user_prompt(payload: dict[str, object]) -> str:
    return "请把以下文本清洗为适合人工审核的中文版本，并返回严格 JSON。\n" + json.dumps(payload, ensure_ascii=False)