# Graph RAG 并行运行问题

**User:**   
**Created:**   
**Updated:**   
**Exported:** 3/19/2026 11:56:36  
**Link:** [https://chatgpt.com/share/69625f19-9b18-8002-96a2-d5aae4640a4e](https://chatgpt.com/share/69625f19-9b18-8002-96a2-d5aae4640a4e)  

## Prompt:
graph rag的index可不可以并行的运行

## Response:
请问您提到的“graph RAG 的 index 并行运行”具体是指以下哪种情况？

1.  构建 graph index 的过程是否可以并行化？
2.  多个 graph index 是否可以在运行时并行使用？
3.  在 RAG 推理阶段中，是否可以并行查询图中的节点？

另外，请问您使用的是哪种框架或工具（例如 LlamaIndex、LangChain、Haystack 等）？这样我可以提供更针对性的解答。

## Prompt:
多个 graph index 是否可以在运行时并行使用？

## Response:
明白了。我将调研在 RAG（Retrieval-Augmented Generation）系统中，是否可以在运行时并行使用多个 graph index，包括主流框架（如 LlamaIndex、LangChain、Haystack 等）是否支持该功能，以及实现方式和注意事项。  
研究完成后会将结果汇报给您，期间您也可以随时继续提问。

## Prompt:
RAG系统中并行使用多个索引的可行性调研
====================

在**检索增强生成**（Retrieval-Augmented Generation，简称RAG）系统中，将查询同时发送到多个不同索引（如多个向量索引、关键词索引或知识图谱索引）并行检索，可以提高检索覆盖范围和结果质量。本文将围绕以下几个方面展开技术分析：

1.  **推理阶段并行查询多个索引的支持情况** – 探讨RAG在运行时是否能够同时查询多个“Graph Index”（广义指多种索引，如向量索引、图数据库索引等）获取候选结果。
2.  **主流RAG框架的原生支持** – 考察当前流行的RAG框架（如LlamaIndex、LangChain、Haystack）是否提供原生接口支持这一能力。
3.  **非原生支持下的实现方式** – 如果框架未直接支持，介绍可选的实现方案（如多线程、异步请求等）以并行检索多个索引。
4.  **运行时性能与注意事项** – 分析在运行时并行检索的性能表现、可能遇到的瓶颈，以及使用时需要注意的问题。

并行查询多个索引的背景与需求
--------------

现实应用中，单一检索方式往往有局限。**融合多索引并行检索**可以充分利用不同检索机制的优势，提高召回率和准确率。例如，在RAG中常见的**混合检索**就是同时使用稠密向量检索与稀疏关键词检索，然后融合结果以提供更全面的支持[medium.com](https://medium.com/@adnanmasood/hybrid-retrieval-augmented-generation-systems-for-knowledge-intensive-tasks-10347cbe83ab#:~:text=,)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=,often%20improves%20recall%20and%20precision)。这种策略可以让向量相似度匹配捕获语义相关内容，同时让BM25等关键词检索确保精确术语匹配[medium.com](https://medium.com/@adnanmasood/hybrid-retrieval-augmented-generation-systems-for-knowledge-intensive-tasks-10347cbe83ab#:~:text=,)。现代RAG实现中已经出现**并行的多路检索管线**：同时查询向量索引（如基于HNSW或FAISS）和倒排索引（如ElasticSearch），在查询时融合二者的结果[medium.com](https://medium.com/@adnanmasood/hybrid-retrieval-augmented-generation-systems-for-knowledge-intensive-tasks-10347cbe83ab#:~:text=hallucinations.%20,as%20a%20first%E2%80%91class%20feature%2C%20cutting)。这种融合检索也被称为**多路召回**或**多模检索**。正如某技术文档所述：“**你可以同时通过多路不同类型的索引（比如向量索引与关键词索引）对输入问题进行检索，并对召回的知识块进行重排序处理后获取Top K结果**”[developer.volcengine.com](https://developer.volcengine.com/articles/7377708006907068466#:~:text=%E3%80%96%E5%9F%BA%E4%BA%8E%E5%A4%9A%E7%A7%8D%E7%B1%BB%E5%9E%8B%E7%9A%84%E7%B4%A2%E5%BC%95%E3%80%97)。由此可见，并行使用多个索引在理论上是可行且有益的。关键在于如何在实现上支持这种并行查询。

主流RAG框架对多索引并行的支持
----------------

下面分别考察几个主流的RAG开发框架对于**同时查询多个索引**的原生支持能力。

### LlamaIndex（原 GPT Index）

**LlamaIndex** 提供了灵活的索引组合和查询路由机制，支持对多数据源的统一查询。其**ComposableGraph**类可以将多个索引链接成一个分层结构，从而让查询可以路由到不同子索引上[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=Once%20indices%20are%20created%2C%20use,if%20no%20matches%20are%20found)。例如，我们可以构建一个知识**图索引**（Graph Index）来合并产品文档索引和客服工单索引，使查询能同时从两种来源提取信息[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=Once%20indices%20are%20created%2C%20use,if%20no%20matches%20are%20found)。在查询执行时，ComposableGraph会根据查询内容将请求路由到相关子索引上，比如查询“最近的故障报告”可以优先查询客服工单索引，如果没有匹配再回退到通用文档索引[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=structure,if%20no%20matches%20are%20found)。这种路由机制本质上是一种**多索引查询**，但默认行为可能是**顺序**查找或按需路由，而非真正并发。

为真正实现**并行查询多个索引**，LlamaIndex 新版本提供了**QueryPipeline**等组件来支持异步/并行流水线查询[llamaindexxx.readthedocs.io](https://llamaindexxx.readthedocs.io/en/latest/examples/pipeline/query_pipeline_async.html#:~:text=We%20do%20this%20by%20setting,pipeline%20that%20does%20the%20following)。通过QueryPipeline可以将同一个用户查询同时发送给多个Query Engine（每个Engine可对应不同索引），然后并行获取结果并合并处理[llamaindexxx.readthedocs.io](https://llamaindexxx.readthedocs.io/en/latest/examples/pipeline/query_pipeline_async.html#:~:text=We%20do%20this%20by%20setting,pipeline%20that%20does%20the%20following)。官方示例中展示了如何设置一个并行查询流水线：将输入 query 同时发送给多个 RAG 查询引擎，再把各自的检索结果合并后交给LLM[llamaindexxx.readthedocs.io](https://llamaindexxx.readthedocs.io/en/latest/examples/pipeline/query_pipeline_async.html#:~:text=We%20do%20this%20by%20setting,pipeline%20that%20does%20the%20following)。开发者可以自定义如何合并结果，例如简单拼接后摘要，或基于得分进行排序。LlamaIndex 还提供了一些高级组合器，例如 **RouterQueryEngine**（基于元数据自动将查询发送到特定索引）和 **SummaryQueryEngine**（对多个索引结果生成总结）等，方便对多索引结果进行处理[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=uniform%20chunks%20across%20sources%2C%20ensuring,and%20balance%20speed%20versus%20comprehensiveness)。此外，LlamaIndex的最新版本甚至内置了**QueryFusionRetriever**这类融合检索器，可以将多个底层Retriever的结果融合返回（底层实现采用类似RRF的重新排序策略）[developer.volcengine.com](https://developer.volcengine.com/articles/7377708006907068466#:~:text=%E5%AE%9E%E7%8E%B0%E8%9E%8D%E5%90%88%E6%A3%80%E7%B4%A2%E5%B9%B6%E4%B8%8D%E5%A4%8D%E6%9D%82%EF%BC%8C%E4%B8%8D%E7%AE%A1%E5%9C%A8LangChain%E8%BF%98%E6%98%AFLlamaIndex%E6%A1%86%E6%9E%B6%E4%B8%AD%EF%BC%8C%E9%83%BD%E6%9C%89%E8%BD%AC%E6%8D%A2%E5%99%A8)。总的来说，LlamaIndex原生支持通过**索引组合**和**并行流水线**来查询多个索引，但具体是否并行取决于所用组件：ComposableGraph/Router通常串行路由，而QueryPipeline/QueryFusionRetriever等可以实现真正的并行查询和结果融合。

\*示例：\*利用LlamaIndex组合两个向量索引并行查询。首先构建单独索引并组合：

```
from llama_index import VectorStoreIndex, ComposableGraph, SimpleDirectoryReader

# 创建两个索引，各自加载不同数据
index1 = VectorStoreIndex.from_documents(SimpleDirectoryReader('data/source1').load_data())
index2 = VectorStoreIndex.from_documents(SimpleDirectoryReader('data/source2').load_data())
# 通过ComposableGraph组合索引
graph = ComposableGraph.from_indices({"idx1": index1, "idx2": index2})

# 方法1：使用RouterQueryEngine，根据查询内容自动选择子索引
query_engine = graph.as_query_engine()  # RouterQueryEngine by default
response = query_engine.query("查询内容")

# 方法2：使用QueryPipeline并行查询所有子索引
from llama_index import QueryPipeline, ResponseSynthesizer
# 将每个子索引转换为QueryEngine
engines = {
    "idx1": index1.as_query_engine(),
    "idx2": index2.as_query_engine()
}
# 构建并行查询Pipeline，将输入query并发发送给两个索引引擎
pipeline = QueryPipeline.from_components(components=engines, synthesizer=ResponseSynthesizer())
response = pipeline.run("查询内容")
```

上述**方法2**利用`QueryPipeline`实现了对`idx1`和`idx2`两个索引的并行查询，最终通过`ResponseSynthesizer`合成统一的答案。在实际应用中，可以根据需要定制合成策略（如拼接内容后总结、按相关度排序选取前k条等）。

### LangChain

**LangChain** 作为通用的LLM应用框架，本身支持多向量仓库和多检索器的集成。早期的LangChain需要开发者自行对接多个检索源（例如依次查询多个`VectorStoreRetriever`并合并结果），但现在LangChain提供了**EnsembleRetriever/MergerRetriever**等高级Retrieval类，简化了多索引并行查询的实现[github.com](https://github.com/langchain-ai/langchain/issues/8677#:~:text=,the%20results%20of%20multiple%20retrievers)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=MergerRetriever%20in%20RAG%20%28Retrieval)。其中**MergerRetriever**（绰号“LOTR：Lord of the Retrievers”）可以将多个基础Retriever组合起来，实现**一次查询获取多个检索结果并融合**[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=MergerRetriever%20in%20RAG%20%28Retrieval)。MergerRetriever的工作流程包括：将用户查询并行发送给其包含的多个 Retriever（例如一个向量检索器和一个BM25检索器）→ 收集所有检索到的文档 → 根据预定策略对合并的结果进行重新排序、去重和裁剪[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Query%20Multiple%20Retrievers)。例如，可以使用**互惠排名融合**（RRF）或加权评分等策略对来自不同检索器的结果进行打分归一化后排序[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Ranking%20and%20Filtering)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=B)。通过这种方式，LangChain能够在**单次调用中查询多个索引/向量库**，最后返回一个统一的文档列表。

值得注意的是，LangChain的MergerRetriever抽象了多检索源，但具体实现上可能是串行地调用各retriever后合并。不过由于很多向量检索操作是IO或由后端数据库处理，在Python中即使顺序调用也不会显著延迟；而MergerRetriever也**可以配合异步机制**实现真正并发（LangChain的Retriever接口通常提供`aget_relevant_documents`用于异步调用）。实际中，如果需要进一步降低延迟，开发者也可以自行使用`asyncio.gather`或线程池并行调用各retriever，然后手动合并结果（参见下一节）。LangChain还有**RouterChain**等工具链路，可根据查询内容动态选择不同数据源，但如果要**同时**查询多个源，则MergerRetriever或自定义Chain是更直接的方式。

\*示例：\*利用LangChain的MergerRetriever组合关键词检索和向量检索：

```
from langchain.retrievers import MergerRetriever, BM25Retriever, VectorStoreRetriever
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings

# 初始化两个基础Retriever：BM25基于文档列表，Vector基于FAISS索引
bm25_retriever = BM25Retriever.from_documents(documents_list)  # 稀疏检索
vectorstore = FAISS.from_texts(texts_list, embedding=OpenAIEmbeddings())  # 建立向量索引
vector_retriever = VectorStoreRetriever(vectorstore=vectorstore)  # 稠密检索

# 创建MergerRetriever，使用Reciprocal Rank Fusion (RRF) 策略融合结果
merger = MergerRetriever(retrievers=[bm25_retriever, vector_retriever], merge_strategy="reciprocal_rank_fusion")
# 执行查询，将并行调用两个底层retriever并融合其返回结果
results = merger.get_relevant_documents("请问机器学习的定义是什么？")
```

上述MergerRetriever会将查询并发发送给BM25和向量索引检索，然后将得到的文档按RRF策略归一化得分并排序后返回统一的前k个结果。实际上，这正是\*\*混合检索（Hybrid Retrieval）\*\*的一种实现方式：利用密集和稀疏两个索引并行查询、取长补短[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=,often%20improves%20recall%20and%20precision)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Query%20Multiple%20Retrievers)。

除了MergerRetriever，LangChain社区也有其他类似方案，例如自行实现一个`EnsembleRetriever`来对多个`VectorStore`分别调用，再做并集排序[github.com](https://github.com/langchain-ai/langchain/issues/8677#:~:text=,the%20results%20of%20multiple%20retrievers)。总的来说，**LangChain在新版本中已经原生支持融合多个检索器**，方便开发者在RAG系统中使用多索引并行检索。

### Haystack

**Haystack** 是由Deepset提供的开源问答/RAG框架，以Pipeline形式串联检索和阅读器等组件。Haystack非常注重**多检索器结合**的场景，原生支持**Hybrid Retrieval**以及自定义Pipeline。开发者可以在Haystack的Pipeline中放入多个并行的Retriever节点，然后使用**JoinDocuments**节点将它们的输出进行合并[milvus.io](https://milvus.io/ai-quick-reference/what-are-the-different-retriever-models-supported-by-haystack#:~:text=Hybrid%20retrievers%20merge%20sparse%20and,options%2C%20Haystack%20provides%20flexibility%20to)。例如，一个经典的用法是同时使用**BM25Retriever**（基于Elasticsearch的关键词检索）和**EmbeddingRetriever**（基于向量数据库的语义检索），然后通过**EnsembleRetriever**或JoinDocuments将两者结果融合、去重并重新排序后，再传递给后续的Reader模块[milvus.io](https://milvus.io/ai-quick-reference/what-are-the-different-retriever-models-supported-by-haystack#:~:text=Hybrid%20retrievers%20merge%20sparse%20and,options%2C%20Haystack%20provides%20flexibility%20to)。Haystack的EnsembleRetriever实际上封装了这种逻辑：内部会调用多个基础Retriever获取结果，然后基于得分对文档进行重排。开发者也可以控制融合策略，比如简单地按最高分选取，或对不同检索器结果赋予不同权重。

需要指出，Haystack的Pipeline配置虽然允许多个节点**看起来并行**，但默认实现中各节点调用是同步进行的（当前线程顺序执行）。不过由于Haystack底层许多IO操作（例如数据库查询）会主动释放GIL，实践中串行调用多个Retriever对总体延迟的影响有限。同时，如果部署在支持并发的服务器环境（如Gunicorn的多worker模式），每个请求仍可充分利用多核。Haystack的开发者文档和社区也建议，如有需要可通过在Retriever中实现**多线程**批量查询或使用**亚检索(MultiQuery)**等方式提升并发性能[docs.haystack.deepset.ai](https://docs.haystack.deepset.ai/docs/retrievers#:~:text=MultiQueryEmbeddingRetriever%20%3A%20Wraps%20an%20embedding,variations%2C%20use%20the%20QueryExpander)[medium.com](https://medium.com/@adnanmasood/hybrid-retrieval-augmented-generation-systems-for-knowledge-intensive-tasks-10347cbe83ab#:~:text=Hybrid%20Retrieval,The)。实际上，Haystack提供了**MultiQueryRetriever**这类特殊组件，可对单个查询生成多种变体并行检索以提高召回率，其内部就是通过并行发出多个检索请求实现的[docs.haystack.deepset.ai](https://docs.haystack.deepset.ai/docs/retrievers#:~:text=This%20approach%20works%20with%20both,based%20Retrievers)。因此，可以认为Haystack框架本身具备一定的并行检索能力，尤其在混合检索场景下已将**多路检索融合**作为一等公民特性（如官方所述“多个检索器的结果可以通过JoinDocuments节点合并输出”[milvus.io](https://milvus.io/ai-quick-reference/what-are-the-different-retriever-models-supported-by-haystack#:~:text=Hybrid%20retrievers%20merge%20sparse%20and,options%2C%20Haystack%20provides%20flexibility%20to)）。

\*示例：\*使用Haystack Pipeline定义一个并行混合检索流程（伪代码说明）：

```
from haystack import Pipeline, Document
from haystack.nodes import DensePassageRetriever, BM25Retriever, JoinDocuments

# 初始化Haystack DocumentStore及两个Retriever
# 假设DocumentStore已包含文档的向量和BM25索引
dense_retriever = DensePassageRetriever(document_store=doc_store, query_embedding_model="dpr-query-model", passage_embedding_model="dpr-pass-model")
bm25_retriever = BM25Retriever(document_store=doc_store)

# 构建Pipeline
pipeline = Pipeline()
pipeline.add_node(component=dense_retriever, name="DenseRetriever", inputs=["Query"])
pipeline.add_node(component=bm25_retriever, name="BM25Retriever", inputs=["Query"])
# JoinDocuments节点将并行来的两个结果列表合并
pipeline.add_node(component=JoinDocuments(join_mode="merge", top_k_join=5), name="Join", inputs=["DenseRetriever", "BM25Retriever"])
# 后续还可以接入Reader或PromptNode等
# pipeline.add_node(... Reader ... inputs=["Join"])

# 执行查询
result_docs: [Document] = pipeline.run(query="什么是机器学习？")["documents"]
```

以上Pipeline中，同一个查询会经由两个不同Retriever分别检索，然后由JoinDocuments节点将它们的输出文档列表合并。参数`join_mode="merge"`表示简单合并结果并按得分排序（Haystack默认采用概率论的Score融合或直接依据Retriever顺序），`top_k_join=5`控制最终输出文档数。虽然代码上两个检索器节点是串联添加，但因为它们的`inputs`都是`["Query"]`且汇聚到同一个Join节点，这实际上配置了一种**并行分支**（Fork-Join）结构。在运行时，Haystack Pipeline调度会顺序触发Retriever节点，但由于它们互不依赖，可以近似看作并行检索两个索引，然后在Join处归并。

### 总结对比

*   **LlamaIndex**：通过ComposableGraph进行索引合并和路由，支持多索引统一查询；借助QueryPipeline或FusionRetriever可实现真正的并行查询和结果融合[llamaindexxx.readthedocs.io](https://llamaindexxx.readthedocs.io/en/latest/examples/pipeline/query_pipeline_async.html#:~:text=We%20do%20this%20by%20setting,pipeline%20that%20does%20the%20following)[developer.volcengine.com](https://developer.volcengine.com/articles/7377708006907068466#:~:text=%E5%AE%9E%E7%8E%B0%E8%9E%8D%E5%90%88%E6%A3%80%E7%B4%A2%E5%B9%B6%E4%B8%8D%E5%A4%8D%E6%9D%82%EF%BC%8C%E4%B8%8D%E7%AE%A1%E5%9C%A8LangChain%E8%BF%98%E6%98%AFLlamaIndex%E6%A1%86%E6%9E%B6%E4%B8%AD%EF%BC%8C%E9%83%BD%E6%9C%89%E8%BD%AC%E6%8D%A2%E5%99%A8)。适合需要灵活控制查询流程或构建复杂索引关系的场景。
*   **LangChain**：提供MergerRetriever等高层封装，方便地将多个Retriever并用，返回合并结果[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Query%20Multiple%20Retrievers)。对于常见的混合搜索需求，LangChain已将其标准化为一个Retrieval接口，实现简单。需要更高级控制时也可自行使用并发工具手动实现。
*   **Haystack**：采用Pipeline架构，通过多个Retriever节点+JoinDocuments实现多索引结果融合[milvus.io](https://milvus.io/ai-quick-reference/what-are-the-different-retriever-models-supported-by-haystack#:~:text=Hybrid%20retrievers%20merge%20sparse%20and,options%2C%20Haystack%20provides%20flexibility%20to)。它偏向流程配置，混合检索是其推荐模式之一。虽然不显式标称“并行执行”，但Pipeline设计和某些组件（MultiQueryRetriever等）已经考虑了并行的思想。

总体而言，这些框架**都支持同时利用多个索引/检索器**来增强RAG查询，只是实现方式不同：有的是**路由选择**（一个查询交给最相关索引），有的是**并行融合**（一个查询送多个索引并取并集），也有通过**层次结构**（先粗再细地检索不同层次索引）等。选择哪种方式应根据应用需求权衡复杂度和性能。

非原生支持下的多索引并行实现
--------------

如果所使用的框架没有直接提供多索引并行查询的高级接口，开发者可以采用**多线程**或**异步调用**来实现手动的并行检索。思路是相对直接的：对每个索引分别发起查询，将所有查询以并发方式执行，最后合并结果集并进行处理。例如：

*   **使用多线程**：在Python中可以借助`concurrent.futures.ThreadPoolExecutor`来并行执行IO操作。由于检索通常包含网络IO或数据库查询，多线程方式可以很好地利用等待时间，从而减少总延迟。例如：
    ```
    import concurrent.futures
    def query_index(index, query):
        return index.search(query)  # 假设每个索引对象都有search方法返回结果列表
    indices = [indexA, indexB, indexC]  # 多个索引实例
    query = "用户的查询"
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(indices)) as executor:
        future_to_index = {executor.submit(query_index, idx, query): idx for idx in indices}
        for future in concurrent.futures.as_completed(future_to_index):
            res = future.result()
            results.extend(res)
    # 此时results包含来自所有索引的结果，需要根据得分等再排序过滤
    ```
    上述伪代码中，我们为每个索引提交一个线程执行查询，`as_completed`会在各线程完成时收集结果。最后再对合并的`results`按照相关度评分等进行重新排序并截断。线程池的大小可以根据索引数量和系统资源设置。
*   **使用异步IO**：如果底层检索接口支持`async`/`await`（例如一些向量数据库的Python SDK提供异步查询方法），可以使用`asyncio`并发执行。例如：
    ```
    import asyncio
    async def query_index_async(index, query):
        return await index.async_search(query)
    async def query_all_indices(indices, query):
        tasks = [query_index_async(idx, query) for idx in indices]
        all_results = await asyncio.gather(*tasks)
        merged = [doc for res in all_results for doc in res]
        return merged
    merged_results = asyncio.run(query_all_indices(indices, query))
    ```
    这利用`asyncio.gather`同时调度多个异步检索任务，性能上相当于并行发出了请求[developer.volcengine.com](https://developer.volcengine.com/articles/7377708006907068466#:~:text=class%20FusionRetriever%28BaseRetriever%29%3A,retrievers)。需要注意Python异步适用于IO密集型任务，如果检索涉及大量CPU计算，异步未必比多线程高效。
*   **多进程或分布式**：对于计算密集或需要利用多核的检索（例如本地FAISS在大数据上查询，或涉及复杂算法的Knowledge Graph查询），可以考虑使用多进程并行（如Python的`multiprocessing`或基于Ray的并行执行）[llamaindex.ai](https://www.llamaindex.ai/blog/build-and-scale-a-powerful-query-engine-with-llamaindex-and-ray-bfb456404bc4#:~:text=We%E2%80%99ll%20give%20a%20quick%20introduction,Ray%20Serve%20to%20build%20deployments)[llamaindex.ai](https://www.llamaindex.ai/blog/build-and-scale-a-powerful-query-engine-with-llamaindex-and-ray-bfb456404bc4#:~:text=and%20query%20their%20private%20data)。多进程避免了GIL限制，但进程间通信开销较大，适合较重的检索任务。分布式方案则可以将不同索引部署在不同服务，由一个调度器同时发送请求给各服务再汇总结果，这在索引规模很大时具有良好的伸缩性。

无论采用哪种并行手段，实现后都需要加入**结果融合逻辑**。常见的融合处理包括：合并结果列表后按照统一标准排序（可能需要对不同索引的相关性分数进行**归一化**以确保可比[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Ranking%20and%20Filtering)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Query%20Multiple%20Retrievers)），去除重复的文档片段，根据需要裁剪至Top K，以及在最终交给LLM前拼接上下文或总结摘要。简单情况下，可以根据每个结果自带的相关度评分直接选取最高的若干来自所有索引的结果[reddit.com](https://www.reddit.com/r/LangChain/comments/141mn27/can_i_query_multiple_vectorstores_at_the_same_time/#:~:text=%E2%80%A2%20%203y%20ago)；更精细的方案会对不同来源结果赋权、或者用学习到的模型重新rank。开发者可以参考现有实现（如LangChain的MergerRetriever使用RRF融合[medium.com](https://medium.com/etoai/better-rag-with-lotr-lord-of-retriever-23c8336b9a35#:~:text=Better%20RAG%20with%20LOTR,robin)，Haystack EnsembleRetriever加权合并等）来设计自己的融合策略。

需要强调，如果框架本身已有类似MergerRetriever或JoinDocuments等组件，**优先使用框架提供的机制**，因为它们通常已经处理好了异步、安全和结果归一化等问题，减少自行实现出错的可能。

运行时性能表现与注意事项
------------

**并行查询多个索引**在提高检索覆盖面的同时，也引入了一些性能上的考量和潜在瓶颈：

*   **查询延迟**：理想情况下，并行检索的总延迟接近于最慢的那个子查询的耗时，而显著小于顺序求和。例如，如果三个索引各需100ms查询时间，那么串行需要约300ms，而并行可能仍是~100ms左右就能拿到所有结果（取决于最慢一个）。因此在**检索耗时较长或差异较大**时，并行能显著缩短等待时间。不过，如果各索引查询时间非常短（比如都在几十毫秒内），那么并行节省的时间有限，反而增加了一些线程/调度开销。
*   **LLM调用瓶颈**：在完整的RAG流程里，检索只是前半段，后续还要将检索结果提交给大模型生成答案。通常LLM调用本身耗时更长（数百毫秒到几秒不等，视模型大小和输出长度）。因此相对于LLM推理时间，**并行检索节省的那点时间可能并不是主要矛盾**。优化检索并行度对**整体**响应延迟的改善需要结合LLM时间来看。在一些情况下，与其复杂并行检索，不如考虑减少不必要的长上下文传入模型以加快生成。但在对实时性要求极高的场景（如实时问答、对话系统），并行检索依然是有意义的优化手段，可以把宝贵的时间留给模型生成和用户交互。
*   **系统资源占用**：并行执行意味着同时消耗更多资源。例如并行对多个索引查询会同时消耗多份CPU、内存或网络带宽。如果这些索引都在同一台机器进程内，可能会引发竞争。**GIL**（全局解释器锁）也是需要考虑的问题：在CPython中，多线程同一时刻只能有一个线程执行Python字节码。如果检索操作主要在Python层计算（比如复杂过滤逻辑），多线程可能无法利用多核。同时进行太多并发任务还可能导致上下文切换开销增加。如果索引查询涉及大量向量相似度计算（BLAS库实现）或IO等待，则GIL影响会小一些，因为这些操作要么在底层C释放了GIL，要么属于IO操作不会阻塞其它线程。
*   **检索结果合并的开销**：将多个索引的结果合并排序本身需要一定时间，尤其当每个索引各返回很多文档时。一般会限制每路索引的top\_k，比如每个索引取前10，然后合并成最多30条再排序取前10，以控制开销。结果合并在算法上通常是O(n log n)（n为合并后文档总数），这个开销相对于检索本身通常不大。但如果有**复杂的融合算法**（例如基于BERT的重排序模型对每个候选再评分），那就是另一层消耗，需要在架构上合理安排（比如异步启动rerank）。
*   **评分标准差异**：不同索引返回的相关性评分不在同一尺度上，例如向量相似度通常在\[0,1\]（cosine similarity），而BM25分数可能上不封顶。因此直接混排可能不公平。在并行方案中**分数归一化**和**融合策略**很重要[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Ranking%20and%20Filtering)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=,Queries)。常见做法是对每个索引的分数做Min-Max归一或Z-score归一[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=%28E%29%20Normalization%20%28Min)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=1,FAISS%20%2F%20ChromaDB)后再融合，或者采用无关评分值的RRF算法（只看排名次序进行融合）。这些都会影响最终结果质量，属于并行检索需要注意的质量细节问题，而非性能瓶颈但同样重要。
*   **上下文长度限制**：并行检索往往会**召回更多信息**。如果最后要把多索引结果都提供给LLM构成提示上下文，需要注意模型的上下文窗口大小限制。硬件上虽然检索并行了，但是LLM输入长度有上限，传入太多文本也会带来**生成延迟**和费用升高。为此，可以考虑在多个结果合并后先做摘要或筛选（例如取各索引Top3共N条）再交由LLM[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=performance%2C%20cache%20frequently%20accessed%20indices,and%20balance%20speed%20versus%20comprehensiveness)。LlamaIndex的SummaryQueryEngine就是用LLM对多索引结果生成一个总结以减小提示长度[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=uniform%20chunks%20across%20sources%2C%20ensuring,and%20balance%20speed%20versus%20comprehensiveness)。总之，要在**答案丰富**和**提示精炼**之间取得平衡。
*   **错误处理和一致性**：并行查询多个来源时，要做好错误和异常处理。例如某个索引查询失败或超时，是否等它还是忽略？如果不同索引的数据存在重叠，该如何避免重复回答或冲突？这些都需要在实现时考虑。框架原生组件一般会处理一些基本超时和去重逻辑，但自实现时别忘了这些细节。

**小结**：在RAG系统中并行使用多个索引可以**提升召回效果并减少单路检索的延迟瓶颈**。目前主流框架均提供了一定程度的支持（如LlamaIndex的Graph组合和Pipeline，LangChain的MergerRetriever，Haystack的Pipeline Join等），开发者应优先采用这些原生工具[milvus.io](https://milvus.io/ai-quick-reference/what-are-the-different-retriever-models-supported-by-haystack#:~:text=Hybrid%20retrievers%20merge%20sparse%20and,options%2C%20Haystack%20provides%20flexibility%20to)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Query%20Multiple%20Retrievers)。如果需要自行实现并行，一定要关注线程/异步模型对性能的影响，并仔细处理结果融合的质量和一致性问题。适当的并行优化可以让RAG系统更快速地从海量知识中找到答案，但也要避免过度并行导致系统复杂度和资源消耗不成比例。在实践中，建议通过**实验评估**并行检索带来的速度提升和对LLM回答准确性的影响，从而决定最适合自己应用的方案[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=metadata%2C%20while%20,and%20balance%20speed%20versus%20comprehensiveness)。

**参考文献：**

*   LlamaIndex官方文档和博客示例，说明如何组合多索引并行查询[llamaindexxx.readthedocs.io](https://llamaindexxx.readthedocs.io/en/latest/examples/pipeline/query_pipeline_async.html#:~:text=We%20do%20this%20by%20setting,pipeline%20that%20does%20the%20following)[milvus.io](https://milvus.io/ai-quick-reference/how-do-i-handle-multiple-indexing-sources-with-llamaindex#:~:text=Once%20indices%20are%20created%2C%20use,if%20no%20matches%20are%20found)
*   LangChain检索器合并（MergerRetriever）的介绍[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Query%20Multiple%20Retrievers)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=,often%20improves%20recall%20and%20precision)
*   Haystack官方与社区文档关于混合检索和JoinDocuments的说明[milvus.io](https://milvus.io/ai-quick-reference/what-are-the-different-retriever-models-supported-by-haystack#:~:text=Hybrid%20retrievers%20merge%20sparse%20and,options%2C%20Haystack%20provides%20flexibility%20to)
*   技术博客对于融合检索（Fusion Retrieval）的描述及实现建议[developer.volcengine.com](https://developer.volcengine.com/articles/7377708006907068466#:~:text=%E3%80%96%E5%9F%BA%E4%BA%8E%E5%A4%9A%E7%A7%8D%E7%B1%BB%E5%9E%8B%E7%9A%84%E7%B4%A2%E5%BC%95%E3%80%97)[developer.volcengine.com](https://developer.volcengine.com/articles/7377708006907068466#:~:text=%E5%AE%9E%E7%8E%B0%E8%9E%8D%E5%90%88%E6%A3%80%E7%B4%A2%E5%B9%B6%E4%B8%8D%E5%A4%8D%E6%9D%82%EF%BC%8C%E4%B8%8D%E7%AE%A1%E5%9C%A8LangChain%E8%BF%98%E6%98%AFLlamaIndex%E6%A1%86%E6%9E%B6%E4%B8%AD%EF%BC%8C%E9%83%BD%E6%9C%89%E8%BD%AC%E6%8D%A2%E5%99%A8)
*   相关Medium文章关于LOTR MergerRetriever原理的分析[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=MergerRetriever%20in%20RAG%20%28Retrieval)[medium.com](https://medium.com/@danushidk507/rag-series-vi-merge-retriever-lotr-lord-of-the-retriever-49442a0717ff#:~:text=Ranking%20and%20Filtering)



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)