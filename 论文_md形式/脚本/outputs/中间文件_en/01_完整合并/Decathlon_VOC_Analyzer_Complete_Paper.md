# Decathlon VOC Analyzer: An Evidence-Driven Multimodal VOC Analysis System for Aligning Product Images, Product Text, and User Reviews

Severin Ye
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
6severin9@gmail.com

Seowan Jung
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
swan041014@gmail.com

HyunJun Jung
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
beanbeansummon@naver.com

Hye Jeon
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
prajna0426@naver.com

Dokeun Lee
Department of Physics
Kyungpook National University
Daegu, Republic of Korea
nsa08008@naver.com

# Abstract

E-commerce voice-of-customer (VOC) analysis requires understanding subjective customer feedback and grounding it in objective product-page evidence. Text-only review analysis can identify sentiment and aspects, but it cannot determine whether a user claim is supported by product copy, specifications, images, or visual details. Conversely, directly asking a large language model to summarize all reviews and product information often produces fluent but weakly auditable conclusions. This paper presents Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system for aligning customer reviews with product text and image evidence.

The system normalizes raw product folders into traceable evidence packages, including product text, product images, default image regions, and review records. It performs review filtering, rating-aware sampling, aspect-level structured extraction, and deduplication. Each extracted aspect is then converted into evidence-seeking questions with explicit text, image, or cross-modal retrieval routes. The retrieval layer performs two-stage recall and reranking over product text and image evidence. The generation layer produces structured reports containing strengths, weaknesses, controversies, evidence gaps, improvement suggestions, and claim-level evidence attribution. The implementation also includes FastAPI endpoints, a LangGraph single-product workflow, runtime policies, retrieval caches, feedback/replay sidecars, HTML export, and manifest-based evaluation.

The main contributions are threefold. First, we propose a product VOC framework based on review aspect modeling, question planning, multimodal evidence retrieval, and evidence-constrained generation. Second, we implement an artifact-first research system in which reviews, questions, evidence, reports, and evaluation records are represented by structured schemas. Third, we provide a system validation protocol: the current codebase passes 166 automated tests and supports Recall@K, MRR, NDCG, claim support rate, and citation precision. The paper is positioned as a system-methodology paper rather than a completed large-scale benchmark study.

Keywords: multimodal RAG; voice of customer; aspect-level review modeling; evidence-constrained generation; product review analysis; evidence attribution

# 1 Introduction

Customer review analysis is a core task in e-commerce intelligence. Traditional approaches usually focus on sentiment classification, topic modeling, or aspect-based sentiment analysis. They can summarize what users like or dislike, but they rarely answer whether a claim is supported, contradicted, or left unresolved by the product page itself. For product operations, knowing that users complain about size or comfort is not sufficient; analysts also need to know whether the product copy states the relevant specifications and whether product images expose the corresponding structure.

Large language models make review summarization easier, but one-shot summarization introduces a different risk. If reviews, product text, and image descriptions are simply concatenated and passed to a model, the resulting report may be fluent while remaining difficult to audit. Users cannot reliably determine which claims came from reviews, which came from product text, and which were inferred from images. Error localization also becomes difficult.

This paper studies how to explicitly align subjective customer feedback with verifiable product text and image evidence. We propose Decathlon VOC Analyzer, a staged system that constructs product-centered evidence packages, extracts review aspects, plans evidence-seeking questions, retrieves product text and image evidence, reranks candidates, and generates structured VOC reports with claim-level attribution.

The contributions are as follows. First, we propose an evidence-driven multimodal RAG framework for product VOC analysis, adding a question-planning layer between review aspects and product evidence. Second, we implement an artifact-first prototype in which evidence packages, review aspects, retrieval questions, retrieval records, reports, feedback, replay files, and manifests are all structured and persistent. Third, we provide reproducible system interfaces and evaluation hooks for both retrieval metrics and generated-claim grounding metrics.

The rest of the paper is organized as follows. Section 2 defines the task and design constraints. Section 3 reviews related work. Section 4 describes the methodology. Section 5 presents the experimental setup. Section 6 reports system validation results. Section 7 discusses implications. Sections 8 and 9 conclude and describe limitations.

# 2 Background and Problem Definition

## 2.1 Evidence Needs in Product VOC Analysis

Product VOC analysis is not equivalent to generic review summarization. A useful product report should contain stable analytical objects such as strengths, weaknesses, controversies, applicable scenes, evidence gaps, and improvement suggestions. Each insight should ideally trace back to both customer review evidence and product-page evidence.

