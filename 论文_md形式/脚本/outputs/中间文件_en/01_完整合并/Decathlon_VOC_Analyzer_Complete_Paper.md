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

Voice-of-customer analysis is a core task in e-commerce intelligence, yet review-only analysis often yields broad sentiment summaries without showing whether those conclusions are supported by product evidence. Conversely, directly feeding product text, product images, and reviews into a large language model can generate fluent summaries, but the resulting conclusions are frequently weak in evidential grounding and difficult to audit. To address this problem, we present Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis framework for product understanding. The framework constructs a normalized product-centered evidence package, performs aspect-level review modeling, converts subjective review opinions into evidence-seeking questions, retrieves supporting signals from both product text and product images, and finally produces structured product insights and improvement suggestions with explicit supporting evidence.

The present version focuses on method design and system organization rather than incorporating unfinished experimental sections into the main paper. More specifically, it explains how product-side multimodal evidence is normalized into a reusable evidence package, how review aspects are rewritten into evidence-seeking queries, and how dual-route retrieval and evidence-constrained generation are combined into a traceable analysis pipeline. In that sense, the paper should be read as a first system-paper skeleton rather than a benchmark-complete experimental article.

The main contributions of this work are threefold: it proposes a question-driven multimodal VOC analysis framework, implements a reproducible research prototype with unified Chinese-English export support, and establishes a stable paper structure into which formal experiments, human evaluation, and error analysis can be added in the next stage.

Keywords: multimodal RAG; voice-of-customer analysis; aspect extraction; evidence-constrained generation; product review analysis

# 1 Introduction

User-review analysis has long been a central task in e-commerce intelligence, yet existing approaches usually fall into one of two paradigms. The first focuses on sentiment classification or aspect-based sentiment analysis, which is effective for summarizing positive or negative attitudes in review text but weak at determining whether those opinions are supported by the product itself. The second directly feeds product text, product images, and reviews into a large language model to generate product summaries or recommendations. While such systems can quickly produce readable outputs, they often lack explicit evidence grounding, making it difficult to explain whether a conclusion comes from user reviews, product descriptions, or product imagery. For real-world product analysis tasks that require stable outputs such as strengths, weaknesses, applicable scenes, controversies, and improvement suggestions, both paradigms remain insufficient.

This paper studies the following question: how can subjective user opinions be explicitly aligned with objective product evidence in a multimodal product setting, so that the resulting VOC analysis is traceable, verifiable, and auditable? Our key observation is that the product side naturally forms a multimodal evidence space, whereas the review side is better treated as a structured textual source. The main challenge is therefore not simply generating a summary, but building an analysis chain that converts user opinions into evidence-seeking tasks. Based on this view, Decathlon VOC Analyzer does not rely on one-shot black-box summarization. Instead, it decomposes the workflow into normalization, aspect extraction, question generation, dual-route retrieval, aggregation, report generation, and replay-based continuation.

Unlike benchmark-oriented papers that prioritize final task scores, the current version of this work is positioned as a system-paper draft. The goal is not to report benchmark results before the evaluation protocol is complete, but to clearly formulate a product-oriented multimodal VOC method and instantiate it as a stable workflow with explicit intermediate artifacts. In other words, this paper first answers how such a system should be built, while leaving the question of comparative performance for a later experimental version.

The contributions of this paper are threefold. First, we propose a product-oriented analysis framework that explicitly decouples review understanding from multimodal evidence retrieval through a structured “review modeling -> question generation -> retrieval” chain. Second, we implement a reproducible research prototype with unified APIs, workflow scripts, export pipelines, and intermediate artifacts. Third, we establish a stable bilingual paper structure with a normalized citation pipeline, so that formal experiments can be added later without rewriting the core problem formulation or method section.

The remainder of this paper is organized as follows. Section 2 introduces the task background and problem formulation. Section 3 reviews related work. Section 4 presents the proposed method. Section 5 discusses the implications, applicability, and future directions of the framework. Section 6 concludes the paper, and Section 7 summarizes the current limitations.

# 2 Background and Problem Formulation

## 2.1 Task Background

