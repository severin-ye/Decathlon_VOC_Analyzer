# 4 方法

## 4.1 总体框架

本文提出的 Decathlon VOC Analyzer 将商品 VOC 分析形式化为一个证据驱动的多阶段推理过程。系统首先把商品页面中的文本、图像和评论组织为统一证据空间；随后在评论侧抽取方面级用户反馈；再通过问题规划将主观反馈转化为可执行的证据查询；最后在商品文本与商品图像之间执行多模态检索、重排和证据约束生成。与一步式大模型摘要不同，该框架将“用户表达了什么”“商品证据能否支持”“最终报告如何归因”拆分为可观察的中间环节。

本文将该框架抽象为四个逻辑层。第一层是商品证据层，负责构建商品文本、图片和局部视觉区域的结构化表示。第二层是 VOC 需求层，负责将评论转化为方面、观点、情感和场景。第三层是证据对齐层，负责把方面改写为具有明确模态路线的问题，并在商品证据空间中检索和重排候选。第四层是报告归因层，负责生成结构化洞察，并将报告主张映射回评论证据与商品证据。

[图1占位符：证据驱动多模态 VOC 分析总体框架图]

AI 绘图提示词：请绘制一张适合学术论文方法章节的系统框架图，风格简洁、扁平、现代，白色背景，蓝灰色主色调，少量橙色用于强调关键创新。图中从左到右展示四个主要逻辑层：第一层“Product Evidence Layer”，包含 product text、product images、image regions、reviews 四类输入对象；第二层“VOC Demand Modeling Layer”，包含 review filtering、rating-aware sampling、aspect extraction、aspect objects；第三层“Question-Guided Multimodal Retrieval Layer”，包含 question intent planning、text route retrieval、image route retrieval、reranking、language-balanced candidate pool；第四层“Evidence-Constrained Reporting Layer”，包含 aspect aggregation、structured report、claim attribution、evidence gaps、feedback/replay。请用箭头表示数据流，用虚线框表示可复用 artifacts 和 caches。图中不要出现具体文件路径、代码类名或品牌 Logo，强调“review aspects become evidence-seeking questions”和“claims are grounded back to product and review evidence”。图的整体比例适合论文单栏或双栏宽图，文字清晰，适合黑白打印也能辨认。

*图1. Decathlon VOC Analyzer 的总体框架。系统以商品证据包和评论方面为中间表示，通过问题规划连接主观 VOC 信号与多模态商品证据，并在报告阶段进行 claim 级归因。*

## 4.2 商品证据表示

商品页面通常同时包含标题、描述、类目、规格、图片和用户评论。如果这些信息在系统入口处被简单拼接为长文本，后续模型虽然能够生成摘要，却很难追踪某一结论的来源。为此，本文首先构建商品级证据包，将商品文本、商品图片、图片局部区域和评论记录表示为具有稳定标识的证据对象。

文本证据保留其来源字段，例如标题、描述或类目。图像证据不仅保留整图，还构造若干规则化局部区域，以便后续模型能够在没有人工标注框的情况下初步访问局部视觉信息。评论证据则保留评分、语言提示和原文片段，为后续抽样与方面抽取提供输入。该表示的目的不是在数据层完成全部语义理解，而是为后续检索、归因和评估建立统一对象边界。

## 4.3 评论方面建模

评论侧的核心任务是将自然语言反馈转化为方面级 VOC 单元。每个方面单元包含被评价的属性、情感倾向、观点描述、原文证据片段、使用场景和置信度。与整句级摘要相比，方面级表示能够同时支持统计聚合和证据检索：系统既可以计算某一属性的正负反馈分布，也可以围绕该属性生成后续证据查询。

为了避免有限评论预算被高星短评占据，本文在评论抽取前引入星级感知抽样。默认策略更重视低星评论，从而优先捕获产品改进中更有价值的问题反馈。同时，为保证系统在不同运行条件下可复现，方面抽取同时支持结构化 LLM 路径和启发式路径。前者提供更强语义理解能力，后者保证在外部模型不可用时仍可完成端到端验证。

## 4.4 从方面到问题的规划机制

本文的关键设计是引入“方面到问题”的中间规划层。评论方面往往仍然是主观表达，例如“容量小”“佩戴舒适”“设计吸引儿童”。若直接用这些短语或原始评论检索商品证据，查询通常过宽，且难以判断应检索文本还是图像。因此，系统为每个方面构造若干具有明确检索意图的问题。

这些问题覆盖三类证据需求：文本支持、视觉确认和跨模态解释。文本支持问题关注商品文案或规格是否直接支持评论观点；视觉确认问题关注商品图片是否呈现相关结构或外观；跨模态解释问题则尝试判断某一反馈更接近真实产品问题、页面呈现不足还是用户预期偏差。通过这种方式，评论中的主观体验被转化为可以由商品证据回答的检索任务。

