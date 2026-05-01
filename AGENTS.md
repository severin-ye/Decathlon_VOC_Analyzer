# Decathlon VOC Analyzer —— 智能体备忘

**技术栈：** Python ≥3.11、FastAPI、Pydantic v2、LangChain/LangGraph、Pytest、Ruff。

## 环境搭建

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

- 源码位于 `05_src/`；setuptools 映射为 `package-dir = {"": "05_src"}`。
- 仓库根目录的 `oh-my-opencode/` **未被 Git 追踪**，与本项目无关。

## 运行方式

- **启动 API 服务：** `uvicorn decathlon_voc_analyzer.app.api.main:app --reload`
- **单商品工作流：** `.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010`
- **中文审核数据集：** 加 `--cn`（自动切换数据集根目录、提示词变体和输出命名空间）
- **离线 / 无 LLM：** 加 `--no-llm`（使用启发式降级链路）
- **限制评论数：** `--R_5` 是 `--max-reviews 5` 的简写，在 argparse 解析前被内部转换
- **导出 HTML + 清单：** 加 `--export-html --write-manifest`
- **清理输出产物：** `.venv/bin/python 04_scripts/clear_generated_outputs.py --yes`

## 测试

```bash
.venv/bin/pytest              # 运行 06_tests；pythonpath=05_src
.venv/bin/pytest -k test_name # 运行单个测试
```

- `conftest.py` 中的 **autouse fixture** 会隔离整个测试套件，使其不调用真实 LLM 和重型后端。它会强制设置：
  - `EMBEDDING_BACKEND=hash`
  - `RERANKER_BACKEND=heuristic`
  - `MULTIMODAL_RERANKER_BACKEND=disabled`
  - `RETRIEVAL_BACKEND=local`
  - 空 API key
  - 通过临时运行时策略文件设置 `allow_degradation: true`
- 它还会调用 `get_settings.cache_clear()` 并重置 FastAPI 路由服务单例。
- 测试中 **不要依赖真实的模型调用**。

## 代码检查 / 格式化

```bash
.venv/bin/ruff check .
.venv/bin/ruff format .
```

- 配置位于 `pyproject.toml`：行宽 100，目标版本 `py311`。

## 架构

```
05_src/decathlon_voc_analyzer/
  app/                # FastAPI、配置、路由
  stage1_dataset/     # 将原始商品标准化为 ProductEvidencePackage
  stage2_review_modeling/  # 评论抽样、方面抽取
  stage3_retrieval/   # 向量嵌入、索引构建（本地 JSON 或 Qdrant）、重排
  stage4_generation/  # 问题规划、报告生成、主张归因
  workflows/          # LangGraph 编排 + 实验运行器
  evaluation/         # 清单评估指标
  llm/                # Qwen / OpenAI 兼容网关
  prompts/            # 提示词模板，支持变体（main / CN）
  schemas/            # 全链路 Pydantic 模型
```

## 关键约定与注意事项

- **配置缓存：** `get_settings()` 使用了 `@lru_cache(maxsize=1)`。修改环境变量后必须调用 `get_settings.cache_clear()`，否则旧值仍会保留。测试中已自动处理。
- **环境变量覆盖：** `run_workflow.py` 在导入服务前会设置大量环境变量（`DATASET_ROOT`、`REPORTS_OUTPUT_DIR`、`QDRANT_PATH`、`PROMPT_VARIANT` 等）。仅修改 `.env` 文件可能不会影响脚本运行。
- **后端切换：** `EMBEDDING_BACKEND`、`IMAGE_EMBEDDING_BACKEND`、`RERANKER_BACKEND`、`MULTIMODAL_RERANKER_BACKEND`、`RETRIEVAL_BACKEND` 控制加载的具体实现。默认值见 `app/core/config.py`。
- **API Key 双名：** `qwen-plus_api` **或** `QWEN_PLUS_API_KEY`；`DeepSeek-V3_api` **或** `DEEPSEEK_V3_API_KEY`；`openai-gpt5_api` **或** `OPENAI_GPT5_API_KEY`。
- **运行时策略：** `03_configs/runtime_execution_policy.json` 控制系统是否允许静默降级到更便宜的后端。仓库默认 `allow_degradation: false`；测试中会覆盖为 `true`。
- **断点续跑：** `run_workflow.py` 支持 `--resume-from-aspects` 和 `--resume-from-analysis-checkpoint`，可跳过已完成的早期阶段。
- **脚本可被导入：** `validate_multimodal_runtime.py` 和部分测试通过 `importlib.util` 加载 `run_workflow.py` —— 应保持模块级副作用最小化。
- **Qdrant 作用域：** `--qdrant-scope isolated`（默认）每次运行创建独立目录；`shared` 则复用固定的 `qdrant_store`。
