# 4 Method

## 4.1 System Architecture

The proposed system is organized into six layers: data, retrieval, review modeling, aggregation, generation-and-suggestion, and explainability-and-evaluation. The key principle is to separate review understanding from evidence retrieval rather than directly matching raw review sentences against product evidence. In other words, the system first identifies what a review is claiming, then rewrites that claim into one or more evidence-seeking questions, and finally retrieves supporting or clarifying evidence from product text and product images.

At the workflow level, single-product analysis is implemented as a four-stage chain: dataset overview, normalization, index construction, and analysis. The overview stage gathers minimal sample statistics; normalization converts raw product folders into unified evidence packages; index construction builds retrievable text and image representations; and the analysis stage performs review extraction, question generation, dual-route retrieval, aggregation, and report generation. This staged design ensures both stable execution order and artifact-level debuggability.

## 4.2 Product Evidence Modeling and Normalization

The system organizes product evidence around product_id. A normalized evidence package includes product metadata, text blocks, image objects, and reviews. Text blocks typically come from product title, category, and model description fields, while images preserve identifiers such as image_id, variant, and image_path. Unlike pipelines that immediately collapse images into textual descriptions, our system keeps images as a dedicated evidence route and only uses proxy text as an auxiliary hint during image vectorization.

Text evidence is represented via text embeddings, and image evidence via native image embeddings. In the current validated runtime, the system uses text-embedding-v4 for text embeddings, openai/clip-vit-base-patch32 for image embeddings, gte-rerank-v2 for text reranking, and qwen-vl-max-latest for multimodal reranking. When external model services are unavailable, the pipeline can fall back to heuristic or local settings without breaking the end-to-end workflow.

## 4.3 Review Modeling: From Natural Language to Aspect Objects

To reduce repeated execution cost, stage 3 retrieval also stores query embeddings and rerank outputs in a disk cache. The cache signature is tied to the backend, model, base_url, and candidate-set digest, so identical configurations can reuse results while different configurations remain isolated.

The review-modeling layer does not directly produce final conclusions. Instead, it transforms reviews into structured and reusable objects. Each aspect object contains at least an aspect label, sentiment, opinion, evidence span, usage scene, and confidence score. This representation allows the system to compute aspect frequency, sentiment ratios, scene distributions, and evidence-backed suggestions in a stable way.

The implementation supports two extraction paths. The first is an LLM path that uses structured prompts and typed outputs. The second is a heuristic path used as a reproducible fallback when external model calls are unavailable. To reduce review-selection bias toward only high-rating comments, the system also supports star-ratio-based sampling profiles, including problem_first, balanced, and praise_first. The goal is not to propose a novel sampling algorithm, but to make the review input controllable and to expose the sampling plan itself as a structured artifact.

## 4.4 Question Generation as Evidence-Seeking Reformulation

Question generation is the main design choice that distinguishes this framework from direct review retrieval. Raw review sentences are often colloquial, compressed, and semantically overloaded. Using them directly as retrieval queries introduces noise. The system therefore rewrites each aspect into one or more clarification questions, such as whether a product description explicitly supports the claimed experience, whether product images contain structural evidence for the judgment, or whether a complaint is more consistent with an actual defect or a user expectation mismatch.

Each generated question contains at least source_review_id, source_aspect, question text, rationale, and expected_evidence_routes. This step converts subjective review statements into evidence-seeking tasks, thereby creating the key interface between review understanding and multimodal retrieval.

## 4.5 Dual-Route Retrieval and Reranking

For each question, the system retrieves candidates from both the text route and the image route. The text route targets product title, model description, and other textual segments, whereas the image route targets product images and their variants. Candidates are unified at the product level and then reranked to form the final evidence bundle.

The implementation decouples embedding services from index backends. Embedding services are responsible for text and image vectorization, while index backends manage persistence and search. This allows the upper-layer logic to remain unchanged regardless of whether the backend is a local persistent index or a Qdrant-backed store. The retrieval design is explicitly two-stage: embedding-based candidate retrieval preserves coverage, and reranking reduces noise over a smaller candidate set.

## 4.6 Aggregation, Reporting, and Replay

When gold labels are available on the evaluation side, ManifestEvaluationService can additionally report Recall@1/3/5, MRR, and NDCG@3/5 as complementary validation metrics.

Retrieved evidence is not directly passed to a summarization model. Instead, the system first aggregates evidence into aspect-level aggregates containing frequency, sentiment ratios, representative reviews, and scene distributions. Based on these aggregates, the system generates strengths, weaknesses, controversies, applicable scenes, supporting evidence, and suggestions. If LLM generation is available, a structured LLM path is used; otherwise, the system falls back to a heuristic report-construction path. Both paths share the same output schema.

The system also supports a replay-sidecar mechanism. A new run can load replay data from a previous run, merge unresolved issues and resolved items into the current report and trace, and thereby support longitudinal analysis over iterative refinements or human-review cycles.

## 4.7 Artifact-First Explainability

The system is explicitly designed to expose intermediate states as artifacts rather than hiding them in memory. Normalization outputs, aspect outputs, indexes, final reports, feedback files, replay files, HTML pages, and manifests are all persisted. Analysis artifacts further expose extraction objects, questions, retrieval records, retrieval-quality summaries, runtime profiles, aggregates, report items, traces, and warnings. This artifact-first design makes explainability concrete and inspectable rather than merely conceptual.