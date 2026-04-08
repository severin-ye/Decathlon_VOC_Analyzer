from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Decathlon VOC Analyzer"
    app_env: str = "development"
    dataset_root: Path = ROOT_DIR / "Dataset" / "products"
    artifacts_root: Path = ROOT_DIR / "artifacts"
    normalized_output_dir: Path = ROOT_DIR / "artifacts" / "normalized"
    reports_output_dir: Path = ROOT_DIR / "artifacts" / "reports"
    aspects_output_dir: Path = ROOT_DIR / "artifacts" / "aspects"
    indexes_output_dir: Path = ROOT_DIR / "artifacts" / "indexes"

    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_plus_model: str = "qwen-plus"
    qwen_embedding_model: str = "qwen3-vl-embedding-2b"
    retrieval_backend: str = "local"
    qdrant_collection_name: str = "product_evidence"
    qdrant_path: Path = ROOT_DIR / "artifacts" / "indexes" / "qdrant_store"

    qwen_plus_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("qwen-plus_api", "QWEN_PLUS_API_KEY"),
    )
    deepseek_v3_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DeepSeek-V3_api", "DEEPSEEK_V3_API_KEY"),
    )
    openai_gpt5_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("openai-gpt5_api", "OPENAI_GPT5_API_KEY"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.normalized_output_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_output_dir.mkdir(parents=True, exist_ok=True)
    settings.aspects_output_dir.mkdir(parents=True, exist_ok=True)
    settings.indexes_output_dir.mkdir(parents=True, exist_ok=True)
    return settings