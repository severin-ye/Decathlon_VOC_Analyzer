# 6 Results and Analysis

## 6.1 Workflow Completeness

The first validation result is that the current implementation completes the full analysis chain from raw product information to attributed structured reports. It performs product evidence normalization, review aspect modeling, question planning, multimodal recall, candidate reranking, aspect aggregation, report generation, and evidence attribution. Each stage emits consistent structured objects, so a single run can be decomposed into auditable analytical units.

This demonstrates that the method is not only conceptual. Review-side objects, product-side evidence, and report-side claims are connected through explicit data flow. Even when external model calls are disabled for validation, the system preserves the same object boundaries, separating workflow correctness from model capability.

## 6.2 Structured Auditability

A complete analysis contains not only a final narrative report but also review aspects, question intents, retrieval questions, retrieved evidence, retrieval quality, runtime configuration, aspect aggregation, process trace, and report attribution. These objects allow analysts to inspect the source of a conclusion instead of accepting a single opaque summary.

This structure directly supports error localization. If a suggestion lacks support, one can inspect whether the review was extracted correctly, whether the question was too broad, whether text or image retrieval found valid evidence, whether reranking prioritized key evidence, and whether report refinement correctly identified evidence gaps.

## 6.3 Role of Question Planning

Question planning is the key structure connecting reviews and product evidence. Raw reviews often contain emotion, context, and implicit assumptions; direct retrieval can scatter evidence candidates. Aspect-level questions convert these expressions into clearer evidence needs, such as whether product copy explicitly supports an experience, whether images show the relevant structure, or whether cross-modal evidence explains a negative review.

Because every retrieval keeps its source aspect, source question, and expected evidence routes, the system can be analyzed at query level. Human labels can also be attached directly to questions, text blocks, images, or regions, making question-driven retrieval a natural unit for future evaluation.

## 6.4 Complementarity of Multimodal Evidence

Text and image evidence serve different functions in product VOC analysis. Text evidence is suited for explicit specifications, usage claims, categories, and descriptions. Image evidence is suited for structure, appearance, color, local details, and presentation quality. The route-aware design allows the report to state whether a review claim is supported by text, by images, by both, or by neither.

This design also prevents image evidence from being textified too early. For appearance and structure-related issues, image candidates can be reranked by a vision-language model that directly inspects the whole image or crop. Although the current regions are rule-based, they demonstrate the feasibility of introducing local visual evidence into VOC analysis.

## 6.5 Extensibility of Evaluation

The evaluator already supports both retrieval quality and report-grounding quality. With human relevance labels, it can compute Recall@K, MRR, and NDCG. Without labels, it still reports claim support rate, citation precision, contradiction rate, and modality contribution. This allows the system to move naturally from system validation to formal benchmark evaluation.

The evaluation interface shares identifiers with intermediate objects. Annotators can label questions, text blocks, images, regions, or report claims without redefining the data structure. This lowers the cost of expanding to multi-category evaluation.

## 6.6 Boundary of Current Results

The current results establish workflow completeness, artifact auditability, and a stable test baseline. They should not be interpreted as final performance claims. The paper does not yet report statistically significant comparisons over a frozen multi-category dataset, nor systematic ablations over retrieval strategies, rerankers, or visual region policies.