Product-oriented voice-of-customer analysis is not equivalent to generic review summarization. In practice, analysts are interested in a stable set of outputs, such as product strengths, weaknesses, user concerns, applicable scenes, controversies, and improvement suggestions that can be traced back to both product evidence and review evidence. Such outputs require the system to reason over two complementary information sources: subjective user comments and objective product-side evidence, including product descriptions, specifications, and images.

If a system only processes review text, it may correctly identify subjective claims such as “the backpack is too small” or “the sunglasses look stylish,” yet it cannot determine whether these claims are supported or contradicted by product-side evidence. If a system only performs retrieval over product text and images, it becomes difficult to transform noisy, colloquial, and often mixed-purpose review statements into stable analytical units. The challenge is therefore not simply clustering text or answering multimodal questions, but constructing an explicit alignment mechanism between review-derived judgments and product-derived evidence.

## 2.2 Problem Formulation

Given a product package $P$ that contains structured product metadata, product text blocks, product images, and a set of reviews, the goal is to generate a structured analysis report $R$:

$$
R = f(P_{text}, P_{image}, C_{reviews})
$$

In our setting, however, $f$ is not a one-step generation function. Instead, it is implemented as a staged analysis pipeline:

$$
C_{reviews} \rightarrow A_{aspects} \rightarrow Q_{questions} \rightarrow E_{retrieval} \rightarrow G_{aggregates} \rightarrow R
$$

where $A_{aspects}$ denotes aspect-level review objects, $Q_{questions}$ denotes the evidence-seeking questions derived from those aspects, $E_{retrieval}$ denotes the multimodal evidence retrieved from the product package, and $G_{aggregates}$ denotes the aggregated evidence over aspects, sentiments, and scenes.

## 2.3 Design Constraints

The proposed framework is built on four design constraints. First, product-side evidence should preserve original modalities as much as possible, instead of converting all visual information into pure text at ingestion time. Second, review inputs should be transformed into structured objects early in the pipeline so that subsequent statistics, retrieval, and recommendation steps can operate over stable fields. Third, retrieval queries should not directly reuse raw review sentences, but should instead be rewritten as evidence-seeking questions. Fourth, intermediate and final outputs should be materialized as structured artifacts to support reproducibility, manual auditing, and error analysis.

## 2.4 Difference from Pure QA Systems

Although the system uses multimodal retrieval, vector indexing, structured outputs, and large language models, its objective is not open-ended question answering. The target output is a set of structured product insights, including strengths, weaknesses, controversies, applicable scenes, and suggestions. Moreover, retrieval is driven not by external user queries, but by latent questions derived from review aspects. Finally, the system emphasizes traceability throughout the workflow, as reflected in normalized packages, aspect artifacts, retrieval records, replay summaries, and final report manifests.

# 3 Related Work

## 3.1 Review Analysis and Aspect Modeling

Traditional review-analysis research has focused on sentiment classification, aspect-based sentiment analysis, and topic clustering. These approaches are useful for answering whether users are generally positive or negative and which aspects are frequently discussed, but they are less suited to explicitly aligning review conclusions with product-side evidence. For product VOC analysis, aspect modeling remains essential because it converts free-form review text into stable objects such as aspects, sentiments, opinions, evidence spans, and usage scenes. However, without an explicit evidence-retrieval stage, such systems remain at the level of “what users said,” rather than “what product evidence supports or explains those claims.”

## 3.2 Multimodal RAG and Cross-Modal Retrieval

Classical work on retrieval-augmented generation shows that separating parametric generation from external evidence retrieval is an effective way to improve traceability in knowledge-intensive tasks [1]. Follow-up work on retrieval-grounded revision further suggests that retrieved evidence can be used not only to answer questions but also to constrain and revise generated claims [2]. On the visual side, CLIP-style vision-language pretraining demonstrates that a shared image-text embedding space can support large-scale cross-modal retrieval, which motivates our treatment of product images as first-class evidence objects [3]. These studies jointly support our decision to model the product side as a dual-route text-image retrieval space.

Nevertheless, most existing multimodal RAG systems are designed for document QA, knowledge QA, or general assistants, where the query is an externally posed question. In contrast, our retrieval queries are derived from structured review aspects and are therefore part of the internal analysis chain rather than user-facing search requests.

## 3.3 Two-Stage Retrieval and Vector-Store Engineering

