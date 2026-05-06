---
description: "Use when debugging workflow runs, runtime configuration, backend selection, environment-variable overrides, Qdrant locks, output cleanup, or offline fallbacks in Decathlon VOC Analyzer."
name: "Runtime Debugging"
---

# Runtime Debugging

- Before trusting any changed environment variable, check whether `get_settings()` has been cached. In Python code that mutates env vars, call `get_settings.cache_clear()` before recreating settings-dependent services.
- When debugging `04_scripts/run_workflow.py` or `04_scripts/validate_multimodal_runtime.py`, prefer CLI flags over `.env` edits. These script entrypoints set `DATASET_ROOT`, `REPORTS_OUTPUT_DIR`, `QDRANT_PATH`, `PROMPT_VARIANT` and related variables before importing services.
- Keep offline validation separate from full-model validation. Tests already force `EMBEDDING_BACKEND=hash`, `RERANKER_BACKEND=heuristic`, `MULTIMODAL_RERANKER_BACKEND=disabled`, `RETRIEVAL_BACKEND=local`, and permissive runtime policy in `06_tests/conftest.py`.
- If a run touches Qdrant stores or `02_outputs/`, first check for active `run_workflow.py`, `launch_interactive_workflow.py`, or `validate_multimodal_runtime.py` processes. Shared Qdrant scope and cleanup scripts are intentionally conservative around live processes.
- Preserve import safety in `04_scripts/run_workflow.py`. Some tests and validators import that module via `importlib.util`, so avoid new module-level side effects.
- For backend triage, inspect this order before editing code: runtime policy in `03_configs/runtime_execution_policy.json`, backend env vars, CLI flags, then service defaults in `05_src/decathlon_voc_analyzer/app/core/config.py`.
- If a task needs the authoritative runtime architecture or experiment behavior, read `0_docs/03_论文子模块文档/08_API配置LLM与提示词层.md` and `0_docs/04_实验运行指南.md` instead of duplicating those details here.