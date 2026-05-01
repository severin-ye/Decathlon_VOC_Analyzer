# Decathlon VOC Analyzer: An Evidence-Driven Multimodal VOC Analysis System for Aligning Product Images, Product Text, and User Reviews

Severin Ye
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
6severin9@gmail.com

Dokeun Lee
Department of Physics
Kyungpook National University
Daegu, Republic of Korea
nsa08008@naver.com

Wushuang Liu
Department of Child Studies
Kyungpook National University
Daegu, Republic of Korea
824309203q@gmail.com

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

# Abstract

E-commerce voice-of-customer (VOC) analysis requires understanding subjective customer feedback and grounding it in objective product-page evidence. Text-only review analysis can identify sentiment and aspects, but it cannot determine whether a user claim is supported by product copy, specifications, images, or visual details. Conversely, directly asking a large language model to summarize all reviews and product information often produces fluent but weakly auditable conclusions. This paper presents Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system for aligning customer reviews with product text and image evidence.

The method normalizes raw product information into traceable evidence packages, including product text, product images, default image regions, and review records. It performs review filtering, rating-aware sampling, aspect-level structured extraction, and deduplication. Each extracted aspect is then converted into evidence-seeking questions with explicit text, image, or cross-modal retrieval routes. The retrieval layer performs two-stage recall and reranking over product text and image evidence. The generation layer produces structured reports containing strengths, weaknesses, controversies, evidence gaps, improvement suggestions, and claim-level evidence attribution. Key intermediate representations and evaluation records are retained to support reproducibility and error analysis.

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

## 4.1 Overall Framework

Decathlon VOC Analyzer formulates product VOC analysis as an evidence-driven multi-stage reasoning process. The system first organizes product text, images, and reviews into a unified evidence space. It then extracts aspect-level customer feedback, converts each aspect into evidence-seeking questions, retrieves and reranks product text and image evidence, and finally generates structured reports with claim-level attribution. Unlike one-step LLM summarization, the framework separates what customers express, whether product evidence supports it, and how the final report grounds its claims.

The framework contains four logical layers. The product evidence layer constructs structured representations of product text, images, and local visual regions. The VOC demand layer converts reviews into aspects, opinions, sentiments, and usage scenes. The evidence alignment layer rewrites aspects into route-aware questions and retrieves evidence from the product evidence space. The report attribution layer generates structured insights and maps report claims back to review and product evidence.

[Figure 1 placeholder: overall framework of evidence-driven multimodal VOC analysis]

AI drawing prompt: Create a clean academic system architecture diagram with a white background, blue-gray color palette, and small orange highlights for the core innovation. Show four left-to-right logical layers: Product Evidence Layer with product text, product images, image regions, and reviews; VOC Demand Modeling Layer with review filtering, rating-aware sampling, aspect extraction, and aspect objects; Question-Guided Multimodal Retrieval Layer with question intent planning, text route retrieval, image route retrieval, reranking, and language-balanced candidate pool; Evidence-Constrained Reporting Layer with aspect aggregation, structured report, claim attribution, evidence gaps, and feedback/replay. Use arrows for data flow and dashed boxes for reusable artifacts and caches. Do not include file paths, code class names, or brand logos. Emphasize that review aspects become evidence-seeking questions and report claims are grounded back to product and review evidence. The diagram should be suitable for a conference paper, readable in grayscale, and usable as a one-column or two-column figure.

*Figure 1. Overall framework of Decathlon VOC Analyzer. The system uses review aspects and product evidence packages as intermediate representations, connects subjective VOC signals with multimodal product evidence through question planning, and performs claim-level attribution during reporting.*

## 4.2 Product Evidence Representation

Product pages contain names, descriptions, categories, specifications, images, and customer reviews. If these inputs are simply concatenated into a long prompt, later conclusions become difficult to trace. The system therefore builds product-level evidence packages in which text blocks, images, image regions, and reviews are represented as stable evidence objects.

Text evidence preserves source sections such as title, description, or category. Image evidence includes whole images and rule-based local regions, enabling local visual access without annotated bounding boxes. Review records preserve rating, language hints, and original text spans. The goal is not to complete semantic interpretation at the data layer, but to establish object boundaries for retrieval, attribution, and evaluation.

## 4.3 Review Aspect Modeling

The review-side task is to convert natural language feedback into aspect-level VOC units. Each aspect contains an attribute, sentiment, opinion, evidence span, usage scene, and confidence. Compared with whole-review summarization, aspect-level representation supports both statistical aggregation and evidence retrieval.

The system uses rating-aware sampling before extraction to avoid spending limited review budget on high-rating short comments. The default policy gives more weight to low-rating reviews because they often contain higher-value product improvement signals. Aspect extraction supports both structured LLM extraction and heuristic extraction, allowing the same workflow to run under full model settings or offline validation settings.