From a methodological perspective, RAG and its follow-up work commonly adopt a coarse-to-fine pattern in which candidate retrieval is separated from higher-precision evidence selection or revision [1,2]. This layered view does not depend on one specific vector store or one specific reranker. Instead, it highlights the importance of maintaining a clean object boundary between retrieval and final generation. Our system follows this principle by decoupling embedding services, index backends, reranking, and evidence aggregation, so that the chain “question generation -> dual-route retrieval -> reranking -> evidence aggregation” remains modular and extensible.

## 3.4 Structured Outputs and Workflow Orchestration

Recent work on structured outputs shows that schema-bound tasks remain brittle when they rely on fully unconstrained text generation, especially with respect to field consistency, type correctness, and parseability [4,5]. At the same time, reasoning-and-acting approaches suggest that multi-step stateful workflows are often better suited than one-shot prompting for coordinating tool calls, external retrieval, and intermediate object management [6]. This perspective aligns closely with our system design, because review extraction, question generation, evidence aggregation, and report generation all need outputs that are parseable, persistent, and reusable by downstream stages.

## 3.5 Difference from Existing Approaches

This work does not propose a new universal multimodal retrieval algorithm, nor does it aim to replace all intermediate stages with a single model. Instead, it contributes a task-specific system design for product VOC analysis: preserving multimodal product evidence, converting user reviews into structured aspects, rewriting those aspects into evidence-seeking questions, and using evidence-constrained generation to produce auditable product insights. In this sense, the paper is less about maximizing one benchmark score and more about designing a coherent, reproducible, and extensible analysis pipeline.

# 4 Method

## 4.1 System Architecture

The proposed system is organized into six layers: data, retrieval, review modeling, aggregation, generation-and-suggestion, and explainability-and-evaluation. The key principle is to separate review understanding from evidence retrieval rather than directly matching raw review sentences against product evidence. In other words, the system first identifies what a review is claiming, then rewrites that claim into one or more evidence-seeking questions, and finally retrieves supporting or clarifying evidence from product text and product images.

At the workflow level, single-product analysis is implemented as a four-stage chain: dataset overview, normalization, index construction, and analysis. The overview stage gathers minimal sample statistics; normalization converts raw product folders into unified evidence packages; index construction builds retrievable text and image representations; and the analysis stage performs review extraction, question generation, dual-route retrieval, aggregation, and report generation. This staged design ensures both stable execution order and artifact-level debuggability.

## 4.2 Product Evidence Modeling and Normalization

The system organizes product evidence around product_id. A normalized evidence package includes product metadata, text blocks, image objects, and reviews. Text blocks typically come from product title, category, and model description fields, while images preserve identifiers such as image_id, variant, and image_path. Unlike pipelines that immediately collapse images into textual descriptions, our system keeps images as a dedicated evidence route and only uses proxy text as an auxiliary hint during image vectorization.

Text evidence is represented via text embeddings, and image evidence via native image embeddings. In the current validated runtime, the system uses text-embedding-v4 for text embeddings, openai/clip-vit-base-patch32 for image embeddings, gte-rerank-v2 for text reranking, and qwen-vl-max-latest for multimodal reranking. When external model services are unavailable, the pipeline can fall back to heuristic or local settings without breaking the end-to-end workflow.

## 4.3 Review Modeling: From Natural Language to Aspect Objects

The review-modeling layer does not directly produce final conclusions. Instead, it transforms reviews into structured and reusable objects. Each aspect object contains at least an aspect label, sentiment, opinion, evidence span, usage scene, and confidence score. This representation allows the system to compute aspect frequency, sentiment ratios, scene distributions, and evidence-backed suggestions in a stable way.

The implementation supports two extraction paths. The first is an LLM path that uses structured prompts and typed outputs. The second is a heuristic path used as a reproducible fallback when external model calls are unavailable. To reduce review-selection bias toward only high-rating comments, the system also supports star-ratio-based sampling profiles, including problem_first, balanced, and praise_first. The goal is not to propose a novel sampling algorithm, but to make the review input controllable and to expose the sampling plan itself as a structured artifact.

## 4.4 Question Generation as Evidence-Seeking Reformulation

