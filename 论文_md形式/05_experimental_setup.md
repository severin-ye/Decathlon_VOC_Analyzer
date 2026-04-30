# 5 实验设置

## 5.1 实验目标

本文实验定位为系统验证，而非完整 benchmark。实验目标包括四点：验证端到端工作流是否可运行；验证各阶段产物是否结构化且可审查；验证真实模型链路与降级链路是否能够通过运行策略区分；验证评估模块是否能够在有标注和无标注条件下输出可用指标。

## 5.2 运行环境与软件栈

项目基于 Python 3.11+，当前验证环境为 Python 3.12。核心依赖包括 FastAPI、Pydantic、Pydantic Settings、LangChain、LangGraph、OpenAI SDK、Qdrant Client、Transformers、Torch、Pillow、orjson 和 pytest。

API 入口由 FastAPI 提供，批处理入口由 `04_scripts/run_workflow.py` 提供，单商品工作流由 LangGraph 编排。LLM 调用通过 OpenAI 兼容 Qwen 网关完成；检索层支持本地 JSON 索引和 Qdrant 索引；图像 embedding 默认使用 CLIP；图像候选重排默认可使用 Qwen-VL。

## 5.3 数据与产物

原始商品数据位于 `01_data/01_raw_products/products/`，人工审核用中文数据可导出到 `01_data/02_audit_zh_products/products/`。系统产物按阶段写入 `02_outputs/`：标准化证据包写入 `1_normalized/`，评论方面写入 `2_aspects/`，索引与缓存写入 `3_indexes/`，分析报告写入 `4_reports/`，feedback 和 replay 写入 `5_feedback/` 与 `5_replay/`，HTML 报告写入 `6_html/`，运行 manifest 写入 `7_manifests/`。

本文不把当前数据样例描述为冻结公开 benchmark。当前数据用于验证系统链路、schema 产物和评估接口；后续若要比较不同检索策略，需要补充多品类人工标注集。

## 5.4 工作流协议

标准单商品协议如下：

1. 扫描数据集并生成概览。
2. 标准化目标商品证据包。
3. 为目标商品构建文本和图像索引。
4. 抽样并抽取评论方面。
5. 将方面规划为检索问题。
6. 对文本和图像 route 执行粗召回。
7. 对候选证据进行文本或多模态重排。
8. 聚合方面统计并生成报告。
9. 构建 claim attribution、trace、feedback/replay 和 manifest。
10. 可选导出 HTML 报告。

核心命令如下：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --export-html --write-manifest
```

离线验证可关闭 LLM：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --no-llm --output-format json
```

真实多模态运行态验证可使用：

```bash
.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010
```

## 5.5 评估指标

当 manifest 或 analysis artifact 包含 `retrieval_relevance` 标注时，评估模块计算 Recall@1、Recall@3、Recall@5、MRR、NDCG@3 和 NDCG@5。这些指标是信息检索评估中的常用排序与召回指标 [13]。相关证据可以是 `region_id`、`text_block_id`、`image_id` 或 `evidence_id`。

在没有人工 gold labels 时，系统仍统计运行质量指标，包括 informative review 数、aspect 数、question 数、平均置信度、retrieval evidence 数量、evidence coverage、score drift、conflict risk、claim support rate、claim grounded rate、citation precision、citation contradiction rate，以及 text、image、mixed 的 route contribution。

## 5.6 自动化测试

自动化测试覆盖 API、数据集服务、评论服务、问题生成、索引后端、embedding 与 reranker、检索服务、分析服务、HTML 导出、manifest 评估、运行策略、运行进度、工作流脚本和多模态验证脚本。当前代码基线下执行：

```bash
.venv/bin/python -m pytest
```

结果为 166 项测试全部通过。该结果说明当前源码、提示词注册、schema、工作流脚本和评估服务在工程层面保持一致。