## 4.4 Aspect-to-Question Planning

The key design is the intermediate planning layer between aspects and retrieval. Aspects such as small capacity, comfortable fit, or child appeal are still subjective and underspecified. Direct retrieval with these phrases often produces broad candidates and does not indicate whether text or images should be searched. The system therefore constructs evidence-seeking questions with explicit retrieval intents.

The questions cover text support, visual confirmation, and cross-modal resolution. Text-support questions ask whether product copy or specifications directly support a claim. Visual-confirmation questions ask whether product images show relevant structures or appearances. Cross-modal questions ask whether text and images together explain a review as a real product issue, insufficient presentation, or expectation mismatch.

[Figure 2 placeholder: transformation from review aspects to multimodal evidence queries]

AI drawing prompt: Create an academic mechanism diagram showing “review aspect -> question intents -> route-aware retrieval -> evidence bundle.” On the left, draw a customer review bubble such as “too small for travel documents,” and below it an aspect object card with fields aspect, sentiment, opinion, evidence span, and usage scene. In the middle, show three question intent cards: explicit text support, visual confirmation, and cross-modal resolution, each producing one natural-language retrieval question. On the right, split retrieval into two routes: text route pointing to product title, description, and specification snippets; image route pointing to whole product image, center crop, and detail crop. Both routes feed into a reranker and merge into an evidence bundle. Use numbered arrows from 1 to 5. Use blue for text evidence, green for image evidence, and orange for question planning. Avoid real product photos; use abstract backpack or glasses line icons.

*Figure 2. Aspect-to-question planning. Aspect objects are not directly used as retrieval queries; they are decomposed into intent-specific questions that trigger text, image, or cross-modal evidence routes.*

## 4.5 Multimodal Recall and Reranking

The evidence alignment layer uses two-stage retrieval. The first stage performs vector-based coarse recall over product text and product images. The second stage reranks the candidate set with higher-cost models. Text and image evidence are managed as separate routes during retrieval, but they are unified in the product evidence space during attribution.

Text evidence is useful for names, descriptions, specifications, and explicit claims. Image evidence is useful for structure, appearance, color, local details, and presentation quality. Whole images and rule-based local crops allow preliminary region-level evidence to enter the VOC pipeline. The candidate pool is balanced by route and language to prevent a single route or language from dominating final evidence selection.

## 4.6 Evidence-Constrained Reporting and Claim Attribution

The generation stage does not pass retrieved evidence to the model as ordinary context. It first aggregates aspect signals and retrieval coverage, then generates structured reports containing strengths, weaknesses, controversies, applicable scenes, evidence gaps, and suggestions.

To make the report auditable, the system performs claim-level attribution. Major claims are mapped to review evidence, product text evidence, product image evidence, or their combinations, and are labeled as supported, partially supported, unsupported, or contradicted. If a review claim cannot be verified by current product evidence, the system prefers to expose an evidence gap instead of presenting the claim as confirmed.

[Figure 3 placeholder: evidence attribution and evaluation loop]

AI drawing prompt: Create a paper-style loop diagram titled “evidence attribution and evaluation loop.” On the left, show retrieved evidence nodes grouped into review evidence, product text evidence, and product image evidence. In the center, show structured report claim nodes: strength claim, weakness claim, suggestion claim, and evidence gap claim. Draw directed edges from evidence nodes to claims with labels supported, partial, unsupported, and contradicted. On the right, show an evaluation module with retrieval metrics (Recall@K, MRR, NDCG) and attribution metrics (claim support rate, citation precision, modality contribution). At the bottom, draw a feedback/replay loop from evaluation and human review back to question planning and report refinement. Use blue for evidence, purple for claims, red for unsupported/evidence gaps, green for supported edges, and gray dashed arrows for replay.

*Figure 3. Evidence attribution and evaluation loop. Report claims are mapped to review, product text, and product image evidence, while evaluation measures both retrieval quality and claim grounding quality.*

## 4.7 Reproducibility and Explainability

The reproducibility of the method comes from structured intermediate representations and persistent artifacts. Product evidence, review aspects, questions, retrieval records, report claims, and evaluation metrics are represented as typed objects. This allows researchers to freeze earlier stages and replace question generation, retrieval, or reranking strategies for ablation.

The same design improves error analysis. If a final suggestion is unreliable, the error can be traced to sampling, extraction, question planning, candidate recall, reranking, report generation, or attribution calibration. This makes the framework more suitable for human review and iterative system research than black-box summarization.

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

The central conclusion is that product VOC analysis should not be reduced to one-step review summarization. It is better organized as a multi-stage workflow: review aspect modeling, evidence question planning, product text-image retrieval, and evidence-constrained generation. The current implementation forms a runnable research prototype with consistent structured intermediate representations, evidence attribution, replay mechanisms, and evaluation interfaces. The current codebase passes 166 automated tests.

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