Question generation is the main design choice that distinguishes this framework from direct review retrieval. Raw review sentences are often colloquial, compressed, and semantically overloaded. Using them directly as retrieval queries introduces noise. The system therefore rewrites each aspect into one or more clarification questions, such as whether a product description explicitly supports the claimed experience, whether product images contain structural evidence for the judgment, or whether a complaint is more consistent with an actual defect or a user expectation mismatch.

Each generated question contains at least source_review_id, source_aspect, question text, rationale, and expected_evidence_routes. This step converts subjective review statements into evidence-seeking tasks, thereby creating the key interface between review understanding and multimodal retrieval.

## 4.5 Dual-Route Retrieval and Reranking

For each question, the system retrieves candidates from both the text route and the image route. The text route targets product title, model description, and other textual segments, whereas the image route targets product images and their variants. Candidates are unified at the product level and then reranked to form the final evidence bundle.

The implementation decouples embedding services from index backends. Embedding services are responsible for text and image vectorization, while index backends manage persistence and search. This allows the upper-layer logic to remain unchanged regardless of whether the backend is a local persistent index or a Qdrant-backed store. The retrieval design is explicitly two-stage: embedding-based candidate retrieval preserves coverage, and reranking reduces noise over a smaller candidate set.

## 4.6 Aggregation, Reporting, and Replay

Retrieved evidence is not directly passed to a summarization model. Instead, the system first aggregates evidence into aspect-level aggregates containing frequency, sentiment ratios, representative reviews, and scene distributions. Based on these aggregates, the system generates strengths, weaknesses, controversies, applicable scenes, supporting evidence, and suggestions. If LLM generation is available, a structured LLM path is used; otherwise, the system falls back to a heuristic report-construction path. Both paths share the same output schema.

The system also supports a replay-sidecar mechanism. A new run can load replay data from a previous run, merge unresolved issues and resolved items into the current report and trace, and thereby support longitudinal analysis over iterative refinements or human-review cycles.

## 4.7 Artifact-First Explainability

The system is explicitly designed to expose intermediate states as artifacts rather than hiding them in memory. Normalization outputs, aspect outputs, indexes, final reports, feedback files, replay files, HTML pages, and manifests are all persisted. Analysis artifacts further expose extraction objects, questions, retrieval records, retrieval-quality summaries, runtime profiles, aggregates, report items, traces, and warnings. This artifact-first design makes explainability concrete and inspectable rather than merely conceptual.

# 7 Discussion

## 7.1 Why This Design Fits Product VOC Analysis

The main value of the proposed framework does not lie in any isolated module, but in integrating product text, product images, review structures, and final reports into a single evidence loop. This design is particularly suitable for product VOC analysis because product information is inherently multimodal, while reviews are noisy and colloquial. If conclusions are generated directly from reviews, factual grounding becomes weak. If retrieval is only performed over product evidence, user concerns become weakly anchored. The aspect-to-question interface provides a principled bridge between these two information spaces.

## 7.2 Engineering Lessons from the Current Prototype

Three implementation lessons emerge from the current stage. First, the conceptual layers of the method should map cleanly to the implementation layers, reducing friction between design, code, and paper writing. Second, artifacts are more valuable than logs for research-oriented systems. Persisted normalization outputs, aspect outputs, retrieval records, reports, replay files, and manifests make it possible to revisit intermediate reasoning states after the run has finished. Third, real execution paths and fallback paths should coexist. The combination of LLM and heuristic modes, as well as local and Qdrant backends, allows the system to remain reproducible even when external services are unavailable.

## 7.3 Comparison with One-Shot LLM Summarization

One-shot summarization over all product and review inputs can quickly produce natural-language conclusions, but it suffers from three major limitations. First, it is difficult to determine whether a conclusion originates from review text or product evidence. Second, it is difficult to diagnose and repair local failures. Third, it is difficult to accumulate reusable intermediate artifacts for later training, auditing, or evaluation. In contrast, the staged design adopted here sacrifices some simplicity in exchange for clearer objects, greater controllability, and better explainability.

## 7.4 Implications for Future Research