If a system only analyzes reviews, it answers what customers say but not whether the product page explains or supports those claims. If a system only retrieves product-page evidence, it lacks the anchor of actual customer concerns. Therefore, the key challenge is connecting subjective review needs with objective product evidence.

## 2.2 Input and Output

Given a product package $P$ containing product text $P_{text}$, product images $P_{image}$, and reviews $C_{reviews}$, the system outputs a structured report $R$:

$$
R = F(P_{text}, P_{image}, C_{reviews})
$$

In this paper, $F$ is not a one-step generation function. It is a staged workflow:

$$
C_{reviews} \rightarrow A_{aspects} \rightarrow I_{intents} \rightarrow Q_{questions} \rightarrow E_{retrieval} \rightarrow G_{aggregates} \rightarrow R_{attributed}
$$

where $A_{aspects}$ denotes review aspects, $I_{intents}$ denotes question intents, $Q_{questions}$ denotes executable retrieval questions, $E_{retrieval}$ denotes retrieved product evidence, $G_{aggregates}$ denotes aspect-level aggregation, and $R_{attributed}$ denotes the final attributed report.

## 2.3 Design Constraints

The system follows five constraints. Product evidence must be object-based and traceable. Reviews must be structured into aspects before retrieval. Retrieval queries should be questionized instead of using raw review text. Text and image evidence should be managed as separate routes. Final report claims should be traceable to review IDs, text block IDs, image IDs, or region IDs; unsupported claims should be represented as evidence gaps.

## 2.4 Difference from Generic RAG QA

Generic RAG systems usually answer a user question. In this task, the query source is a set of review aspects, and the output is a product VOC profile rather than a single answer. The system must manage multiple aspects, questions, evidence routes, report fields, and trace objects, making it closer to an evidence orchestration system than a standard QA pipeline.

# 3 Related Work

## 3.1 Retrieval-Augmented Generation and Evidence Constraints

Retrieval-augmented generation separates external evidence retrieval from parametric generation, improving traceability in knowledge-intensive tasks [1]. Retrieval-grounded revision further shows that external evidence can constrain and revise model outputs [2]. These ideas motivate our treatment of product VOC reporting as evidence-constrained generation rather than free-form summarization.

## 3.2 Multimodal Retrieval and Visual Evidence

CLIP demonstrates that images and text can be embedded into a shared semantic space for cross-modal retrieval [3]. Engineering discussions of multimodal RAG also emphasize that real-world knowledge systems contain text, images, tables, and structured fields, requiring representation, retrieval, and fusion across modalities [7,8]. Visual document retrieval methods such as ColPali further argue for preserving original visual evidence and using finer-grained visual matching [9]. Our system does not implement ColPali-style late interaction, but it preserves product images as first-class evidence and creates default image regions for future region-level retrieval.

## 3.3 Review Analysis and Aspect Modeling

Aspect-based sentiment analysis decomposes reviews into attributes, opinions, and sentiment polarity [10]. In product VOC analysis, this remains a necessary first step because reviews often mix multiple experiences, scenes, and emotions. In our system, however, aspects are not the final output. They become the starting point for evidence-seeking question generation.

## 3.4 Multi-Stage Retrieval and Reranking

Practical retrieval systems often separate coarse recall from expensive reranking. Qdrant engineering materials emphasize that vector stores should manage candidates and similarity search, while rerankers and downstream logic make higher-precision decisions [11,12]. Our system follows this separation by decoupling embedding services, index backends, candidate pooling, reranking, and final report attribution.

## 3.5 Structured Output and Workflow Orchestration

LLMs can be brittle in structured-output tasks, especially when outputs must satisfy stable field and type constraints [4,5]. ReAct-style reasoning and acting also suggests that multi-step stateful workflows are preferable to one-shot prompting for complex tool-mediated tasks [6]. Our system uses structured schemas for review extraction, question generation, report generation, caching, and evaluation, and uses LangGraph to orchestrate the single-product workflow.

## 3.6 Positioning

This paper does not propose a new general-purpose embedding model or reranker. Its contribution is a system-level framework for product VOC analysis that combines review aspects, question planning, multimodal retrieval, structured reporting, and claim-level attribution into a reproducible evidence workflow.

# 4 Methodology

## 4.1 Overall Architecture

Decathlon VOC Analyzer is a staged evidence-driven system. The main stages are dataset and product evidence normalization, review modeling and sampling, question planning, multimodal indexing and retrieval, reranking and caching, report generation and evidence attribution, workflow orchestration, and evaluation. Stages communicate through Pydantic schemas rather than unstructured text.

