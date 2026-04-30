# 6 结果与分析

## 6.1 端到端闭环结果

当前系统已经形成从原始商品目录到结构化 VOC 报告的端到端闭环。`run_workflow.py` 能够将数据概览、标准化、索引构建和分析串联为单商品流程；`validate_multimodal_runtime.py` 能够检查运行时是否启用真实多模态链路；`export_html_report.py` 能够将分析产物导出为可审查页面；`evaluate_manifests.py` 能够读取 run manifest 并计算评估指标。

这表明系统已经不再是若干独立脚本，而是一个以服务层、schema 和 artifact 为共同边界的分析框架。即使在 `--no-llm` 离线模式下，系统仍能输出同构的方面、问题、检索和报告对象，从而支持调试和回归测试。

## 6.2 测试结果

在当前代码基线下，完整测试套件共收集 166 项测试，全部通过。测试覆盖范围包括数据集扫描与标准化、评论抽取、问题生成、索引后端、embedding 和 reranker、检索服务、分析服务、HTML 导出、manifest 评估、运行策略、运行进度、工作流脚本和多模态运行态验证。

<a id="tab:test-results"></a>

| 验证对象 | 结果 | 说明 |
| --- | --- | --- |
| 自动化测试 | 166/166 通过 | 当前实现与测试断言一致 |
| API 层 | 通过 | dataset、index、reviews、analysis 路由可测 |
| 检索层 | 通过 | 本地索引、Qdrant 抽象、embedding、reranker 和召回逻辑可测 |
| 生成层 | 通过 | 问题生成、报告生成、归因、HTML 和 replay 相关逻辑可测 |
| 工作流脚本 | 通过 | run workflow、interactive workflow 和 runtime validation 可测 |

*Table 1. 当前代码基线下的系统验证结果。*

## 6.3 结构化产物分析

系统输出不是单段自然语言，而是一组可追踪对象。一次完整分析通常包含 extraction、question intents、questions、retrievals、retrieval quality、retrieval runtime、aggregates、report、trace、replay summary 和 artifact bundle。每个 retrieval 记录保留来源问题、来源方面、期望 evidence routes 和召回证据；每个召回证据保留文本块 ID、图片 ID、区域 ID、来源 section、语言、embedding score 和 rerank score。

这种结构带来两个结果。第一，报告可审查。strengths、weaknesses、controversies 和 suggestions 可以追踪到评论证据和商品证据。第二，错误可定位。若某条建议不可靠，开发者可以检查是评论抽取错误、问题规划过宽、检索候选缺失、reranker 排序错误，还是报告后处理校准不足。

## 6.4 问题规划层的作用

本文方法的核心主张是问题规划优于直接用评论原句检索。评论原句通常包含情绪表达、背景叙事和隐含假设，直接检索容易把商品证据空间拉宽。问题规划层将评论方面拆成多个可核验意图，例如商品文案是否直接支持、商品图片是否提供视觉证据、图文证据是否共同说明真实问题或预期偏差。

该机制使检索记录天然带有解释性。每个 retrieval 都可以回到 `source_aspect_id` 和 `source_question_id`，并且 `expected_evidence_routes` 指明该问题为什么需要文本证据、图像证据或二者结合。因此，问题规划不仅提升召回可控性，也为后续评估提供了 query-level 单元。

## 6.5 多模态证据路线分析

系统将文本证据和图像证据作为不同 route 处理。文本证据适合验证商品名称、类目、描述、规格或保修相关主张；图像证据适合验证结构、外观、颜色、局部细节和展示方式。图像 route 同时包含整图和默认局部区域，使系统能够在不依赖人工标注框的情况下进行初步区域级证据检索。

粗召回和重排的分离使系统能够兼顾覆盖和精度。Embedding 阶段负责扩大候选，reranker 阶段负责在候选中选择更相关证据。对于图像候选，多模态 reranker 可以直接观察原图或区域裁剪，从而减少仅靠代理文本判断图像相关性的风险。

## 6.6 评估接口结果

`ManifestEvaluationService` 已经支持两类评估。若运行产物包含人工检索标签，系统能够计算 Recall@K、MRR 和 NDCG；若没有人工标签，系统仍能计算结构化运行统计和 claim attribution 指标。后者包括 claim support rate、claim grounded rate、citation precision、citation contradiction rate 和 route contribution。

这一设计使当前系统具备从系统验证过渡到正式 benchmark 的接口。未来只需补充覆盖多品类、多问题和多证据类型的人工标签，即可在现有 manifest 评估框架中比较评论直召回、问题驱动召回、不同 embedding 后端和不同 reranker 后端。

## 6.7 当前结果边界

当前结果证明系统主链可运行、产物可审查、测试基线稳定，但仍不能等同于完整 benchmark 结论。本文尚未报告多品类冻结测试集上的统计显著性结果，也尚未系统比较不同检索策略的边际收益。因此，本节结果应被理解为系统方法验证，而不是最终性能评测。
