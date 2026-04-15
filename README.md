# Decathlon VOC Analyzer

本仓库实现一个证据驱动的多模态商品 VOC 分析系统。当前阶段先落 MVP 工程基座：

- 后端 Web API
- 数据集扫描与质量概览
- 商品与评论标准化输出
- 为后续评论 Aspect 抽取、多模态检索、证据聚合与生成保留稳定 schema

## 当前能力

- 扫描 01_data/01_raw_products/products 下的商品目录
- 检查 product.json、reviews.json 和图片目录的一致性
- 生成标准化商品证据包
- 输出数据质量摘要报告
- 提供 FastAPI 接口查询与触发标准化

## 目录结构

```text
01_data/
  01_raw_products/
    products/
  02_audit_zh_products/
    products/
02_outputs/
03_docs/
04_scripts/
05_src/decathlon_voc_analyzer/
  app/
  prompts/
  schemas/
  stage1_dataset/
  stage2_review_modeling/
  stage3_retrieval/
  stage4_generation/
06_tests/
```

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 运行

```bash
uvicorn decathlon_voc_analyzer.app.api.main:app --reload
```

启动后访问：

- `/health`
- `/api/v1/dataset/overview`
- `/api/v1/dataset/normalize`
- `/api/v1/index/overview`
- `/api/v1/index/build`
- `/api/v1/reviews/extract`
- `/api/v1/analysis/product`

`/api/v1/reviews/extract` 支持两种模式：

- 传入 `product_id` 和可选 `category_slug`，直接从 01_data/01_raw_products/products 中读取商品评论并做结构化抽取
- 直接传入 `reviews` 数组，做临时评论抽取实验

建议开发期先设置 `use_llm=false` 跑通链路，再切换到真实模型抽取。

`/api/v1/analysis/product` 会串起：

- 读取商品评论
- 做 Aspect 结构化抽取
- 先从每个 aspect 生成 k 个待澄清问题
- 再围绕这些问题在同商品的图文证据中执行双路召回
- 聚合方面统计
- 生成综合意见与改进建议

这一版默认支持纯本地启发式闭环，因此即使未配置向量库，也能完整跑通 MVP 主链路。

索引层现在已独立成一个可持久化模块：

- `/api/v1/index/build` 用于为商品图文证据构建本地索引
- `/api/v1/index/overview` 用于查看当前索引覆盖范围

API 配置层当前默认后端仍是本地持久化向量索引；批处理入口 `04_scripts/run_workflow.py` 已默认切到 Qdrant，并可通过 `--retrieval-backend local` 显式回退。

当前检索层已经拆成两层：

- EmbeddingService：负责文本和图像代理文本向量化
- IndexBackend：负责索引存储与检索；API 默认是 local，批跑默认是 qdrant

当前召回链路已经升级为“两阶段检索”：

- 第一阶段：embedding 粗召回
- 第二阶段：reranker 精排

默认策略为：

- 运行态优先使用真实 embedding API 与专用 reranker API
- 测试态固定使用 hash embedding 与 heuristic reranker，保证可重复和离线可测

当前默认 embedding 模型为 `text-embedding-v4`，通过 DashScope OpenAI 兼容接口调用。
当前默认 reranker 模型为 `gte-rerank-v2`，通过 DashScope 原生 rerank 接口调用。
当前所有业务提示词已统一收口到 `05_src/decathlon_voc_analyzer/prompts/` 目录管理。

评论抽样现在也支持配置文件控制，默认配置文件位于 `03_configs/review_sampling_profiles.json`。

当前配置文件内置 3 个 profile：`problem_first`、`balanced`、`praise_first`。

- `problem_first`：优先低星问题评论
- `balanced`：尽量均衡覆盖 1-5 星评论
- `praise_first`：优先高星优势评论

通过修改 `active_profile` 就可以一键切换当前默认 profile。当前默认 profile 为 `problem_first`，默认星级配额为：

- 5 星：10%
- 4 星：15%
- 3 星：20%
- 2 星：25%
- 1 星：30%

