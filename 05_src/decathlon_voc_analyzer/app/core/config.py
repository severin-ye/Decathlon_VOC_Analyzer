from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Decathlon VOC Analyzer"
    app_env: str = "development"
    dataset_root: Path = ROOT_DIR / "01_data" / "01_raw_products" / "products"
    artifacts_root: Path = ROOT_DIR / "02_outputs"
    normalized_output_dir: Path = ROOT_DIR / "02_outputs" / "1_normalized"
    reports_output_dir: Path = ROOT_DIR / "02_outputs" / "4_reports"
    aspects_output_dir: Path = ROOT_DIR / "02_outputs" / "2_aspects"
    indexes_output_dir: Path = ROOT_DIR / "02_outputs" / "3_indexes"
    feedback_output_dir: Path = ROOT_DIR / "02_outputs" / "5_feedback"
    replay_output_dir: Path = ROOT_DIR / "02_outputs" / "5_replay"
    html_output_dir: Path = ROOT_DIR / "02_outputs" / "6_html"
    review_sampling_config_path: Path = ROOT_DIR / "03_configs" / "review_sampling_profiles.json"
    runtime_execution_policy_path: Path = ROOT_DIR / "03_configs" / "runtime_execution_policy.json"
    review_sampling_profile: str | None = None

    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_rerank_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    qwen_plus_model: str = "qwen-plus"
    qwen_embedding_model: str = "text-embedding-v4"
    qwen_reranker_model: str = "gte-rerank-v2"
    qwen_vl_embedding_model: str = "qwen2.5-vl-embedding"
    qwen_vl_reranker_model: str = "qwen-vl-max-latest"
    clip_vl_embedding_model: str = "openai/clip-vit-base-patch32"
    embedding_backend: str = "api"
    image_embedding_backend: str = "clip"
    retrieval_backend: str = "local"
    reranker_backend: str = "api"
    multimodal_reranker_backend: str = "qwen_vl"
    qdrant_collection_name: str = "product_evidence"
    qdrant_path: Path = ROOT_DIR / "02_outputs" / "3_indexes" / "qdrant_store"

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
    settings.feedback_output_dir.mkdir(parents=True, exist_ok=True)
    settings.replay_output_dir.mkdir(parents=True, exist_ok=True)
    settings.html_output_dir.mkdir(parents=True, exist_ok=True)
    return settings