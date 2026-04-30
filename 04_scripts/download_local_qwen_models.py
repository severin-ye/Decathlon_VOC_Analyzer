from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
MODELS = [
    "Qwen/Qwen3-VL-2B-Instruct",
    "Qwen/Qwen3-Embedding-0.6B",
    "Qwen/Qwen3-Reranker-0.6B",
]


def read_token_from_env_file(path: Path) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "Hugging_Face_User_Access_Tokens":
            token = value.strip()
            return token or None
    return None


def main() -> None:
    token = os.getenv("HF_TOKEN") or read_token_from_env_file(ENV_PATH)
    print("Using HF token:", "yes" if token else "no")
    for repo_id in MODELS:
        print(f"\nDownloading {repo_id} ...")
        cache_dir = snapshot_download(
            repo_id=repo_id,
            token=token,
            local_dir_use_symlinks=False,
        )
        print(f"Downloaded to: {cache_dir}")


if __name__ == "__main__":
    main()
