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
