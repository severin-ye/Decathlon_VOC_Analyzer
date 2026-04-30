# 4 方法

## 4.1 总体架构

Decathlon VOC Analyzer 采用分阶段的证据驱动架构。系统主链路包括：数据集与商品证据标准化、评论建模与抽样、问题规划、多模态索引与召回、重排与缓存、报告生成与证据归因、工作流编排和评估。各阶段之间通过 Pydantic schema 传递对象，而不是传递无结构文本。

单商品工作流由 LangGraph 编排为四个节点：`overview`、`normalize`、`index` 和 `analyze`。`overview` 统计数据集规模与缺失文件；`normalize` 将目标商品转化为标准化证据包；`index` 为商品文本、图片和区域建立索引；`analyze` 执行评论抽取、问题生成、检索、重排、聚合、报告生成和产物落盘。该流程保证系统既可以通过 API 交互调用，也可以通过批处理脚本复现实验。

## 4.2 商品证据标准化

数据标准化模块以 `ProductEvidencePackage` 为核心对象。系统从每个商品目录读取 `product.json`、`reviews.json` 和 `images/`，将商品标题、描述和类目转化为 `TextEvidence`，将图片转化为 `ImageEvidence`，将评论转化为 `ReviewRecord`。每个证据对象都具有稳定 ID、来源字段和语言提示。

为了为局部视觉证据预留空间，系统对有效图片生成五类默认区域：`center_focus`、`upper_focus`、`lower_focus`、`left_focus` 和 `right_focus`。这些区域由相对比例转换为像素框，并被建模为 `ImageRegion`。当前区域并不等价于语义检测结果，但它使系统能够在没有人工标注框的情况下初步支持区域裁剪、局部 embedding 和图像重排。

标准化过程还会输出数据质量信息，包括商品数量、评论数量、图片数量、缺失 `product.json` 或 `reviews.json` 的商品，以及空评论数量。标准化产物写入 `02_outputs/1_normalized/`，后续所有模块优先复用该产物。

## 4.3 评论建模与抽样

评论建模模块将原始评论转化为 `ReviewAspect`。每个方面对象包含 `aspect`、`sentiment`、`opinion`、`evidence_span`、`usage_scene`、`confidence` 和 `extraction_mode`。系统首先清洗评论文本，过滤空评论、过短评论和低信息短评，例如 `ok`、`good`、`great` 等。

当设置 `max_reviews` 时，系统启用星级抽样。默认 profile 为 `problem_first`，其目标比例为 1 星 30%、2 星 25%、3 星 20%、4 星 15%、5 星 10%。如果某个星级样本不足，系统按配置的 fallback 顺序补位，并将目标数量、可用数量、实际选择数量、短缺数量和补位数量写入 `ReviewSamplingPlan`。

方面抽取支持 LLM 和 heuristic 两条路径。LLM 路径使用 Qwen 网关和结构化输出 schema；heuristic 路径使用关键词、评分和负向提示词识别容量、便携性、可用性、耐用性、价值价格、材料硬度等方面。抽取后，系统按评论 ID、方面、情感和证据片段去重，并将结果写入 `02_outputs/2_aspects/`。

## 4.4 问题规划

问题规划模块是本文方法的关键桥接层。系统不直接用评论方面或评论原句检索商品证据，而是先为每个 `ReviewAspect` 规划若干 `QuestionIntent`，再生成 `RetrievalQuestion`。默认意图包括：`explicit_support`、`visual_confirmation`、`cross_modal_resolution`、`spec_check` 和 `visual_detail`。

每个问题都包含来源评论、来源方面、自然语言问题、生成理由、期望证据路线和置信度。`expected_evidence_routes` 明确指定检索应使用 `text`、`image` 或二者结合。该字段使后续召回具备 route-aware 能力，也使报告归因能够区分文本支持、图像支持和混合支持。

问题生成同样支持 LLM 和 heuristic 两条路径。LLM 路径将方面、观点、证据片段、使用场景、情感、意图类型、禁止概念和具体性边界输入提示词；heuristic 路径使用固定模板生成可检索问题。问题缓存签名绑定 prompt variant、prompt digest、方面 digest、问题数量、模型和 API 配置，避免提示词变化后误用旧问题。