The single-product workflow is orchestrated by LangGraph with four nodes: `overview`, `normalize`, `index`, and `analyze`. These nodes scan the dataset, normalize the target product, build evidence indexes, and perform review extraction, question generation, retrieval, reranking, aggregation, report generation, and artifact persistence.

## 4.2 Product Evidence Normalization

The core data object is `ProductEvidencePackage`. Product names, descriptions, and categories become `TextEvidence`; product images become `ImageEvidence`; reviews become `ReviewRecord`. Each evidence object has stable identifiers, source fields, and language hints.

To reserve space for local visual evidence, each valid image is assigned five default regions: `center_focus`, `upper_focus`, `lower_focus`, `left_focus`, and `right_focus`. These fixed regions are not semantic detections, but they enable region cropping, local image embedding, and multimodal reranking without requiring annotated boxes.

## 4.3 Review Modeling and Sampling

The review modeling stage converts raw reviews into `ReviewAspect` objects containing aspect, sentiment, opinion, evidence span, usage scene, confidence, and extraction mode. The system removes empty, overly short, and low-signal reviews.

When `max_reviews` is set, the system applies rating-aware sampling. The default `problem_first` profile allocates 30% to one-star reviews, 25% to two-star reviews, 20% to three-star reviews, 15% to four-star reviews, and 10% to five-star reviews. Shortfalls are redistributed by a configured fallback order, and the resulting sampling plan is saved as an artifact.

Aspect extraction supports both LLM and heuristic paths. The LLM path uses the Qwen gateway and structured schemas. The heuristic path uses keywords, ratings, and sentiment hints to support offline testing. Extracted aspects are deduplicated and persisted.

## 4.4 Question Planning

Question planning is the bridge between subjective reviews and product evidence. For each `ReviewAspect`, the system plans question intents such as `explicit_support`, `visual_confirmation`, `cross_modal_resolution`, `spec_check`, and `visual_detail`. Each generated `RetrievalQuestion` records the source review, source aspect, question text, rationale, expected evidence routes, and confidence.

The `expected_evidence_routes` field explicitly specifies whether retrieval should use text, image, or both. This makes retrieval route-aware and enables downstream attribution to distinguish product-text support, image support, and mixed support.

## 4.5 Multimodal Indexing and Retrieval

The indexing layer converts product evidence into `IndexedEvidence`. Text evidence uses route `text`; whole images and image regions use route `image`. Text embeddings can be produced by `text-embedding-v4` or local Qwen3 embedding. Image embeddings default to CLIP. If allowed by runtime policy, the system can fall back to hash embeddings or proxy-text embeddings.

The `IndexBackend` abstraction supports both local JSON indexes and Qdrant. Retrieval first performs route-aware embedding recall with oversampling, then builds a language-balanced candidate pool, and finally passes candidates to the reranking layer.

## 4.6 Reranking, Caching, and Runtime Policy

Text and image candidates are reranked separately. Text candidates support local Qwen3 reranking, DashScope `gte-rerank-v2`, and heuristic ranking. Image candidates support local Qwen3-VL, Qwen-VL API reranking, text-reranker fallback, and heuristic ranking.

For multimodal image reranking, the system loads product images, crops region candidates when needed, compresses them as JPEG data URLs, and asks Qwen-VL to return strict JSON relevance scores. Query embeddings and rerank outputs are cached with signatures that bind route, query, backend, model, base URL, and candidate digest. Runtime policy controls whether degradation is allowed or forbidden.

## 4.7 Report Generation, Attribution, and Replay

The generation layer aggregates aspects and retrieved evidence, then produces structured reports containing strengths, weaknesses, controversies, evidence gaps, applicable scenes, and suggestions. If the LLM path is unavailable, a heuristic path generates the same schema.

After generation, the report refinement service deduplicates insights, calibrates evidence level, and rewrites unsupported overclaims. The system then builds `claim_attributions`, mapping report claims to review, product text, image, or region evidence and assigning support statuses. Feedback and replay sidecars allow later runs to reuse prior corrections and persistent issue summaries.

## 4.8 Schema-Based Explainability

Explainability is implemented through structured intermediate objects. The final `ProductAnalysisResponse` includes extraction results, question intents, questions, retrievals, retrieval quality, retrieval runtime, aggregates, report, trace, replay summary, artifact bundle, and warnings. This makes errors localizable to sampling, extraction, question planning, retrieval, reranking, report generation, or refinement.

