# 5 Experimental Setup

## 5.1 Experimental Goal

The experiments validate whether the proposed system can perform evidence-driven VOC analysis reliably. We evaluate whether the system can generate complete structured reports from raw product data, whether intermediate objects support audit and error localization, whether full model paths and degraded paths are distinguishable, and whether the evaluation interface can record retrieval quality and report attribution quality.

This setup matches the system-methodology nature of the paper. The paper establishes a reproducible protocol in which the same input product, run configuration, intermediate artifacts, and evaluation summaries can be saved, inspected, and replayed.

## 5.2 Implementation Environment

The system is implemented in the Python ecosystem with both Web API and batch workflow interfaces. Typed schemas constrain intermediate objects, a state graph organizes the multi-stage workflow, and language model calls are routed through a compatible model gateway. The retrieval layer supports local and vector-database backends, image evidence can be encoded with vision-language representations, and candidate evidence can be reranked by text or multimodal rerankers.

Runtime policies distinguish formal evaluation from development validation. When full model dependencies are available, the system uses real embeddings, image encoders, and rerankers. When external capabilities are unavailable and degradation is allowed, the system can fall back to heuristic paths to keep the workflow executable.

The system exposes both interactive API and offline script entry points. The API layer provides endpoints for dataset overview, product normalization, index overview, index construction, review aspect extraction, and single-product analysis. Batch scripts execute the full workflow, offline validation, multimodal run checks, HTML export, manifest writing, and experiment matrices. Because these entry points share the same schemas and service layer, researchers can inspect individual stages through the API during development and reproduce the same workflow in batch mode during experiments.

Table 3 summarizes implementation details directly related to reproducible experiments.

| Item | Current implementation |
| --- | --- |
| Language | Python 3.11 or above |
| Workflow entry points | Web API and `run_workflow.py` batch script |
| Workflow orchestration | LangGraph state graph |
| Data object constraints | Pydantic schemas |
| Retrieval backends | Local JSON index and Qdrant backend |
| Text and image representations | Text embeddings, CLIP or compatible vision-language embeddings, heuristic fallback paths |
| Reranking paths | Text reranker, multimodal reranker, or heuristic ranking |
| Cached objects | Query embeddings, rerank results, and analysis checkpoints |
| Main artifacts | Normalized evidence package, aspect objects, retrieval records, structured reports, feedback/replay sidecars, HTML, and manifests |
| Engineering validation | Tests for normalization, review modeling, retrieval, report generation, manifest evaluation, and workflow entry points |

## 5.3 Data and Validation Units

The data consists of product-page crawl results, including product text, product images, and customer reviews. The system first converts raw inputs into product evidence packages, then executes single-product analysis. The validation unit is therefore a single product run rather than an aggregate cross-product metric. Each run produces structured records for aspects, questions, retrievals, reports, and evaluation.

The current validation unit does not support cross-product performance claims. Its role is to confirm that the system can produce complete, auditable, and replayable analysis samples at single-product granularity.

## 5.4 Metrics

The evaluation metrics are divided into two groups. Retrieval metrics include Recall@1, Recall@3, Recall@5, MRR, NDCG@3, and NDCG@5 when question-level evidence labels are available. These are standard ranking and recall metrics in information retrieval [13].

Claim-grounding metrics evaluate whether structured report claims are supported by review, product text, or product image evidence. They include claim support rate, claim grounded rate, citation precision, citation contradiction rate, and modality contribution. These metrics ask whether the report is evidence-supported rather than merely fluent.

## 5.5 Engineering Validation Protocol

Automated testing is part of the validation protocol. The tests cover data normalization, review modeling, question generation, index backends, embedding and reranking, retrieval, report generation, HTML export, manifest evaluation, runtime policies, and workflow entry points. The current codebase contains 166 passing tests, indicating that the main interfaces, structured artifacts, and workflow assertions are aligned.