## 4.5 多模态索引与召回

索引模块将商品证据转化为 `IndexedEvidence`。文本证据 route 为 `text`，图像整图和区域 route 为 `image`。文本 embedding 可使用 `text-embedding-v4` API 或本地 Qwen3 embedding；图像 embedding 默认使用 `openai/clip-vit-base-patch32`。当外部能力不可用且运行策略允许降级时，系统可退回 hash embedding 或代理文本 embedding。

索引后端通过 `IndexBackend` 抽象统一管理。`LocalIndexBackend` 将索引快照写入本地 JSON 文件，并在搜索时计算 query 向量与 evidence 向量的相似度；`QdrantIndexBackend` 为文本和图像分别创建 collection，并用 `product_id`、`category_slug` 和 `route` 过滤候选。

召回过程针对每个问题执行。系统首先按 route 进行 embedding 粗召回，并使用过采样保留较宽候选集合；随后按语言和 route 构建均衡候选池，避免单一语言或单一路线垄断候选；最后交给 reranker 精排，并通过 route coverage 规则选择最终证据。

## 4.6 重排、缓存与运行策略

重排模块将文本候选和图像候选分开处理。文本候选支持本地 Qwen3 reranker、DashScope `gte-rerank-v2` API 和启发式排序；图像候选支持本地 Qwen3-VL、多模态 Qwen-VL API、文本 reranker 退路和启发式排序。

在多模态图像重排中，系统会读取商品图片，若候选为区域证据则按 `region_box` 裁剪，然后压缩为 JPEG data URL 输入 Qwen-VL，并要求模型返回严格 JSON 评分。这使图像候选的最终排序能够基于真实视觉内容，而不是只依赖图片路径或代理文本。

系统将 query embedding 和 rerank 结果写入磁盘缓存。缓存签名绑定 route、query、backend、model、base URL 和候选 digest，因此相同配置可以复用结果，不同模型或候选集不会串写。运行策略由 `RuntimeExecutionPolicy` 控制：开发时可允许降级，正式实验时可禁止静默降级，满血模式下还会检查 Qdrant、本地 embedding、本地 reranker 和本地多模态 reranker 等前置条件。

## 4.7 报告生成、归因与回放

报告生成模块首先对方面进行聚合，形成每个 aspect 的情感分布、代表评论、证据片段和平均置信度。随后系统基于方面聚合和检索结果生成结构化报告，字段包括 strengths、weaknesses、controversies、evidence gaps、applicable scenes 和 suggestions。LLM 可用时进入结构化生成路径；不可用时使用 heuristic 路径构造同 schema 报告。

报告生成后，`ReportRefinementService` 会对洞察和建议去重，依据支持证据类型重新校准 owner 与 evidence level，并修正“声称有图像支持但实际未检索到图像证据”等不一致表述。随后系统构建 `claim_attributions`，将报告主张映射到评论、商品文本、商品图片或区域证据，并标记 supported、partial、unsupported 或 contradicted。

系统还支持 feedback/replay 侧边车。若存在上一轮反馈或回放产物，新分析可以读取这些上下文，将持续存在的问题、已修正问题和回放摘要并入报告与 trace。最终产物包括 analysis JSON、feedback sidecar、replay sidecar、HTML 报告和 run manifest。

## 4.8 Schema 与可解释性

本文系统的可解释性来自结构化中间表示。`schemas/` 目录定义了数据、评论、索引、分析、问题缓存和检索缓存对象。最终 `ProductAnalysisResponse` 同时包含 extraction、question intents、questions、retrievals、retrieval quality、retrieval runtime、aggregates、report、trace、replay summary、artifact bundle 和 warnings。

这种设计使错误定位可以分解到具体阶段。如果最终建议不合理，可以检查评论抽样是否偏置、方面抽取是否错误、问题是否过宽、召回是否缺证据、reranker 是否误排，或报告后处理是否校准不足。与黑盒摘要相比，这种对象化链路更适合人工审查、消融实验和后续模型迭代。