# 5 Experimental Setup

## 5.1 Goals

The experiments in this paper are system validation experiments rather than a full benchmark. We validate whether the end-to-end workflow runs, whether intermediate artifacts are structured and auditable, whether runtime policies distinguish full model paths from degraded paths, and whether the evaluation module can produce useful metrics with or without gold labels.

## 5.2 Environment and Stack

The project targets Python 3.11+ and is validated in a Python 3.12 environment. Core dependencies include FastAPI, Pydantic, Pydantic Settings, LangChain, LangGraph, OpenAI SDK, Qdrant Client, Transformers, Torch, Pillow, orjson, and pytest. The API is exposed through FastAPI, and batch execution is provided by `04_scripts/run_workflow.py`.

## 5.3 Data and Artifacts

Raw product data is stored in `01_data/01_raw_products/products/`. Chinese audit data can be exported to `01_data/02_audit_zh_products/products/`. Outputs are organized by stage under `02_outputs/`, including normalized packages, aspect extraction results, indexes and retrieval caches, reports, feedback, replay, HTML reports, and run manifests.

The current data should not be interpreted as a frozen public benchmark. It is used to validate the workflow, schemas, artifacts, and evaluation interfaces. Larger multi-category annotated sets are required for formal retrieval comparisons.

## 5.4 Workflow Protocol

The standard protocol scans the dataset, normalizes the target product, builds text and image indexes, samples and extracts review aspects, plans retrieval questions, performs route-aware recall and reranking, aggregates aspects, generates the report, builds claim attribution and traces, and optionally exports HTML and manifest artifacts.

The main command is:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --export-html --write-manifest
```

Offline validation can disable external LLM calls:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --no-llm --output-format json
```

## 5.5 Evaluation Metrics

When `retrieval_relevance` labels are available in the manifest or analysis artifact, the evaluator computes Recall@1, Recall@3, Recall@5, MRR, NDCG@3, and NDCG@5, which are standard information retrieval metrics [13]. Without gold labels, the system still reports review, aspect, question, retrieval, evidence coverage, conflict risk, claim support, citation precision, and route contribution statistics.

## 5.6 Automated Tests

The automated test suite covers APIs, dataset services, review services, question generation, index backends, embedding and reranking, retrieval, analysis, HTML export, manifest evaluation, runtime policies, progress tracking, workflow scripts, and multimodal runtime validation. Running:

```bash
.venv/bin/python -m pytest
```

collects and passes 166 tests in the current codebase.

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

# 7 Discussion

## 7.1 Why Question-Driven Retrieval Fits Product VOC

The difficulty in product VOC analysis is not only summarizing reviews, but also explaining whether review claims are supported by product evidence. Question-driven retrieval adds an intermediate semantic layer: review aspects describe customer concerns, while retrieval questions describe evidence needs that product text or images can answer.

This is suitable for e-commerce because product pages are naturally multimodal and reviews are naturally subjective and noisy. Directly concatenating all information into a model sacrifices controllability, whereas question planning turns feedback into retrievable, evaluable, and attributable units.

## 7.2 Value of Artifact-First Engineering

The system is artifact-first. Normalized evidence packages, aspect extraction results, question caches, retrieval caches, reports, feedback, replay files, HTML exports, and manifests have fixed structures and output locations. Researchers can inspect any stage instead of only reading the final report.

This also lowers future experiment cost. Standardized product packages can be reused across question generation experiments; aspect and question artifacts can be reused across reranker comparisons; HTML and manifests can support human review.

## 7.3 Comparison with One-Step LLM Summarization

One-step LLM summarization is simple, but it cannot reliably answer where a conclusion came from, whether product text supports it, or whether images support it. Our staged design increases implementation complexity but provides interpretability, reproducibility, and evaluability.

For a research-oriented system, this tradeoff is necessary. Product VOC reports must support evidence inspection if they are to be used in operational or product decisions.

## 7.4 Implications for Future Work

The current implementation suggests that better evidence organization and query planning may be more important than simply using larger generators. Future work can add semantic detection or segmentation for image regions, build multi-category labeled benchmarks, compare retrieval strategies, and integrate feedback/replay with human review interfaces.

## 7.5 Paper-Level Significance

The current paper version provides the main body of a system-methodology paper. It defines the problem, architecture, implementation, evaluation interface, and limitations. Larger quantitative experiments can be added without rewriting the methodological core.

# 8 Conclusion

