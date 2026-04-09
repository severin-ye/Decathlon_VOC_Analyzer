# Decathlon VOC Analyzer

本仓库实现一个证据驱动的多模态商品 VOC 分析系统。当前阶段先落 MVP 工程基座：

- 后端 Web API
- 数据集扫描与质量概览
- 商品与评论标准化输出
- 为后续评论 Aspect 抽取、多模态检索、证据聚合与生成保留稳定 schema

## 当前能力

- 扫描 Dataset/products 下的商品目录
- 检查 product.json、reviews.json 和图片目录的一致性
- 生成标准化商品证据包
- 输出数据质量摘要报告
- 提供 FastAPI 接口查询与触发标准化

## 目录结构

```text
src/decathlon_voc_analyzer/
  api/
  core/
  models/
  prompts/
  services/
artifacts/
Dataset/
设计文档/
```

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 运行

```bash
uvicorn decathlon_voc_analyzer.api.main:app --reload
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

- 传入 `product_id` 和可选 `category_slug`，直接从 Dataset 中读取商品评论并做结构化抽取
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

当前默认后端是本地持久化向量索引，后续可在不改 API 的前提下切换到 Qdrant。

当前检索层已经拆成两层：

- EmbeddingService：负责文本和图像代理文本向量化
- IndexBackend：负责索引存储与检索，默认是 local，可切换为 qdrant

当前召回链路已经升级为“两阶段检索”：

- 第一阶段：embedding 粗召回
- 第二阶段：reranker 精排

默认策略为：

- 运行态优先使用真实 embedding API 与专用 reranker API
- 测试态固定使用 hash embedding 与 heuristic reranker，保证可重复和离线可测

当前默认 embedding 模型为 `text-embedding-v4`，通过 DashScope OpenAI 兼容接口调用。
当前默认 reranker 模型为 `gte-rerank-v2`，通过 DashScope 原生 rerank 接口调用。
当前所有业务提示词已统一收口到 `src/decathlon_voc_analyzer/prompts/` 目录管理。

如果需要为人工审核导出单产品中文数据集，可运行：

```bash
.venv/bin/python scripts/export_single_product_chinese_dataset.py --category backpack --product-id backpack_010
```

默认输出到 `Dataset_zh/products/<category>/<product_id>/`，目录结构与原始数据集保持一致，包含：

- `product.json`
- `reviews.json`
- `images/`

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