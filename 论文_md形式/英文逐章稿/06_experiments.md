# 6 Results and Analysis

## 6.1 End-to-End Workflow

The current system forms an end-to-end workflow from raw product folders to structured VOC reports. `run_workflow.py` connects dataset overview, normalization, indexing, and analysis. `validate_multimodal_runtime.py` verifies whether the multimodal runtime is enabled. `export_html_report.py` exports reviewable reports, and `evaluate_manifests.py` computes metrics from run manifests.

This shows that the implementation is not a set of isolated scripts. It is a schema- and artifact-centered analysis framework. Even in offline `--no-llm` mode, the system emits the same classes of aspects, questions, retrievals, and report objects.

## 6.2 Test Results

The current test suite collects 166 tests and all pass. The tests cover dataset normalization, review extraction, question generation, index backends, embedding, reranking, retrieval, analysis, HTML export, manifest evaluation, runtime policies, progress tracking, workflow scripts, and multimodal runtime validation.

| Validation target | Result | Interpretation |
| --- | --- | --- |
| Automated tests | 166/166 passed | Current implementation and assertions are aligned |
| API layer | Passed | Dataset, index, reviews, and analysis routes are tested |
| Retrieval layer | Passed | Local indexes, backend abstraction, embeddings, rerankers, and retrieval logic are tested |
| Generation layer | Passed | Question generation, report generation, attribution, HTML, and replay logic are tested |
| Workflow scripts | Passed | Workflow and runtime validation scripts are tested |

## 6.3 Structured Artifacts

The system output is not a single natural-language summary. A complete analysis contains extraction results, question intents, questions, retrievals, retrieval quality, retrieval runtime, aggregates, report, trace, replay summary, and artifact bundle. Each retrieval record keeps source question, source aspect, expected evidence routes, and retrieved evidence identifiers.

This structure makes reports auditable and errors localizable. If a suggestion is unreliable, one can inspect whether the issue came from sampling, extraction, question planning, retrieval, reranking, or report refinement.

## 6.4 Role of Question Planning

Question planning is the main bridge in the method. Raw review text often contains emotion, background, and implicit assumptions. Question planning converts review aspects into verifiable evidence needs, such as whether product copy explicitly supports a claim or whether product images provide visual evidence.

Each retrieval record keeps `source_aspect_id`, `source_question_id`, and `expected_evidence_routes`, making retrieval analysis query-level and route-aware.

## 6.5 Multimodal Evidence Routes

The system treats product text and images as different evidence routes. Text evidence is useful for names, categories, descriptions, specifications, and warranty-like claims. Image evidence is useful for structure, appearance, color, and local visual details. The image route includes whole images and default local regions.

The separation between coarse recall and reranking balances coverage and precision. For image candidates, multimodal reranking can directly inspect the original image or cropped region, reducing reliance on proxy text.

## 6.6 Evaluation Interfaces

The manifest evaluator supports both labeled and unlabeled settings. With gold retrieval labels, it computes Recall@K, MRR, and NDCG. Without labels, it still reports structured runtime statistics and claim attribution metrics such as claim support rate, claim grounded rate, citation precision, citation contradiction rate, and route contribution.

This design prepares the system for future benchmark experiments. Once multi-category human labels are added, the same manifest framework can compare raw review retrieval, aspect retrieval, question-driven retrieval, embedding backends, and reranking backends.

## 6.7 Boundary of Current Results

The current results demonstrate workflow completeness, artifact auditability, and a stable test baseline. They should not be interpreted as a full benchmark result. The paper does not yet report statistically significant comparisons over a frozen multi-category labeled dataset.
