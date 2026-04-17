# 6 Results and Analysis

## 6.1 Script-Level and Test-Level Results

For a system paper, the first result is not merely the final report text but the reproducibility of the full workflow. From this perspective, the primary finding is that normalization, indexing, analysis, and paper export already form an executable chain. The run_workflow.py script supports end-to-end product analysis, validate_multimodal_runtime.py checks whether the intended multimodal runtime is active, and pipeline.py produces merged drafts, LaTeX sources, and PDF outputs. This indicates that the system has progressed beyond loosely connected experiments toward a reproducible workflow.

Automated testing reinforces this claim. In the current environment, the full test suite executes 43 tests, 42 of which pass. The only failing test is a prompt-language assertion mismatch rather than a failure in the business logic or the workflow core. Thus, at the current stage, the system can be regarded as operationally stable, with remaining issues concentrated in localized prompt-validation synchronization.

<a id="tab:engineering-results"></a>

| Dimension | Result | Interpretation |
| --- | --- | --- |
| End-to-end workflow | Successful | Normalization, indexing, analysis, and export can be executed from unified entry points |
| Multimodal runtime validation | Successful | Runtime profiles expose CLIP image embeddings and Qwen-VL reranking |
| Paper export chain | Successful | Both Chinese and English drafts can be merged and exported into PDF |
| Automated tests | 42/43 passed | The only failure is a localization-related prompt assertion |

*Table 3. Script-level and test-level validation results.*

## 6.2 Structured Nature of the Output Artifacts

The second major result lies in the artifacts themselves. Both representative product outputs demonstrate that the system no longer produces only free-form summaries but complete structured records. For backpack_010, the artifact contains extraction objects, generated questions, retrievals, retrieval-quality measurements, runtime metadata, aspect aggregates, and a final report. Even under the heuristic analysis mode, the system preserves source_review_id, source_aspect, text_block_id, and image_id fields that make the full path auditable.

The sunglasses_001 artifact shows a richer configuration under the LLM path. Three reviews are transformed into nine aspect objects, which are then aligned with both textual and visual evidence. Such output design provides two direct benefits: it makes the final report inherently auditable, and it supports fine-grained error localization because mistakes can be mapped to sampling, extraction, question generation, retrieval, aggregation, or reporting stages.

## 6.3 Case Study I: Sparse Negative Feedback in backpack_010

The backpack_010 sample illustrates a sparse but clearly negative analysis setting. The normalization report shows 200 reviews and 5 images for this product. Under the representative run, the problem_first sampling strategy selects a single 1-star review, from which the system extracts the negative aspect portability_size. A clarification question is then generated for that aspect, textual evidence is retrieved from the model-description block, and the aggregate stage identifies portability_size as the dominant issue in the final report.

The significance of this case is not its scale, but its structure. Even with limited evidence coverage, the system maintains a complete analytical chain: the negative review is explicitly sampled, the aspect is structurally extracted, the question is independently generated, supporting evidence is retrieved, and the final weaknesses and suggestions preserve supporting_evidence and confidence_breakdown fields. This demonstrates that the framework can operate not only in information-rich scenarios but also in sparse, negative, and evidence-limited settings.

## 6.4 Case Study II: Multi-Aspect Positive Analysis in sunglasses_001

The sunglasses_001 sample represents a different scenario: a small number of reviews, but broad positive coverage across multiple aspects and usage scenes. From 3 reviews, the system extracts 9 positive aspects, including value_for_money, durability, child_appeal, temperature suitability, comfort, price, design, overall_experience, and versatility. It then generates evidence-seeking questions for these aspects and retrieves both text-side and image-side evidence where appropriate.

The final report identifies applicable scenes including family use with children, children’s daily wear, mild-weather wear, warm-weather or high-activity use, and sports/travel. Importantly, the artifact does not simply return an “all positive” summary. It also identifies comfort evidence gap and design trend specificity as weak-evidence zones, and generates targeted suggestions accordingly. This indicates that the method does not equate positive sentiment with sufficient evidence, but instead continues to test whether each positive claim is actually grounded in product-side evidence.

## 6.5 Support for the Core Design Claim

Taken together, the two case studies support the main methodological claim of this paper: question-driven retrieval is more suitable than direct review retrieval for product VOC analysis. Raw review sentences are often too colloquial and noisy to serve as effective retrieval queries. Question reformulation makes the query closer to an evidence-seeking task, which improves the interpretability of retrieval and the usability of the resulting candidates.

This intermediate question layer is also crucial for error diagnosis. Because each retrieval record retains source_question_id and source_aspect, it becomes possible to ask whether a poor final result originates from unreasonable questions, weak retrieval, insufficient evidence, or downstream report construction. This property is likely to be essential for future work involving human feedback, region-level retrieval, and retrieval-specific metrics.

## 6.6 Current Boundaries of the Results

Despite these encouraging findings, the present results should still be interpreted as system-validation outcomes rather than final benchmark claims. First, the current framework does not yet report standard retrieval metrics such as Recall@k, MRR, or NDCG, so the marginal benefit of dual-route retrieval and reranking has not yet been quantitatively isolated. Second, the representative artifacts demonstrate capability across different types of scenarios, but they do not constitute a statistically representative evaluation set. Third, image retrieval remains object-level rather than region-level, which limits the analysis of highly localized visual properties.

## 6.7 Summary

At the present stage, the most important findings are threefold. First, product VOC analysis can indeed be organized as an evidence-driven multi-stage process rather than a black-box summarization task. Second, the aspect-to-question layer functions as the key structural bridge that decouples review understanding from multimodal retrieval. Third, the combination of scripts, artifacts, and tests indicates that the prototype has reached a level of maturity sufficient for a system-paper narrative, even though further work is still required before it can be framed as a large-scale benchmark study.