当 `max_reviews` 被设置为具体数量时，系统会先按该配额构建评论抽样池，再进入评论抽取；若低星评论不足，会按 `fallback_order: [1, 2, 3, 4, 5]` 逐级补位。

如果需要为人工审核导出单产品中文数据集，可运行：

```bash
.venv/bin/python 04_scripts/export_single_product_chinese_dataset.py --category backpack --product-id backpack_010
```

默认输出到 `01_data/02_audit_zh_products/products/<category>/<product_id>/`，目录结构与原始数据集保持一致，包含：

- `product.json`
- `reviews.json`
- `images/`

当前 `02_outputs/` 目录按流水线顺序编号：

- `1_normalized/`
- `CN/1_normalized/`
- `2_aspects/`
- `CN/2_aspects/`
- `3_indexes/`
- `CN/3_indexes/`
- `4_reports/`
- `CN/4_reports/`

如果希望一条命令直接跑完整工作流，可运行：

```bash
.venv/bin/python 04_scripts/run_workflow.py
```

默认会针对 `backpack/backpack_010` 执行：

- 标准化
- 索引构建
- 完整分析

如果要直接分析中文测试数据集，可运行：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn
```

如果只想本地验证流程、不调用外部模型，可加：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn --no-llm
```

也可以显式指定商品：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010
```

如果只想分析前 N 条评论，也可以使用简写参数：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn --R_5
```

其中 `--R_5` 表示只分析前 5 条评论，等价于：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn --max-reviews 5
```

如果希望批处理稳定消费运行结果，推荐直接使用 JSON 输出：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --R_5 --no-llm --output-format json
```

该模式会返回统一摘要，包含：

- `review_sampling.profile_name`
- `review_sampling.allocations`
- `analysis.artifact_path`
- `analysis.replay_applied`
- `analysis.replay_persistent_issue_count`
- `artifact_bundle.analysis_path`
- `artifact_bundle.feedback_path`
- `artifact_bundle.replay_path`

评论抽取响应与 `02_outputs/2_aspects/<category>/<product_id>.json` 中还会额外包含 `sampling_plan`；而 `run_workflow.py --output-format json` 现在会把同一份抽样计划直接抬到顶层 `review_sampling`。其中会写明：

- 每个星级的目标数量 `target_count`
- 每个星级的可用数量 `available_count`
- 每个星级的实际抽取数量 `selected_count`
- 因缺口被补入的数量 `redistributed_in_count`
- 未满足目标的数量 `shortfall_count`

若沿用批处理默认配置，`run_workflow.py` 会默认设置 `retrieval_backend=qdrant`，并在存在历史 replay sidecar 时自动把上一轮回放摘要接回当前分析；如需关闭 Qdrant，可显式传入：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --retrieval-backend local
```

如果希望一条命令同时导出 HTML，并把本次运行摘要落盘为 manifest，可运行：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --R_5 --no-llm --output-format json --export-html --write-manifest
```

默认会额外生成：

- `02_outputs/6_html/<category>/<product_id>.html`
- `02_outputs/7_manifests/<category>/<product_id>_run_manifest.json`

如需自定义 manifest 路径，可显式指定：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --manifest-path 02_outputs/custom/backpack_010_manifest.json
```

如果要切换后端，可在 `.env` 中设置：

- `retrieval_backend=local`
- `retrieval_backend=qdrant`

如需显式控制检索质量组件，也可设置：

- `embedding_backend=api` 或 `embedding_backend=hash`
- `reranker_backend=api` 或 `reranker_backend=heuristic`

## 配置

默认读取仓库根目录的 `.env`。为了兼容现有文件，配置层同时支持两组变量名：

- 现有格式：`qwen-plus_api`、`DeepSeek-V3_api`、`openai-gpt5_api`
- 规范格式：`QWEN_PLUS_API_KEY`、`DEEPSEEK_V3_API_KEY`、`OPENAI_GPT5_API_KEY`

后续阶段会继续补齐评论结构化、检索、聚合与生成链路。