This paper presents Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system for aligning product text and image evidence with customer reviews. The system normalizes raw product data into traceable evidence packages, extracts aspect-level VOC objects from reviews, plans evidence-seeking questions, retrieves and reranks product text and image evidence, and generates structured reports with claim-level attribution.

The central conclusion is that product VOC analysis should not be reduced to one-step review summarization. It is better organized as a multi-stage workflow: review aspect modeling, evidence question planning, product text-image retrieval, and evidence-constrained generation. The current implementation provides APIs, batch workflows, structured artifacts, retrieval caches, feedback/replay, HTML export, manifest evaluation, and automated tests. The current codebase passes 166 tests.

Future work will add multi-category human-labeled benchmarks, compare retrieval and reranking strategies, improve visual grounding, and close the feedback/replay loop with human review.

# 9 Limitations

First, the current results are system validation results rather than a complete benchmark. The system supports manifest evaluation and automated testing, but it does not yet include a frozen multi-category human-labeled dataset.

Second, retrieval strategies still require systematic ablation. The implementation supports text routes, image routes, question-driven retrieval, reranking, and caching, but direct comparisons among raw-review retrieval, aspect retrieval, question-driven retrieval, embedding backends, and reranker backends remain future work.

Third, visual evidence granularity is limited. The system supports whole images and fixed-ratio crops, but these regions are not produced by semantic detection, segmentation, or grounding models.

Fourth, LLM outputs still depend on prompts and schema constraints. Structured output, refinement, and heuristic fallbacks reduce but do not eliminate misunderstanding, omission, or overgeneralization.

Fifth, the feedback loop is still mostly an engineering interface. Feedback and replay sidecars exist, but their quality impact has not yet been quantified through large-scale human review.

Sixth, a submission-ready paper will require a broader related-work section, formal figures, detailed annotation protocols, and statistical analysis.

# 10 Acknowledgments

This draft is prepared from the current design documents, implementation artifacts, scripts, tests, and experimental outputs of the project. A formal submission version may include acknowledgments for supervision, infrastructure support, and data preparation.

# Appendix

## A. Key Directories

| Directory | Responsibility |
| --- | --- |
| `01_data/` | Raw product data and Chinese audit data |
| `02_outputs/` | Normalized packages, aspects, indexes, reports, feedback, replay, HTML, and manifests |
| `03_configs/` | Review sampling profiles and runtime policy configuration |
| `04_scripts/` | Workflow, evaluation, export, validation, and cleanup scripts |
| `05_src/` | Core source code |
| `06_tests/` | API, service, script, and workflow tests |
| `0_docs/03_论文子模块文档/` | Thesis module documents based on current source code |
| `论文_md形式/` | Paper chapters, references, and export scripts |

## B. API Endpoints

The main API endpoints are:

- `/health`
- `/api/v1/dataset/overview`
- `/api/v1/dataset/normalize`
- `/api/v1/index/overview`
- `/api/v1/index/build`
- `/api/v1/reviews/extract`
- `/api/v1/analysis/product`

## C. Reproduction Commands

End-to-end run:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --export-html --write-manifest
```

Offline run:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --no-llm --output-format json
```

Manifest evaluation:

```bash
.venv/bin/python 04_scripts/evaluate_manifests.py 02_outputs/7_manifests
```

Test suite:

```bash
.venv/bin/python -m pytest
```

English PDF export:

```bash
.venv/bin/python 论文_md形式/脚本/pipeline.py --en
```

## D. Structured Artifacts

| Artifact | Default location | Purpose |
| --- | --- | --- |
| Normalized product package | `02_outputs/1_normalized/` | Input to indexing and analysis |
| Review aspect result | `02_outputs/2_aspects/` | Input to question planning and aggregation |
| Indexes and retrieval cache | `02_outputs/3_indexes/` | Retrieval and reranking reuse |
| Analysis report | `02_outputs/4_reports/` | Final structured VOC output |
| Feedback sidecar | `02_outputs/5_feedback/` | Human feedback entry point |
| Replay sidecar | `02_outputs/5_replay/` | Replay in later runs |
| HTML report | `02_outputs/6_html/` | Human review interface |
| Run manifest | `02_outputs/7_manifests/` | Evaluation and reproducibility entry point |

## E. Scope

This draft is suitable for system design explanation, methodology drafting, project defense, and future experiment planning. It is not yet a complete benchmark paper because multi-category frozen labels, formal ablations, and large-scale human evaluation are still missing.

# References

The export pipeline generates references from BibTeX entries in ref.bib.
