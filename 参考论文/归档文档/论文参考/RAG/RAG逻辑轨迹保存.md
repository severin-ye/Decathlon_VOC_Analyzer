# 微软 Graph RAG 查询

**User:**   
**Created:**   
**Updated:**   
**Exported:** 3/19/2026 11:56:53  
**Link:** [https://chatgpt.com/share/69625ed7-5270-8002-ab0b-2083ec4d7080](https://chatgpt.com/share/69625ed7-5270-8002-ab0b-2083ec4d7080)  

## Prompt:
微软的graph rag 在执行询问时是如何查询知识图谱和社区报告的?
我应该怎么样将整个逻辑链条保存下来? (每一个子阶段的输入和输出)

## Response:
请问您是想了解微软 Graph RAG 在执行特定任务时的内部工作机制（例如它查询知识图谱和社区报告的顺序和方法），还是希望获得如何在实际开发中复现这种逻辑链的操作指南？另外，请问您使用的是微软开源实现，还是在 Microsoft Azure AI Studio 上构建的服务？

## Prompt:
我想要知道这个是内部工作机制。
我特别需要你详细的给我讲一讲。在这个回答的过程中，大模型具体参与了哪些环节？都做了哪些工作？
使用的是微软开源实现

## Response:
明白了。我将为你详细调研微软开源 Graph RAG 在查询知识图谱和社区报告时的内部机制，特别是大模型在各个阶段的参与角色和所执行的任务。我也会涵盖如何保存整个推理链条，包括每个子阶段的输入输出。  
完成后我会告诉你，期间你可以随时继续提问或补充需求。

## Prompt:
GraphRAG体系概览
============

GraphRAG（Graph-based Retrieval-Augmented Generation）是微软开源的一套基于知识图谱的检索增强生成系统。它首先用大型语言模型（LLM）从输入文本中提取实体、关系和断言，构建起一个结构化的**知识图谱**，并在此基础上进行社区（cluster）划分和摘要生成[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=Retrieval,an%20enterprise%E2%80%99s%20proprietary%20research%2C%20business)。查询时，GraphRAG将这些结构化图谱和社区摘要作为上下文材料提供给LLM，从而在回答问题时既能利用细粒度的实体关系信息，又能覆盖整个数据集的宏观主题。与传统基于向量检索的RAG不同，GraphRAG利用图和社区结构有效“连接信息碎片”，在回答复杂推理问题时能显著提高答案完整度和准确性[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=Retrieval,an%20enterprise%E2%80%99s%20proprietary%20research%2C%20business)[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Whole%20Dataset%20Reasoning)。

索引阶段：知识图谱与社区摘要构建
================

1.  **文本切分（Text Slicing）**：将原始语料切分为多个文本单元（TextUnit）供后续分析使用，并作为引用依据[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)。
2.  **实体与关系抽取**：使用LLM遍历整个语料，从中识别并提取**实体（节点）**、\*\*实体间关系（边）\*\*和关键声明（covariates）等要素。这一步实际上由预设好的提示（prompt）驱动LLM生成结构化数据，将无结构的文本信息转化为图谱中的元素[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=Retrieval,an%20enterprise%E2%80%99s%20proprietary%20research%2C%20business)。
3.  **知识图谱构建**：根据上一步提取的实体和关系构建知识图谱，每个节点代表一个实体或概念，节点大小可表示其度（关系数量），边表示实体之间的联系[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。
4.  **社区检测与摘要**：在构建好的图谱上应用图聚类算法（如Leiden算法）进行自下而上的社区检测，将实体划分为若干语义紧密的社区[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Whole%20Dataset%20Reasoning)。对于每个社区，LLM生成该社区及其元素的摘要报告，从整体上概括该团体的主题和关键信息。这些社区摘要在查询时可用来提供宏观语境[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Whole%20Dataset%20Reasoning)。
5.  **结果输出**：索引完成后，系统会输出一个索引项目文件夹，包括Parquet格式的图谱数据、聚类信息、社区摘要等[microsoft.github.io](https://microsoft.github.io/graphrag/get_started/#:~:text=This%20process%20will%20take%20some,a%20series%20of%20parquet%20files)。这些文件记录了每一步的输入输出，可用于审计和复现。

查询阶段：多模式检索与推理
=============

GraphRAG查询引擎提供多种检索模式，根据问题类型采取不同策略[microsoft.github.io](https://microsoft.github.io/graphrag/query/overview/#:~:text=Query%20Engine)[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)：

*   **本地搜索（Local Search）**：适用于聚焦某个实体或具体问题的查询。首先使用问句（及可选的对话上下文）计算其向量表示，与图谱中实体描述的向量进行匹配，识别出与问句语义相关的实体[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。然后以这些实体为切入点，从知识图谱和原始文本中检索相关信息：包括与之相连的实体、关系、协变量（实体断言）和关联的原始文本块，以及这些实体所属社区的摘要报告[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。所有候选信息都经打分过滤，选出最相关的一部分装入LLM的上下文窗口中，最后由LLM基于这些上下文生成回答[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)。
*   **全局搜索（Global Search）**：用于需要从整体数据集中寻找主题或观点的提问。全局搜索采用图谱社区摘要的“MapReduce”方案[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)。具体地，针对用户查询，每个社区摘要被分割成固定长度的文本块（“Map”阶段），LLM对每块内容分别生成中间答案（通常是要点列表并附上重要性评分）[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)。然后系统从所有中间答案中筛选出最重要的要点进行合并，作为最终回答的上下文，以LLM生成完整回答[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=Retrieval,an%20enterprise%E2%80%99s%20proprietary%20research%2C%20business)。这样，全局搜索能够综合利用预先生成的语义簇摘要来回答“全局感知”问题，如“本文的主要主题是什么”。
*   **DRIFT搜索（DRIFT Search）**：结合了本地搜索与社区信息的新方法[microsoft.github.io](https://microsoft.github.io/graphrag/query/overview/#:~:text=DRIFT%20Search)。它在本地检索的基础上，引入社区摘要作为辅助，从而扩展查询的检索范围。简而言之，先像本地搜索一样找出相关实体，然后使用该实体所在社区的摘要生成进一步的问题或线索，反过来指导更深层的检索。DRIFT搜索通过将社区洞见融入本地查询，可获得更丰富的上下文信息，有助于回答需要更广泛背景的复杂问题[microsoft.github.io](https://microsoft.github.io/graphrag/query/overview/#:~:text=DRIFT%20Search)。
*   **基本搜索（Basic Search）**：GraphRAG还提供了一个简单的向量RAG模式，可按文本块相似度检索内容[microsoft.github.io](https://microsoft.github.io/graphrag/query/overview/#:~:text=Basic%20Search)。用户可指定返回最相关的前`k`个文本单元，把它们作为LLM上下文。这种模式主要用于与GraphRAG复杂模式进行对比，或处理不需要图结构的简单问题[microsoft.github.io](https://microsoft.github.io/graphrag/query/overview/#:~:text=Basic%20Search)。
*   **问题生成（Question Generation）**：GraphRAG还支持基于当前已提问列表自动生成后续候选问题。它使用与本地搜索相同的上下文构建流程，从知识图谱和文本中提取相关实体、关系、协变量和社区摘要，然后将这些信息打包给LLM，让其输出与数据集主题相关的后续问题[microsoft.github.io](https://microsoft.github.io/graphrag/query/question_generation/#:~:text=Methodology)[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。这在对话系统中用于提出“下一个问题”或引导用户更深入探索数据时非常有用。

大语言模型（LLM）的角色
=============

在GraphRAG的整个流程中，LLM发挥了关键作用：

*   **索引阶段**：LLM负责**实体/关系抽取**和**摘要生成**。通过精心设计的提示，LLM从文本中“读出”各种实体和关系，生成图谱数据；同时对各图社区及其组成节点生成自然语言摘要[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。
*   **查询阶段**：LLM主要用于**语义匹配**和**答案生成**。在本地搜索中，LLM被调用在最后阶段，根据提供的实体相关文本上下文生成答案；在全局搜索中，LLM在“映射”阶段对社区摘要块生成要点式响应（列表+评分），在“归约”阶段根据筛选出的要点再次生成综合回答[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)。此外，在DRIFT搜索或问题生成模块，LLM同样用于根据提取的图谱信息生成查询转换或候选问题。总之，LLM接收预先检索到的结构化（图谱）和非结构化（文本）上下文，输出语言化的答案或问题[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。
*   **引用与溯源**：值得注意的是，GraphRAG的答案通常带有溯源信息（如引用实体/关系ID、链接到原始文档）[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=In%20comparison%2C%20the%20GraphRAG%20approach,relationship%20that%20exists%20between%20the)。这意味着生成的回答不仅给出了结论，还指明了支持该结论的图谱节点和文本来源，有助于审查答案的正确性和逻辑。

可追踪、可复现的工作流
===========

要实现“可追踪”、“可复现”的流程，需要保存每个子阶段的输入输出和调用细节。GraphRAG自身支持如下方式：

*   **索引输出**：索引阶段输出的Parquet文件包含了细粒度的中间数据（实体列表、边列表、社区划分、摘要文本等）[microsoft.github.io](https://microsoft.github.io/graphrag/get_started/#:~:text=This%20process%20will%20take%20some,a%20series%20of%20parquet%20files)。保存这些文件即可重现知识图谱构建过程。
*   **日志与回调**：GraphRAG的查询模块（如LocalSearch、GlobalSearch）接受回调（callbacks）参数，可在LLM执行时捕获完整的请求与响应。可利用这些回调记录每个Prompt、LLM参数、以及模型返回内容，做到问答过程的可审计。例如，可定义回调函数将所有上下文和回答写入日志。
*   **请求参数记录**：在每次调用GraphRAG查询时，应记录所用模块（本地/全局/DRIFT）、查询类型、上下文构建器参数（如MaxTokens、Prompt模板等）。GraphRAG配置文件和命令行也可明确指定这些参数，并可将运行记录留存。
*   **回答溯源**：GraphRAG生成的回答中自带实体/关系的参考ID，这些ID可以对应回知识图谱中的元素并进一步追踪到具体文本来源[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=In%20comparison%2C%20the%20GraphRAG%20approach,relationship%20that%20exists%20between%20the)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)。用户可结合这些引用，从回答处回溯到支持该回答的原始信息，实现输出结果的透明化。
*   **框架支持**：此外，可以借助微软的其他工具栈构建更加结构化的流程。例如，用**Semantic Kernel**将GraphRAG步骤作为技能（skill）或记忆（memory）集成，将每次查询视为函数调用并自动记录上下文；用**Microsoft Guidance**设计多阶段Prompt引导，每步交互输出保存在聊天记录中；或用**AutoGen/GRIT**等多Agent框架管理GraphRAG组件，自动处理任务调用并输出链路。总之，通过细粒度的日志与版本控制，可以保证GraphRAG整个检索-推理过程的可追溯性和可重放性。

集成与参考
=====

GraphRAG的实现与多种微软开源框架可以集成：例如，可将其作为LLM技能调用到Semantic Kernel中，或配合Azure AI Search等系统使用。同时，GraphRAG遵循可定制的配置和模块化设计，可在不同语言平台（Python、.NET）中部署。其官方文档、论文和代码库提供了详尽的配置说明和示例[microsoft.github.io](https://microsoft.github.io/graphrag/get_started/#:~:text=This%20process%20will%20take%20some,a%20series%20of%20parquet%20files)[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)。有关GraphRAG内部机制的详细描述，可参见Microsoft Research博客和论文[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=Retrieval,an%20enterprise%E2%80%99s%20proprietary%20research%2C%20business)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)；开源代码库提供了查询引擎（Local/Global/DRIFT/Basic Search）、上下文构建器、Prompt模板等模块的源码实现和说明（见GitHub链接）。

**参考资料：** GraphRAG官方文档[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)[microsoft.github.io](https://microsoft.github.io/graphrag/query/local_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)[microsoft.github.io](https://microsoft.github.io/graphrag/query/overview/#:~:text=Basic%20Search)；Microsoft Research博客和论文[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=Retrieval,an%20enterprise%E2%80%99s%20proprietary%20research%2C%20business)[microsoft.com](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=,window%20when%20answering%20a%20question)；GraphRAG代码仓库及示例[microsoft.github.io](https://microsoft.github.io/graphrag/get_started/#:~:text=This%20process%20will%20take%20some,a%20series%20of%20parquet%20files)[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)。

## Response:
\* \*\*查询阶段\*\*：LLM主要用于\*\*语义匹配\*\*和\*\*答案生成\*\*。在本地搜索中，LLM被调用在最后阶段，根据提供的实体相关文本上下文生成答案；在全局搜索中，LLM在“映射”阶段对社区摘要块生成要点式响应（列表+评分），在“归约”阶段根据筛选出的要点再次生成综合回答\[microsoft.github.io\](https://microsoft.github.io/graphrag/query/global\_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)。此外，在DRIFT搜索或问题生成模块，LLM同样用于根据提取的图谱信息生成查询转换或候选问题。总之，LLM接收预先检索到的结构化（图谱）和非结构化（文本）上下文，输出语言化的答案或问题\[microsoft.github.io\](https://microsoft.github.io/graphrag/query/global\_search/#:~:text=Given%20a%20user%20query%20and%2C,to%20generate%20the%20final%20response)\[microsoft.github.io\](https://microsoft.github.io/graphrag/query/local\_search/#:~:text=Given%20a%20user%20query%20and%2C,response%20to%20the%20user%20query)。 \* \*\*引用与溯源\*\*：值得注意的是，GraphRAG的答案通常带有溯源信息（如引用实体/关系ID、链接到原始文档）\[microsoft.com\](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/#:~:text=In%20comparison%2C%20the%20GraphRAG%20approach,relationship%20that%20exists%20between%20the)。这意味着生成的回答不仅给出了结论，还指明了支持该结论的图谱节点和文本来源，有助于审查答案的正确性和逻辑。

我只关心这个部分。

## Prompt:
好，这里我**只聚焦你点名的这一段：GraphRAG 查询阶段中，LLM 是如何参与语义匹配、社区报告 Map-Reduce、答案生成，以及“引用 / 溯源”是如何形成的**。  
不讲背景、不讲索引、不讲社区怎么来的，只讲\*\*“一次 query 进来以后，系统内部到底发生了什么”**，而且是**微软开源 GraphRAG 的真实机制\*\*。

* * *

一、先给你一个“一句话总览”（非常重要）
--------------------

> **GraphRAG 在查询阶段，LLM 并不是用来“搜索”的，而是用来：  
> ① 对已经被选中的上下文做语义理解  
> ② 在受控上下文内进行多阶段总结与归并  
> ③ 输出带来源锚点（entity / text unit id）的自然语言答案**

**检索 ≠ LLM；LLM = 结构化上下文 → 语言化推理与聚合器**

* * *

二、Local Search：LLM 在哪里参与？做了什么？
------------------------------

### 1️⃣ LLM **不参与**的部分（很多人误解）

在 **Local Search** 中，下面这些 **不是 LLM 做的**：

*   query → embedding
*   embedding → entity 相似度匹配
*   entity → 邻接实体 / 关系 / text units 抽取
*   relevance 打分、截断、top-k

👉 这些全部是**向量计算 + 图遍历 + 规则过滤**  
👉 **LLM 此时完全没被调用**

* * *

### 2️⃣ LLM 第一次真正出场：**“上下文 → 回答”**

当 Local Search 构造完一个 **Context Bundle** 后，才调用 LLM。

这个 Context Bundle 包含 **四类信息**（顺序固定）：

```
[1] Relevant Entities
[2] Relationships among entities
[3] Claims / Covariates
[4] Supporting Text Units (原文片段)
```

然后：

*   这些内容被 **序列化为 prompt**
*   明确要求 LLM：
    *   **只能基于提供内容回答**
    *   **回答时标注引用来源（IDs）**

### 3️⃣ LLM 在 Local Search 中的“职责”

> **LLM = 受控证据下的语言推理器（Evidence-Bound Reasoner）**

具体做的事只有三件：

1.  **跨多实体、多关系的信息整合**
2.  **将图结构 + 原文碎片 → 连贯自然语言**
3.  **在句子级别标注引用来源**

⚠️ 注意：  
LLM **没有权限**：

*   自己扩展事实
*   自己引入新实体
*   自己“想当然”补背景

* * *

三、Global Search：Map-Reduce 中 LLM 的真实工作模式
----------------------------------------

这是你现在做 **社区报告 + 幻觉检测** 时最关键的部分。

* * *

### 🔹 Global Search 的核心思想

> **不让 LLM 一次性读全图，而是：  
> 多次、局部、并行 → 再汇总**

* * *

### 1️⃣ Map 阶段：LLM 被“批量调用”

对 **每一个社区报告（Community Report）**：

*   把 report 切成若干 chunks
*   **每个 chunk 独立调用一次 LLM**

#### LLM 在 Map 阶段的输入

```
[User Query]
+
[One Community Report Chunk]
```

#### LLM 在 Map 阶段的输出（严格结构）

```
{
  "points": [
    {
      "statement": "...",
      "importance": 0.82,
      "supporting_entities": ["E12", "E45"],
      "supporting_text_units": ["T334", "T335"]
    }
  ]
}
```

📌 关键点：

*   不是直接“回答问题”
*   而是 **提炼“可能相关的候选事实点”**
*   每条都有：
    *   重要性评分
    *   可追溯的实体 / 文本 ID

👉 **这是 GraphRAG 引用可解释性的根基**

* * *

### 2️⃣ Reduce 阶段：LLM 第二次登场（汇总器）

系统做完这几步 **后**，才再次调用 LLM：

1.  收集所有 Map 输出
2.  按 importance 排序
3.  截断到 token budget 内
4.  构造一个 **“高密度事实集合”**

然后：

#### Reduce 阶段的 LLM 输入

```
[User Query]
+
[Top-N Structured Fact Points from all communities]
```

#### LLM 的任务（非常明确）

> **不是再“检索”，而是：  
> 在已确认事实点集合中 → 生成最终叙述**

它做的是：

*   去重
*   合并
*   排序
*   语言组织

📌 **LLM 此时已经被“剥夺了幻想空间”**

* * *

四、DRIFT Search：LLM 的“问题生成”而非“答案生成”
----------------------------------

你如果关注 **推理深度扩展**，DRIFT 非常关键。

在 DRIFT 中，LLM 的角色是：

> **“基于当前证据，提出下一个更有信息增益的问题”**

流程是：

1.  Local Search 找到核心实体
2.  社区摘要被加载
3.  LLM 被要求输出：

```
Given what we know, what follow-up question would reveal missing but important information?
```

📌 **注意**：  
LLM 在 DRIFT 中：

*   ❌ 不给最终答案
*   ✅ 只生成 **query transformation / query expansion**

* * *

五、引用（Citation）与溯源是如何“自然出现”的？
----------------------------

这是 GraphRAG 与普通 RAG 最大的结构差异。

* * *

### 1️⃣ 引用不是“事后补”的

GraphRAG 的 prompt **在一开始就强制要求**：

> Every statement MUST be supported by:
> 
> *   entity\_id
> *   relationship\_id (optional)
> *   text\_unit\_id
>     

* * *

### 2️⃣ 为什么 LLM 能做到“可引用”？

因为：

*   LLM 看到的上下文 **本身就是带 ID 的**
*   例如：

```
[E23] Diabetes Mellitus
[T991] "The patient was diagnosed with diabetes in 2018..."
```

LLM **只是复用已有锚点**，并没有“发明引用”。

* * *

### 3️⃣ 这对你做幻觉检测意味着什么？

这点非常重要，直接对你有用：

你可以做到：

*   **句子级 hallucination 判断**
*   **实体级冲突检测**
*   **文本证据级一致性验证**

因为你能明确知道：

> 这句话 → 用了哪些实体 → 来自哪些原始证据

* * *

六、把这一整段“逻辑链”完整保存下来，你应该存什么？
--------------------------

你问的是**工程级可追踪性**，不是概念。

### 对每一次 query，至少存这 6 组东西：

#### ① Query 原文 + Query embedding

#### ② 检索阶段产物

*   matched entity ids
*   matched relationship ids
*   selected text unit ids
*   community ids

#### ③ Context Builder 输出（LLM 输入前）

> **这是最关键的证据快照**

#### ④ Map 阶段 LLM 原始输出（JSON）

#### ⑤ Reduce 阶段 LLM 原始输出

#### ⑥ 最终回答 + citation map

📌 **不要只存最终回答，那是最低价值信息**

* * *

七、一句话总结（给你压缩成“研究级表述”）
---------------------

> 在微软开源 GraphRAG 中，  
> **LLM 并不承担检索或事实发现角色，而是作为一个受控的语义聚合器（constrained semantic aggregator）**，  
> 它仅在结构化上下文已确定的前提下执行多阶段总结、排序与语言生成，  
> 并通过实体与文本单元 ID 实现天然的可引用与可审计推理路径。

* * *

如果你愿意，**下一步我可以直接帮你**：

*   用你现在的 **GraphRAG output 目录**
*   设计一个 **“Query Trace Schema（JSON）”**
*   直接对齐你后续要做的 **幻觉检测 / 错误注入 / 对比学习**

你只要说一句：  
👉「按我现在的 GraphRAG 项目结构来」

## Response:
\### 2️⃣ LLM 第一次真正出场：\*\*“上下文 → 回答”\*\* 当 Local Search 构造完一个 \*\*Context Bundle\*\* 后，才调用 LLM。 这个 Context Bundle 包含 \*\*四类信息\*\*（顺序固定）： css 复制代码 \`\[1\] Relevant Entities \[2\] Relationships among entities \[3\] Claims / Covariates \[4\] Supporting Text Units (原文片段)\` 然后： \* 这些内容被 \*\*序列化为 prompt\*\* \* 明确要求 LLM： \* \*\*只能基于提供内容回答\*\* \* \*\*回答时标注引用来源（IDs）\*\* ### 3️⃣ LLM 在 Local Search 中的“职责” > \*\*LLM = 受控证据下的语言推理器（Evidence-Bound Reasoner）\*\* 具体做的事只有三件： 1. \*\*跨多实体、多关系的信息整合\*\* 2. \*\*将图结构 + 原文碎片 → 连贯自然语言\*\* 3. \*\*在句子级别标注引用来源\*\* ⚠️ 注意： LLM \*\*没有权限\*\*： \* 自己扩展事实 \* 自己引入新实体 \* 自己“想当然”补背景

所以是根据一个已经组织好的上下文进行一次性的回答，对不对？

## Prompt:
**简短结论：是的，但要加一个非常关键的限定条件。**

> **在微软开源 GraphRAG 的 Local Search / Reduce 阶段中，  
> LLM 确实是在“一个已经组织好的上下文（Context Bundle）上，进行一次性的回答生成”。**

下面我用**工程视角**把这句话拆清楚，避免产生误解。

* * *

一、你的理解在“机制层面”是正确的
-----------------

在 **Local Search（以及 Global Search 的 Reduce 阶段）** 中，真实执行逻辑是：

1.  **系统先完成所有检索与筛选**
    *   实体匹配
    *   图遍历
    *   文本单元筛选
    *   社区报告选择
    *   relevance / importance 截断
2.  **构造一个“最终上下文快照（Final Context Snapshot）”**
    *   内容顺序、格式、token 上限全部确定
    *   这是一个**不可再变的输入**
3.  **LLM 只被调用一次**
    *   输入：这个 Context Snapshot + 用户问题
    *   输出：最终回答（带引用）

👉 **LLM 在这个阶段不会再请求更多信息，也不会回头“再查一次图”**

所以你说的这句话在技术上是对的：

> **“根据一个已经组织好的上下文进行一次性的回答”**

* * *

二、但有一个非常重要的“不是你以为的那种一次性”⚠️
--------------------------

### ❌ 错误理解（很多人会掉坑里）

> LLM = 看一眼上下文 → 自由发挥 → 回答

**GraphRAG 不是这样用 LLM 的。**

* * *

### ✅ 正确理解（GraphRAG 的真实约束）

> **LLM = 在一个“强约束、结构化、带 ID 的上下文中”，  
> 执行一次性的、不可扩展的语言推理**

这个“一次性”有 4 个硬限制：

1.  **上下文是“证据闭集（closed evidence set）”**
    *   没有外部知识
    *   没有常识补全
    *   没有世界模型调用
2.  **LLM 不允许生成上下文中不存在的事实**
    *   Prompt 明确写死
    *   输出必须能回指 entity / text\_unit
3.  **LLM 不参与任何检索或决策**
    *   不选实体
    *   不选社区
    *   不决定 relevance
4.  **LLM 不能“多轮反思”**
    *   没有 chain-of-thought loop
    *   没有 self-refine
    *   没有 tool-calling

👉 所以这是一个\*\*“单次、受控、不可扩展”的生成调用\*\*

* * *

三、用一句“系统级准确表述”帮你定型
------------------

你之后写论文 / 设计系统，可以直接用这一句话：

> In Microsoft GraphRAG, the LLM is invoked **only after a fully constructed and fixed evidence context is prepared**, and performs **a single-pass, constrained generation** over this context, without any capability to retrieve, expand, or revise the evidence set.

如果用中文、偏研究口径一点：

> 在 GraphRAG 中，大模型仅在上下文构建完成后被调用一次，  
> 其角色是对一个**已冻结的证据集合**进行受约束的语义整合与语言生成，  
> 而非参与检索、推理路径选择或事实扩展。

* * *

四、这件事为什么对你现在的研究**非常关键**
-----------------------

结合你正在做的事情（**医学出院小结、幻觉检测、错误合成**）：

### 1️⃣ 你可以非常明确地区分责任

*   ❌ 幻觉 ≠ LLM“乱编”
*   ✅ 幻觉来源可以精确归因：
    *   Context 构建阶段（漏证据 / 错证据）
    *   Map 阶段摘要偏移
    *   Reduce 阶段聚合冲突

### 2️⃣ 你可以做“上下文级别”的对照实验

因为：

*   **同一个 Context**
*   **不同 LLM**
*   **输出差异 = 纯生成偏差**

或者：

*   **同一个 Query**
*   **轻微改 Context**
*   **输出变化 = 证据敏感性**

这是普通 RAG 很难做到的。

* * *

五、最终一句话回答你的问题（不绕）
-----------------

> **是的。**  
> 在微软开源 GraphRAG 中，  
> **LLM 的确是在一个已经完整组织、筛选并冻结的上下文之上，  
> 进行一次性的回答生成；  
> 且该生成过程是强约束、不可扩展、不可再检索的。**

如果你下一步想做的是：  
👉 **“把这个 Context Snapshot 作为一等公民存下来，用于 hallucination 判定 / 错误注入 / 对比学习”**

那你现在的理解，**是完全站在正确起点上的**。

## Response:
我应该如何读取到这个  Context Snapshot

## Prompt:
已思考 26s

可以。\*\*在微软开源 GraphRAG 里，“Context Snapshot”本质上就是：`context_builder` 把（实体/关系/协变量/文本单元/社区报告）筛选、排序、截断到 token 预算后，拼成的一段（或几段）最终 prompt context。\*\*本地搜索（Local Search）就是在这个“已冻结”的上下文上调用一次 LLM 生成答案；全局搜索（Global Search）则在 Map/Reduce 两个阶段分别构造上下文并多次调用 LLM。[microsoft.github.io+2microsoft.github.io+2](https://microsoft.github.io/graphrag/query/local_search/?utm_source=chatgpt.com)

下面给你**最实用的 3 种读取方式**（从“最少改代码”到“最干净可复现”）。

* * *

方式 1：直接调用 `context_builder`，把返回值当作 Context Snapshot（推荐）
-------------------------------------------------------

GraphRAG 的 Local Search 会用一个 **Mixed Context Builder**（把社区报告 + 实体/关系/协变量表 + 文本单元组合成上下文）来构造本次查询的上下文。[GitHub+1](https://github.com/microsoft/graphrag/blob/main/graphrag/query/structured_search/local_search/mixed_context.py?utm_source=chatgpt.com)  
你可以**不走完整 search**，只调用它的 `build_context(...)`（或同名方法），拿到 “context\_text / selected items / token usage”等结构化结果，然后落盘。

**你要保存的 snapshot 最少包含：**

*   `query`
*   `context_text`（最终拼好的上下文文本）
*   `selected_entity_ids / selected_relationship_ids / selected_text_unit_ids / selected_community_ids`（如果返回结构里有）
*   `token_count / truncation_info`（如果有）

> 这样你就能做到：**同一个 snapshot → 换不同 LLM → 输出差异完全可归因于生成，而不是检索**。

* * *

方式 2：在 Local Search / Global Search 的“构造上下文之后、调用 LLM 之前”打 hook（最贴近真实执行）
-----------------------------------------------------------------------

你现在应该是用官方示例/脚本跑 query。那最贴近真实机制的做法是：

1.  找到你实际调用 Local Search 的入口（通常是 `LocalSearch` / `search(...)` 一类）
2.  在里面会先 `context_builder.build_context(...)`，得到 `context_result`
3.  **在调用 LLM 之前把 `context_result` 序列化写文件**
4.  再继续走 LLM 生成

Global Search 同理：它在 **Map 阶段**和 **Reduce 阶段**都会构造上下文，并且支持并发 Map；你可以分别保存：

*   `map_context[i]`：第 i 个社区（或社区 chunk）的上下文快照
*   `reduce_context`：Reduce 阶段最终汇总上下文快照

官方文档明确说明 Global Search 有 `context_builder_params`、并行控制，以及 `callbacks`（用于事件处理/流式等），说明这一段是可插入/可观测的。[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/?utm_source=chatgpt.com)

* * *

方式 3：用“callbacks + 自定义事件”保存 LLM 输入（适合你要完整链路审计）
----------------------------------------------

如果你想保存**更完整的逻辑链**（尤其是你做幻觉检测要审计每一步）：

*   在调用 LLM 的包装层（GraphRAG 会有一个统一的 LLM client / completion 调用点）做 callback
*   把每一次 LLM 调用的：
    *   `system prompt / user prompt`
    *   `messages`（如果是 chat 格式）
    *   `model / temperature / max_tokens`
    *   **最重要：prompt 里那段 context\_text**
    *   `raw response`  
        都写成一条 trace 记录

这对 Global Search 的 Map-Reduce 特别有用，因为 Map 阶段会并发多次调用 LLM。[microsoft.github.io](https://microsoft.github.io/graphrag/query/global_search/?utm_source=chatgpt.com)

* * *

你现在做“医学出院小结幻觉检测”，我建议你存的 Snapshot 格式
-----------------------------------

不管你用哪种方式，建议落盘 JSON（每次 query 一条），字段至少：

*   `run_id` / `timestamp`
*   `query`
*   `mode`: `local` / `global_map` / `global_reduce` / `drift`
*   `context_text`（**必存**）
*   `selected_entities`（id + name）
*   `selected_relationships`（source/target/id）
*   `selected_text_units`（id + 原文片段 + 来源note\_id/段落）
*   `selected_community_reports`（community\_id + 摘要文本）
*   `llm_request`（模型参数）
*   `llm_response_raw`

这样你后续做：

*   句子级一致性检查
*   entity-level 冲突检测
*   “证据缺失 vs 模型乱编”的归因  
    都会非常顺。

* * *

你下一步怎么最快落地（不问你要更多信息的版本）
-----------------------

1.  你现在用的 query 脚本（比如 `query_interactive.sh` 或 Python 脚本）里，找到 Local Search 的调用点
2.  在 LLM 调用前，把“构建好的 context”写到 `output/traces/<query_id>/context.txt`
3.  同时把选中的 ids（entities/relationships/text\_units/community\_ids）写到 `context.json`

如果你把你当前用的**查询脚本文件名**（或贴出那段调用 Local/Global Search 的 Python 代码片段），我可以直接告诉你：

*   **哪一行就是 context\_builder 的返回值**
*   **怎么把它完整 dump 出来**（包括 Map-Reduce 两阶段）

## Response:
我想知道graph rag支不支持

🔄 自动 JSON 序列化与反序列化
项目中的实践
在你的项目中，所有工具都返回 JSON 字符串：

# vision_tools.py
@tool
def detect_dishes_and_portions(image_path: str) -> str:
    dishes = [...]  # 识别结果
    return json.dumps({"dishes": dishes, "image_path": image_path})

# portion_tools.py
@tool
def check_and_refine_portions(vision_result: str) -> str:
    # LangChain 自动将上一个工具的输出传递过来
    vision_data = json.loads(vision_result)  # 手动解析
    dishes = vision_data.get("dishes", [])
    # ... 处理逻辑
    return json.dumps({"dishes": refined_dishes, "image_path": ...})
底层保障内容
功能	说明
智能解析	Agent 自动识别工具返回的是 JSON 还是普通文本
类型适配	自动处理 Python dict ↔ JSON string 转换
错误容错	JSON 解析失败时自动回退到纯文本处理
工具链传递	自动将上一个工具的输出传递给下一个工具的输入
嵌套结构支持	支持复杂的嵌套 JSON 结构

## Prompt:
结论先行，然后我会**非常具体、工程级**地拆解，避免和 LangChain / Agent 框架混淆。

* * *

一、直接结论（非常重要）
------------

**❌ 微软开源 GraphRAG 本身「不原生支持」你描述的这种：  
“工具 → JSON → 自动反序列化 → 传给下一个工具”的 Agent 式工具链机制。**

但要补一句同样重要的：

> **✅ GraphRAG 的设计「完全兼容」这种 JSON 序列化 / 反序列化机制，  
> 只是：它把这件事交给“调用层（orchestrator）”，而不是 GraphRAG 内核。**

也就是说：

*   **LangChain / Tool-Calling / Agent Runtime：负责 JSON 工具链**
*   **GraphRAG：只负责“构建上下文 + 受控生成”**

* * *

二、为什么你现在的那套机制 ≠ GraphRAG 内部机制
-----------------------------

你给的示例，本质是 **Agent + Tool Pipeline**：

```
@tool
def detect_dishes_and_portions(...) -> str:
    return json.dumps({...})

@tool
def check_and_refine_portions(vision_result: str) -> str:
    vision_data = json.loads(vision_result)
```

并且你列的这些能力：

| 能力 | 典型归属 |
| --- | --- |
| 自动 JSON 解析 | LangChain / OpenAI tool calling |
| 工具输出 → 下一个工具输入 | Agent runtime |
| JSON 容错 | Agent executor |
| 嵌套结构 | Tool schema / Pydantic |

👉 **这些都不是 GraphRAG 的职责范围**

GraphRAG 的哲学是：

> **“我不做 Agent，也不做工具编排；  
> 我只保证：当你把证据交给我，我给你一个可审计的回答。”**

* * *

三、GraphRAG 内部到底“支持什么级别的 JSON”
-----------------------------

虽然它不做 Agent，但 GraphRAG **非常重度使用 JSON / 结构化对象**，只是方式不同。

### 1️⃣ GraphRAG 的“JSON 使用层级”

| 层级 | 是否支持 | 说明 |
| --- | --- | --- |
| LLM 输出 JSON | ✅ 强支持 | 实体抽取、Map 阶段输出 |
| 中间结果结构化 | ✅ 强支持 | entity / relation / claim |
| 自动工具链 JSON 传递 | ❌ 不支持 | 没有 tool runtime |
| JSON schema 校验 | ⚠️ 部分 | 靠 prompt + Python 校验 |
| 自动反序列化 | ❌ | 你自己 `json.loads` |

* * *

### 2️⃣ 一个关键点：**GraphRAG 的 JSON 是“数据产物”，不是“工具协议”**

例如在 **Global Search – Map 阶段**，LLM 被要求输出：

```
{
  "points": [
    {
      "statement": "...",
      "importance": 0.78,
      "supporting_entities": ["E12"],
      "supporting_text_units": ["T91"]
    }
  ]
}
```

但注意：

*   这是 **GraphRAG 自己定义的中间数据结构**
*   **不会自动被“送给下一个工具”**
*   只是被 Python 代码读进来，用于 Reduce

👉 **它是 pipeline data，不是 tool I/O**

* * *

四、那你要的这套能力，GraphRAG 应该放在“哪一层”？
------------------------------

这是关键设计问题。

### ✅ 正确架构（推荐）

```
┌────────────────────────┐
│ Agent / Orchestrator   │  ← LangChain / 自写
│                        │
│  - Tool calling        │
│  - JSON auto parse     │
│  - Error recovery      │
│  - Multi-step logic    │
└─────────▲──────────────┘
          │
          │ JSON / dict
          ▼
┌────────────────────────┐
│ GraphRAG (Library)     │
│                        │
│  - build_context()     │
│  - local/global search │
│  - one-shot generate   │
└────────────────────────┘
```

GraphRAG **只作为一个“可调用工具”**，例如：

```
@tool
def graphrag_answer(query: str) -> dict:
    context = build_context(query)
    answer = llm_generate(context)
    return {
        "context_snapshot": context,
        "answer": answer
    }
```

然后：

*   **LangChain 负责**
    *   自动 JSON 序列化
    *   工具链衔接
*   **GraphRAG 负责**
    *   可审计上下文
    *   可引用回答

* * *

五、如果你“硬要问”：GraphRAG 能不能做到你列的那张表？
--------------------------------

我逐条非常明确地对照你给的表回答。

### 🔄 自动 JSON 序列化与反序列化

❌ **GraphRAG 不提供**  
✅ 但它的所有中间结果 **天然是 dict / dataclass**

* * *

### 🧠 智能解析（JSON vs 文本）

❌ 不支持  
GraphRAG 假定 **你知道你在传什么**

* * *

### 🔁 类型适配（dict ↔ JSON）

❌ 不支持自动  
✅ 你在调用层做一行 `json.dumps / json.loads`

* * *

### 🛠️ 工具链传递

❌ GraphRAG 内部没有“工具链”这个概念  
它只有：

*   indexing pipeline
*   query pipeline

* * *

### 🧩 嵌套 JSON 支持

✅ **支持，但只是“数据结构支持”**  
不是 Agent 意义上的“工具协议支持”

* * *

六、结合你现在做的事情，给你一个**非常实用的建议**
---------------------------

你现在的研究方向是：

*   医学出院小结
*   GraphRAG
*   幻觉检测
*   错误合成

### 👉 **最佳实践是：GraphRAG + LangChain（或你自己的 orchestrator）**

你可以做到：

1.  LangChain Agent：
    *   负责 JSON 工具链
    *   负责 vision / rule / checker / synthesizer
2.  GraphRAG：
    *   只负责“给定证据 → 生成 or 审查文本”
3.  **Context Snapshot 作为 JSON 工具输出的一部分**

这会让你后面做：

*   **hallucination attribution**
*   **error injection**
*   **contrastive training**

全部变成**结构化问题**，而不是 prompt 魔法。

* * *

七、一句“研究级总结”（你以后肯定用得上）
---------------------

> Microsoft GraphRAG does not implement an agent-style tool execution framework with automatic JSON serialization and chaining.  
> Instead, it exposes a deterministic, structured query pipeline whose intermediate artifacts are natively represented as structured objects, making it well-suited to be embedded as a tool within an external agent or orchestration framework that handles JSON-based tool communication.

如果你愿意，**下一步我可以直接帮你**：

*   设计一个  
    **`GraphRAGTool` 的 JSON schema**
*   或把你现在那套 `@tool` 风格，  
    **无缝嵌进 GraphRAG Query Pipeline**

你只要说一句：  
👉「我想把 GraphRAG 包成一个 LangChain tool」

## Response:
我能不能让rag在执行的时候调用langchain的这些功能呢？

## Prompt:
可以，但要把边界说清楚：**不是“让 GraphRAG 内核自己去跑 LangChain Agent/Tools”，而是“用 LangChain（或你自写 orchestrator）来包住 GraphRAG 的检索与生成流程，在关键节点插入 LangChain 的能力”。**

换句话说：

*   ✅ **你可以让“RAG 系统”在执行时调用 LangChain 的功能**
*   ❌ **你不能指望 GraphRAG 开源库内部原生支持 LangChain 的 tool-calling / 自动 JSON 链接**

下面给你三种成熟的集成方式，从“最稳”到“最像 Agent”。

* * *

方案 A（最推荐）：LangChain 作为 Orchestrator，GraphRAG 作为一个 Tool
------------------------------------------------------

### 你得到什么

*   LangChain 的：
    *   tool calling
    *   JSON 自动解析（取决于你怎么写工具和 schema）
    *   多工具链路
    *   容错/重试/路由
*   GraphRAG 的：
    *   context snapshot（可审计上下文）
    *   local/global 查询
    *   引用溯源（ids）

### 执行模式

```
User Query
  -> LangChain Router (决定走 local/global/drift 或先做别的工具)
      -> GraphRAG Tool (返回 {context_snapshot, answer, citations})
      -> 其他 Tools (e.g. 事实校验/结构化抽取/错误注入)
  -> Final Response
```

### 核心点

GraphRAG 返回的不止 answer，而要把 **context\_snapshot** 也返回，这样你的后续工具（检查器/对比器）才有证据闭环。

* * *

方案 B：把 LangChain 插到 GraphRAG 的“关键节点”（上下文构建前后、LLM 调用处）
-----------------------------------------------------

这适合你想保留 GraphRAG 的 query pipeline，但希望：

*   LLM 调用用 LangChain 的模型封装（统一缓存/追踪）
*   在生成前后插入 LangChain 的工具（比如结构化校验、JSON schema 验证、二次审查）

### 可以插的典型点

1.  **context\_builder 之后、LLM 之前**
    *   用 LangChain 做：结构化检查、去噪、压缩、敏感信息过滤
2.  **LLM 输出之后**
    *   用 LangChain 做：JSON 修复、引用完整性检查、反事实检测
3.  **Global Search 的 Map / Reduce 两阶段之间**
    *   用 LangChain tool 对每个 map 输出做一致性/去重

### 注意

这类方式通常需要你改一点 GraphRAG 调用代码（但不需要改 GraphRAG 库的核心逻辑）。

* * *

方案 C（最像你想要的）：Agent 先调用工具，再把结果“喂给”GraphRAG 或用 GraphRAG 结果继续调用工具
--------------------------------------------------------------

适用于你这种复杂任务：医学出院小结 / 幻觉检测 / 错误合成。

### 示例链路（很贴你的研究）

1.  Tool：从 EHR 证据中提取结构化事实（JSON）
2.  Tool：生成候选出院小结（或候选错误版本）
3.  Tool：GraphRAG 检索图谱 + 社区报告，补充上下文（context snapshot）
4.  Tool：LLM Judge / Checker：做“证据一致性”审查（输出冲突点 JSON）
5.  Tool：纠错/重写

GraphRAG 在这里可以是：

*   证据补全器（提供相关实体/关系/原文片段）
*   或审计器（拿 snapshot 做受控回答/对照）

* * *

关键限制（你要提前知道，避免走弯路）
------------------

### 1) “GraphRAG 执行时调用 LangChain 工具”这句话有两种含义

*   **含义 1：RAG 系统整体执行过程中调用 LangChain** ✅可行（方案 A/C）
*   **含义 2：GraphRAG 内核内部自动 tool-calling** ❌不现实（除非你重写其执行器）

### 2) GraphRAG 的强项是“证据闭集”

如果你让 Agent 在生成中途自由调用外部工具/外部检索，会破坏：

*   可审计性
*   可复现性
*   你做 hallucination attribution 的“归因边界”

所以工程上常见做法是：

*   **先工具 → 再冻结证据 → 再一次性生成**  
    而不是生成过程中随意插工具。

* * *

给你一个最适合你研究的推荐模式（可追踪 + 可复现）
--------------------------

> **LangChain 负责“多阶段工具链”，  
> 每次进入生成阶段前都把证据冻结成 Context Snapshot，  
> 生成阶段严格 one-shot，输出必须引用 snapshot 的 IDs。**

这样你后面做：

*   句子级 hallucination
*   错误注入的可控性评估
*   训练数据的可追踪 provenance  
    都会非常顺。

* * *

你现在如果要立刻落地，我建议你先做这一步
--------------------

把 GraphRAG 包装成一个 LangChain tool，输出固定 schema：

```
{
  "mode": "local|global",
  "query": "...",
  "context_snapshot": {
    "entities": [...],
    "relationships": [...],
    "text_units": [...],
    "community_reports": [...]
  },
  "answer": "...",
  "citations": [...]
}
```

然后你的下一个工具（checker / injector）就能直接消费这个 JSON。

* * *

如果你贴一下你目前是怎么调用 GraphRAG query 的（`query_interactive.py` 或你自己的入口函数那段），我可以直接告诉你：

*   哪个位置最适合插 LangChain
*   用方案 A 还是 B 更省改动
*   以及如何把 snapshot 以 schema 方式输出给下游工具



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)