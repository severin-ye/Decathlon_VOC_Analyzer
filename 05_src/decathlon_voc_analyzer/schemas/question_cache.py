from typing import Literal

from pydantic import BaseModel, Field

from decathlon_voc_analyzer.schemas.analysis import QuestionIntent, RetrievalQuestion


QuestionGenerationMode = Literal["llm", "heuristic"]


class QuestionGenerationCacheSignature(BaseModel):
    prompt_variant: str
    question_prompt_digest: str
    use_llm: bool
    questions_per_aspect: int = Field(ge=1, le=5)
    aspect_count: int = Field(ge=0)
    aspects_digest: str
    qwen_plus_api_enabled: bool
    qwen_plus_model: str
    qwen_base_url: str


class QuestionGenerationCachePayload(BaseModel):
    signature: QuestionGenerationCacheSignature
    question_mode: QuestionGenerationMode
    question_warnings: list[str] = Field(default_factory=list)
    question_intents: list[QuestionIntent] = Field(default_factory=list)
    questions: list[RetrievalQuestion] = Field(default_factory=list)
