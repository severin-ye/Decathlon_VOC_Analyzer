# Decathlon VOC Analyzer Agent Guide

面向 AI 编码代理的最小入口说明。只保留跨任务都会用到的信息；实现细节优先跳转到现有文档。

## Start Here

- 项目总览与常用命令：`README.md`
- 实验矩阵与评估：`0_docs/04_实验运行指南.md`
- 按源码边界组织的模块文档：`0_docs/03_论文子模块文档/README.md`
- 深入设计文档：`0_docs/01_设计文档/README.md`

## Fast Path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
.venv/bin/pytest
.venv/bin/ruff check .
uvicorn decathlon_voc_analyzer.app.api.main:app --reload
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010
```

## Repo Shape

- Python 包源码在 `05_src/decathlon_voc_analyzer/`，`pyproject.toml` 使用 `package-dir = {"": "05_src"}`。
- 测试在 `06_tests/`，pytest 已通过 `pythonpath=05_src` 指向源码。
- 数据输入在 `01_data/`，运行产物默认写到 `02_outputs/`。
- `oh-my-opencode/` 与本项目无关，且未被 Git 追踪。

## Project-Specific Conventions

- 优先使用仓库内虚拟环境命令，如 `.venv/bin/python`、`.venv/bin/pytest`、`.venv/bin/ruff`。
- 测试默认隔离真实模型与重型后端；不要把真实 LLM、CLIP 或外部 API 作为测试前提。需要背景时先看 `06_tests/conftest.py`。
- `get_settings()` 带有 `lru_cache`。脚本或测试里若改动环境变量，必须同步清理配置缓存，否则会读到旧值。
- `04_scripts/run_workflow.py` 会在导入服务前覆盖一批环境变量。排查工作流行为时，优先看 CLI 参数与脚本内设置，不要只改 `.env`。
- 涉及索引、Qdrant 或输出目录的任务，先确认是否有活跃流程占用 `02_outputs/`。`shared` scope 会复用固定 store，`isolated` 会为单次运行创建独立目录。
- `run_workflow.py` 会被脚本和测试以导入方式加载。修改它时保持模块级副作用最小，避免导入即启动重逻辑。

## Where To Dive Deeper

- `stage1_dataset` 到 `stage4_generation`、`workflows`、`evaluation` 的职责说明见 `0_docs/03_论文子模块文档/README.md` 及其同目录分文档。
- 运行策略、后端切换、提示词与 LLM 网关细节优先查 `0_docs/03_论文子模块文档/08_API配置LLM与提示词层.md`。
- 实验、监控、断点续跑、LLM-as-Judge 评估优先查 `0_docs/04_实验运行指南.md`。