[图2占位符：从评论方面到多模态证据查询的转换机制图]

AI 绘图提示词：请绘制一张论文机制图，展示“review aspect -> question intents -> route-aware retrieval -> evidence bundle”的转换过程。左侧放一个用户评论气泡，例如 “too small for travel documents”，下方抽取出 aspect object，包含 aspect、sentiment、opinion、evidence span、usage scene 五个字段。中间展示三个问题意图卡片：explicit text support、visual confirmation、cross-modal resolution，每张卡片生成一个自然语言 question。右侧分成两条检索路线：text route 指向 product title、description、specification snippets；image route 指向 whole product image、center crop、detail crop。两条路线进入 reranker，再合并为 evidence bundle。请使用流程箭头和编号 1 到 5 展示步骤，突出“question planning”是核心桥梁。视觉风格应像顶会论文中的方法示意图，不要使用真实商品照片，可用抽象背包/眼镜线稿图标，颜色使用蓝色表示文本证据、绿色表示图像证据、橙色表示问题规划。

*图2. 评论方面到证据查询的规划机制。方面对象并不直接进入检索，而是先被分解为具有不同证据意图的问题，再分别触发文本路线、图像路线或图文联合路线。*

## 4.5 多模态召回与重排

证据对齐层采用两阶段检索。第一阶段使用向量表示进行粗召回，以较低成本从商品文本和商品图像中获得候选证据。第二阶段使用重排模型对候选集合进行精排，以提高最终证据的相关性。文本证据和图像证据在召回阶段被分路线管理，但在重排和报告阶段被统一到同一商品证据空间中。

文本路线主要用于验证商品名称、类目、描述、规格和显式承诺。图像路线主要用于验证结构、外观、颜色、局部细节和页面呈现方式。对于图像候选，系统既可以对整图建模，也可以对规则化区域进行裁剪和编码。虽然这些区域尚不等价于语义 grounding，但它们为局部视觉证据进入 VOC 分析提供了低成本接口。

为避免某一路线或某一种语言的候选过度占据结果，召回后还会构建语言与路线均衡的候选池。最终证据选择不仅考虑相关性分数，也考虑是否覆盖问题所声明的证据路线。因此，一个跨模态问题应尽量同时获得文本证据和图像证据，而不是被单一路线候选完全替代。

## 4.6 证据约束报告与 claim 归因

报告生成阶段不把召回结果作为普通上下文直接交给模型总结，而是先对方面信号和检索证据进行聚合。聚合对象记录每个方面的出现频次、情感分布、代表评论、证据片段和检索覆盖情况。随后系统生成结构化报告，报告字段包括优势、缺点、争议点、适用场景、证据缺口和改进建议。

为了降低生成式报告的不可审查性，本文进一步引入 claim 级归因。报告中的主要主张会被映射到评论证据、商品文本证据、商品图像证据或二者的组合，并标记为支持、部分支持、未支持或冲突。若某一评论观点在当前商品证据中无法得到充分验证，系统倾向于输出证据缺口，而不是把该观点包装成确定结论。

[图3占位符：证据归因与评估闭环图]

AI 绘图提示词：请绘制一张论文风格的闭环图，主题是“evidence attribution and evaluation loop”。左侧为 retrieved evidence nodes，分为 review evidence、product text evidence、product image evidence 三组节点；中间为 structured report claims，包含 strength claim、weakness claim、suggestion claim、evidence gap claim；从证据节点到 claim 节点画有向连线，连线标签包括 supported、partial、unsupported、contradicted。右侧为 evaluation module，包含 retrieval metrics（Recall@K, MRR, NDCG）和 attribution metrics（claim support rate, citation precision, modality contribution）。底部画 feedback/replay loop，从 evaluation 和 human review 回到 question planning 与 report refinement。视觉风格应清晰、学术、无代码感，使用节点-边图结构，蓝色表示证据，紫色表示报告主张，红色表示 unsupported/evidence gap，绿色表示 supported，灰色虚线表示 replay loop。

*图3. 证据归因与评估闭环。报告主张被映射到评论、商品文本和商品图像证据；评估模块同时衡量检索质量和生成主张的证据支撑质量。*

## 4.7 可复现性与可解释性设计

本文方法的可复现性来自两个层面。第一，所有关键中间结果均被表示为结构化对象，包括商品证据、评论方面、问题、检索记录、报告主张和评估指标。第二，系统在运行过程中保留可复用的中间产物和缓存，使研究者可以固定前序阶段，只替换问题生成、检索或重排策略进行消融。

这种设计也提升了错误分析能力。当最终报告出现不可靠建议时，分析者可以沿链路回溯到评论抽样、方面抽取、问题规划、候选召回、重排排序、报告生成或归因校准中的具体阶段。相比黑盒式摘要，本文框架更适合用于人工审查、模型替换、检索消融和后续多品类评测。
