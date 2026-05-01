# 5 Experimental Setup

## 5.1 Experimental Goal

The experiments validate whether the proposed system can perform evidence-driven VOC analysis reliably. They do not constitute a frozen large-scale benchmark. We evaluate whether the system can generate complete structured reports from raw product data, whether intermediate objects support audit and error localization, whether full model paths and degraded paths are distinguishable, and whether the evaluation interface can support future human-labeled data.

This setup matches the system-methodology nature of the paper. The current examples are not treated as a public standard dataset. Instead, the paper establishes a reproducible protocol that can later be expanded with more products, human evidence labels, and retrieval strategy comparisons.

## 5.2 Implementation Environment

The system is implemented in the Python ecosystem with both Web API and batch workflow interfaces. Typed schemas constrain intermediate objects, a state graph organizes the multi-stage workflow, and language model calls are routed through a compatible model gateway. The retrieval layer supports local and vector-database backends, image evidence can be encoded with vision-language representations, and candidate evidence can be reranked by text or multimodal rerankers.

Runtime policies distinguish formal evaluation from development validation. When full model dependencies are available, the system uses real embeddings, image encoders, and rerankers. When external capabilities are unavailable and degradation is allowed, the system can fall back to heuristic paths to keep the workflow executable.

## 5.3 Data and Validation Units

The data consists of product-page crawl results, including product text, product images, and customer reviews. The system first converts raw inputs into product evidence packages, then executes single-product analysis. The validation unit is therefore a single product run rather than an aggregate cross-product metric. Each run produces structured records for aspects, questions, retrievals, reports, and evaluation.

For strict quantitative comparison, future work should construct human labels for question-level relevant evidence, claim-level support status, visual evidence visibility, and suggestion quality. The current setup already provides the object boundaries and evaluation entry points for such annotation.

## 5.4 Metrics

The evaluation metrics are divided into two groups. Retrieval metrics include Recall@1, Recall@3, Recall@5, MRR, NDCG@3, and NDCG@5 when question-level evidence labels are available. These are standard ranking and recall metrics in information retrieval [13].

Claim-grounding metrics evaluate whether structured report claims are supported by review, product text, or product image evidence. They include claim support rate, claim grounded rate, citation precision, citation contradiction rate, and modality contribution. These metrics ask whether the report is evidence-supported rather than merely fluent.

## 5.5 Engineering Validation Protocol

Automated testing is part of the validation protocol. The tests cover data normalization, review modeling, question generation, index backends, embedding and reranking, retrieval, report generation, HTML export, manifest evaluation, runtime policies, and workflow entry points. The current codebase contains 166 passing tests, indicating that the main interfaces, structured artifacts, and workflow assertions are aligned.