One of the key implications of this study is that multimodal product analysis may be better approached from the perspective of evidence-seeking task reformulation rather than direct multimodal generation. Once review-derived needs are expressed as retrieval questions, a broad range of future extensions becomes natural: finer-grained visual evidence retrieval, stronger user-segment modeling, retrieval-specific evaluation metrics, replay optimization from human feedback, and semi-automatic audit workflows built around HTML review interfaces.

## 7.5 Implications for Paper Development

At the present stage, the most important scholarly task is not to overclaim benchmark-scale results, but to articulate the system design, experimental protocol, and method boundaries in a rigorous way. This provides a stable narrative foundation on top of which larger-scale experiments, stronger visual retrieval, and human evaluation can later be layered without rewriting the central research problem.

# 8 Conclusion

This paper presents a system-oriented draft of Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis framework for product understanding. The main claim of this work is that product-oriented VOC analysis should not be reduced to one-shot large-model summarization, but is better formulated as a structured pipeline that combines review modeling, question generation, multimodal retrieval, aggregation, and evidence-constrained reporting.

The emphasis of the current version is not to present formal experimental results, but to provide a coherent system-method narrative together with a stable bilingual paper structure, a BibTeX-based citation pipeline, and an export chain that can accommodate future evaluation sections without restructuring the core manuscript.

Future work will focus on completing the formal experimental design, introducing standard retrieval metrics, adding stricter human evaluation, and advancing from object-level visual retrieval toward finer-grained evidence alignment.

# 9 Limitations

This work must clearly distinguish between what has already been validated and what remains to be established through formal evaluation. First, the present study relies primarily on representative artifacts, script-level validation, and automated tests rather than a frozen large-scale benchmark with human annotations. Therefore, the current results should not be interpreted as statistically representative across all product categories.

Second, retrieval evaluation is still not fully closed. The current system can already report Recall@1/3/5, MRR, and NDCG@3/5 in the manifest evaluator when gold labels are available, but the repository still lacks a frozen multi-category benchmark and a systematic offline comparison between direct review retrieval and question-driven retrieval.

Third, visual evidence granularity remains relatively coarse. The main pipeline now supports region-level image evidence v1 through fixed crops used in indexing, retrieval, and reranking, but this is still a rule-based approximation rather than detector- or segmentation-driven visual grounding. As a result, product properties that depend strongly on highly localized structures may not yet be fully explainable.

Fourth, there remains a small gap between multilingual prompt evolution and validation baselines. The only failing automated test in the current environment is caused by a localization mismatch in prompt-template assertions, which suggests that multilingual engineering support and validation assets still need further synchronization.

Fifth, the paper metadata and references remain provisional. A formal submission version would require additional related-work coverage, a more standardized reference style, and finalized author and affiliation information.

# 10 Acknowledgments

This draft is prepared from the current design documents, implementation artifacts, scripts, tests, and experimental outputs of the project. A formal submission version may include acknowledgments for supervision, infrastructure support, and data preparation.

# Appendix

## A. Main Directories and Their Roles

| Directory | Role |
| --- | --- |
| 01_data | Raw product data and Chinese audit data |
| 02_outputs | Normalization outputs, aspect outputs, indexes, reports, feedback, replay, HTML, and manifests |
| 03_docs | Design documents, technical notes, and citation materials |
| 04_scripts | Workflow execution, export, and multimodal-runtime validation |
| 05_src | Core source code |
| 06_tests | API, service, and workflow tests |

## B. Current API Endpoints

The current system exposes at least the following API routes:

- /health
- /api/v1/dataset/overview
- /api/v1/dataset/normalize
- /api/v1/index/overview
- /api/v1/index/build
- /api/v1/reviews/extract
- /api/v1/analysis/product

## C. Reproducibility Commands

The main workflow can be executed with:

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010
```

The multimodal runtime can be validated with:

```bash
.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010
```

The English paper export pipeline can be executed with:

```bash
.venv/bin/python 论文_md形式/脚本/pipeline.py --en
```

## D. Current Scope of This Draft

This draft is suitable for:

- system-design reporting
- intermediate paper drafts
- project review and defense materials

It is not yet suitable for:

- a final benchmark-oriented submission requiring large-scale quantitative evaluation
- a camera-ready version with complete figures, human annotations, and fully standardized references

# References

The export pipeline generates references from BibTeX entries in ref.bib.
