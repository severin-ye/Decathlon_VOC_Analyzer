# Decathlon VOC Analyzer

Decathlon VOC Analyzer 是一个证据驱动的多模态商品 VOC 分析系统。系统以用户评论为需求入口，将评论抽取为方面级 VOC 信号，再围绕每个方面生成证据查询，从商品文案、商品图片和图片局部区域中召回可核验证据，最后生成带证据归因、证据缺口和改进建议的商品分析报告。

当前项目已经形成端到端闭环：数据标准化、评论抽样与方面抽取、多模态索引、两阶段召回、文本/图像重排、报告生成、claim 级证据归因、回放侧边车、HTML 导出和 manifest 评估。

## 核心能力

- 扫描 `01_data/01_raw_products/products/` 下的商品数据集，并输出数据质量概览。
- 将 `product.json`、`reviews.json` 和 `images/` 标准化为 `ProductEvidencePackage`。
- 对评论进行低信息过滤、星级抽样、方面级结构化抽取和去重。
- 将商品文案、商品整图和默认局部区域构建为可检索证据索引。
- 支持本地 JSON 索引和 Qdrant 索引后端。
- 支持文本 embedding、CLIP 图像 embedding、文本 reranker 和 Qwen-VL 多模态 reranker。
- 将评论方面规划为可执行的文本、图像或图文联合检索问题。
- 基于召回证据生成 strengths、weaknesses、controversies、evidence gaps 和 suggestions。
- 对报告主张构建 claim attribution，追踪到评论、商品文本和商品图片证据。
- 通过 feedback/replay sidecar 支持后续分析回放。
- 通过 manifest 评估 Recall@K、MRR、NDCG、claim support rate、citation precision 等指标。

## 架构概览

```text
01_data/
  01_raw_products/products/          # 原始商品、评论和图片
  02_audit_zh_products/products/     # 人工审核用中文导出数据
02_outputs/
  1_normalized/                      # 标准化商品证据包
  2_aspects/                         # 评论方面抽取结果
  3_indexes/                         # 本地索引、Qdrant store、检索缓存
  4_reports/                         # 分析报告 JSON
  5_feedback/                        # 人工反馈侧边车
  5_replay/                          # 回放侧边车
  6_html/                            # HTML 报告
  7_manifests/                       # 运行 manifest
03_configs/                          # 抽样 profile、运行策略等配置
04_scripts/                          # 批处理、评估、导出和验证脚本
05_src/decathlon_voc_analyzer/
  app/                               # FastAPI、配置、运行策略
  evaluation/                        # manifest 评估服务
  llm/                               # Qwen/OpenAI 兼容调用网关
  prompts/                           # 业务提示词
  schemas/                           # 全链路 Pydantic schema
  stage1_dataset/                    # 数据集扫描与商品证据标准化
  stage2_review_modeling/            # 评论抽样、清洗、方面抽取
  stage3_retrieval/                  # embedding、索引、召回、重排、缓存
  stage4_generation/                 # 问题规划、报告生成、归因、回放
  workflows/                         # LangGraph 单产品工作流
06_tests/                            # 测试目录
0_docs/                              # 设计文档、技术文档、论文子模块文档
论文_md形式/                         # 论文草稿与导出脚本
```

## 模块说明

`stage1_dataset` 负责把商品原始目录转化为结构化证据包。系统会为文本块、图片、图片区域和评论生成稳定 ID，并保留来源、语言、宽高、区域框等字段。

`stage2_review_modeling` 负责评论侧 VOC 建模。它支持 `problem_first`、`balanced`、`praise_first` 三类抽样 profile，并可在 LLM 抽取和启发式抽取之间切换。

`stage3_retrieval` 负责商品侧证据索引与召回。它将文本证据和图像证据分 route 建模，先通过 embedding 粗召回，再通过 reranker 精排，并把 query embedding 与 rerank 结果写入签名化缓存。

`stage4_generation` 负责把评论方面转成检索问题，聚合方面统计和召回证据，生成结构化 VOC 报告，并对报告主张做证据归因和回放修正。

`workflows` 使用 LangGraph 将 `overview -> normalize -> index -> analyze` 编排为单产品端到端工作流。

`evaluation` 读取运行 manifest 和分析产物，计算检索指标、claim attribution 指标和回放相关统计。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

如果需要 OpenVINO 相关依赖：

```bash
pip install -e .[openvino]
```

如果需要 GPU 相关可选依赖：

```bash
pip install -e .[gpu]
```

## 启动 API

```bash
uvicorn decathlon_voc_analyzer.app.api.main:app --reload
```

常用接口：

- `/health`
- `/api/v1/dataset/overview`
- `/api/v1/dataset/normalize`
- `/api/v1/index/overview`
- `/api/v1/index/build`
- `/api/v1/reviews/extract`
- `/api/v1/analysis/product`

`/api/v1/reviews/extract` 支持两种输入方式：传入 `product_id` 和可选 `category_slug`，或直接传入临时 `reviews` 数组。

`/api/v1/analysis/product` 会串联评论抽取、问题生成、图文召回、重排、方面聚合、报告生成和证据归因。

## 批处理运行

执行默认单产品工作流：

