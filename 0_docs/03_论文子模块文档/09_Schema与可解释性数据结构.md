# Schema 与可解释性数据结构模块

## 模块定位

本模块对应 `schemas/` 目录，包括 `dataset.py`、`review.py`、`index.py`、`analysis.py`、`retrieval_cache.py` 和 `question_cache.py`。它定义了项目中所有核心输入、输出、中间产物和缓存签名。

论文中可将该模块定义为“结构化中间表示层”。它是系统创新的重要组成部分，因为本项目的可解释性、可复现性和可评估性都依赖这些 schema。

## 主要创新点

1. 全链路对象统一：从 `ProductEvidencePackage` 到 `ReviewAspect`、`RetrievalQuestion`、`RetrievalRecord`、`ProductAnalysisReport`，系统为每个阶段都定义了显式对象，而不是在各模块之间传递无结构 dict。
2. 证据对象可追踪：文本、图片、区域、评论、方面、问题、检索记录和报告主张都有独立 ID，可在报告和评估中相互引用。
3. 生成结果可评估：报告 schema 不只包含自然语言 answer，还包含 strengths、weaknesses、controversies、evidence gaps、suggestions、claim attributions 和 confidence breakdown。
4. 缓存签名 schema 化：query embedding、rerank 和 question generation 的缓存签名被建模为独立 schema，降低缓存误用风险。
5. 运行 profile 与质量指标入库：`RetrievalRuntimeProfile` 和 `RetrievalQualityMetrics` 让分析产物携带模型后端、证据覆盖率、分数漂移、冲突风险等信息，方便实验统计。

## 具体实现

数据层 schema 定义商品目录、文本证据、图像证据、图像区域、评论记录、商品证据包、数据概览和标准化统计。评论层 schema 定义评论输入、预处理评论、方面对象、抽样计划和抽取响应。

索引层 schema 定义 `IndexedEvidence`、`ProductIndexSnapshot`、`IndexBuildRequest`、`IndexBuildResponse` 和 `IndexOverview`。其中 `IndexedEvidence` 同时保存 route、doc_type、source_section、image_path、region_box、content_original、content_normalized、language、vector 和 score，是检索层最核心的证据对象。

分析层 schema 覆盖范围最大，包括 question intent、retrieval question、retrieved evidence、retrieval record、aspect aggregate、insight item、improvement suggestion、evidence node、claim attribution、product/customer impression、aspect relation、process trace、replay summary、analysis artifact bundle 和最终 response。

缓存 schema 则定义 query embedding 和 rerank 的签名字段。例如 rerank 签名包含 route、query、use_llm、backend_kind、candidate_count、candidate_digest、base_url、reranker_model 和 multimodal_reranker_model，使缓存与具体运行条件绑定。

## 与文献思路的关系

RAG 研究通常关注检索和生成，但在工程系统中，中间表示决定了证据是否可追踪 [1]。本项目将 schema 作为方法核心，而不是只作为 API 类型定义。

结构化输出研究指出，大模型在复杂结构生成中容易出现格式错误或字段漂移 [2]。本项目通过 Pydantic schema 约束 LLM 产物，并在必要时进行后处理补全。

可解释 AI 研究强调模型结论应能追踪到输入证据 [3]。本项目通过 ID 化证据节点和 claim attribution 实现从报告主张到商品证据和评论证据的追踪。

## 可写入论文的表述

本文将结构化 schema 作为系统方法的核心约束。所有关键中间结果均以可验证对象表示，包括商品证据、评论方面、检索问题、召回证据、报告洞察和 claim 归因。该设计使最终自然语言报告不再是不可拆解文本，而是可追踪、可缓存、可复用和可评估的结构化分析产物。

## 参考文献

[1] Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020.

[2] Liu, Y. et al. Are LLMs Good at Structured Outputs? Information Processing & Management, 2024.

[3] Gao, L. et al. RARR: Researching and Revising What Language Models Say, Using Language Models. ACL, 2023.