```bash
.venv/bin/python 04_scripts/run_workflow.py
```

指定商品：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010
```

分析中文审核数据集：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn
```

离线验证流程，不调用外部 LLM：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn --no-llm
```

只分析前 N 条评论可使用 `--max-reviews` 或简写参数：

```bash
.venv/bin/python 04_scripts/run_workflow.py --cn --R_5
```

输出 JSON 摘要：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --R_5 --no-llm --output-format json
```

同时导出 HTML 和 manifest：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --R_5 --no-llm --output-format json --export-html --write-manifest
```

默认会额外生成：

- `02_outputs/6_html/<category>/<product_id>.html`
- `02_outputs/7_manifests/<category>/<product_id>_run_manifest.json`

## 检索后端

API 默认使用本地持久化索引，批处理入口默认可切换到 Qdrant。常用参数：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --retrieval-backend local
```

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --retrieval-backend qdrant
```

批处理运行可以通过 `--qdrant-scope shared` 或 `--qdrant-path <dir>` 控制 Qdrant store 的复用方式。

## 模型与运行策略

默认配置位于 `05_src/decathlon_voc_analyzer/app/core/config.py`，运行时读取根目录 `.env`。

主要模型配置：

- `qwen_plus_model=qwen-plus`
- `qwen_embedding_model=text-embedding-v4`
- `qwen_reranker_model=gte-rerank-v2`
- `qwen_vl_reranker_model=qwen-vl-max-latest`
- `clip_vl_embedding_model=openai/clip-vit-base-patch32`
- `local_embedding_model_name=Qwen/Qwen3-Embedding-0.6B`
- `local_reranker_model_name=Qwen/Qwen3-Reranker-0.6B`
- `local_multimodal_reranker_model_name=Qwen/Qwen3-VL-2B-Instruct`

主要后端配置：

- `embedding_backend=api` 或 `embedding_backend=local_qwen3`
- `image_embedding_backend=clip`
- `retrieval_backend=local` 或 `retrieval_backend=qdrant`
- `reranker_backend=api` 或 `reranker_backend=local_qwen3`
- `multimodal_reranker_backend=qwen_vl` 或 `multimodal_reranker_backend=local_qwen3_vl`

如果外部模型不可用，系统在允许降级时会回退到 hash embedding 或 heuristic reranker。严格运行策略由 `03_configs/runtime_execution_policy.json` 控制：

- `allow_degradation=true`：允许模型失败后降级，适合开发验证。
- `allow_degradation=false`：禁止静默降级，适合正式实验。
- `full_power=true`：要求完整模型链路，且请求不能关闭 LLM。

API Key 兼容两组变量名：

- `qwen-plus_api` 或 `QWEN_PLUS_API_KEY`
- `DeepSeek-V3_api` 或 `DEEPSEEK_V3_API_KEY`
- `openai-gpt5_api` 或 `OPENAI_GPT5_API_KEY`

## 评论抽样

评论抽样配置位于 `03_configs/review_sampling_profiles.json`。当前内置 profile：

- `problem_first`：优先低星问题评论。
- `balanced`：尽量均衡覆盖 1 至 5 星评论。
- `praise_first`：优先高星优势评论。

默认 profile 为 `problem_first`，默认星级配额为：

- 5 星：10%
- 4 星：15%
- 3 星：20%
- 2 星：25%
- 1 星：30%

当 `max_reviews` 被设置时，系统会按配额构建抽样池；如果低星评论不足，会按 `fallback_order` 逐级补位。抽样结果会写入 `sampling_plan`，并在 JSON 输出中提升为 `review_sampling` 摘要。

## 评估

如果运行时写入 manifest，可使用：

```bash
.venv/bin/python 04_scripts/evaluate_manifests.py 02_outputs/7_manifests
```

当 manifest 或 analysis artifact 中存在 `retrieval_relevance` gold labels 时，评估服务会计算：

- `Recall@1/3/5`
- `MRR`
- `NDCG@3/5`

即使没有 gold labels，评估服务也会统计：

- informative review 数量
- aspect 数量和平均置信度
- question 数量和平均置信度
- retrieval evidence 数量
- evidence coverage、score drift、conflict risk
- claim support rate、claim grounded rate、citation precision
- text、image、mixed route contribution

## 常用脚本

导出单产品中文审核数据：

```bash
.venv/bin/python 04_scripts/export_single_product_chinese_dataset.py --category backpack --product-id backpack_010
```

真实多模态运行态回归：

```bash
.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010
```

导出已有分析报告为 HTML：

```bash
.venv/bin/python 04_scripts/export_html_report.py --category backpack --product-id backpack_010
```

清理生成产物：

```bash
.venv/bin/python 04_scripts/clear_generated_outputs.py
```

## 文档入口

- `0_docs/01_设计文档/`：早期设计、路线和参考资料。
- `0_docs/02_技术文档/`：教程、推理、本地模型和技术说明。
- `0_docs/03_论文子模块文档/`：基于当前源码整理的论文写作模块文档。
- `论文_md形式/`：论文草稿、参考文献和导出脚本。

论文子模块文档是当前最适合继续写论文的方法章节和系统章节的入口。
