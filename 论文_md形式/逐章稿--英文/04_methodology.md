# 4 Methodology

## 4.1 Overall Framework

Decathlon VOC Analyzer formulates product VOC analysis as an evidence-driven multi-stage reasoning process. The system first organizes product text, images, and reviews into a unified evidence space. It then extracts aspect-level customer feedback, converts each aspect into evidence-seeking questions, retrieves and reranks product text and image evidence, and finally generates structured reports with claim-level attribution. Unlike one-step LLM summarization, the framework separates what customers express, whether product evidence supports it, and how the final report grounds its claims.

The framework contains four logical layers. The product evidence layer constructs structured representations of product text, images, and local visual regions. The VOC demand layer converts reviews into aspects, opinions, sentiments, and usage scenes. The evidence alignment layer rewrites aspects into route-aware questions and retrieves evidence from the product evidence space. The report attribution layer generates structured insights and maps report claims back to review and product evidence.

![Figure 1. Overall framework of Decathlon VOC Analyzer. The system uses review aspects and product evidence packages as intermediate representations, connects subjective VOC signals with multimodal product evidence through question planning, and performs claim-level attribution during reporting.](图片/图1.png)

Table 1 summarizes the differences between the proposed system and traditional review summarization or aspect-based sentiment analysis in terms of output objective, evidence access, review handling, and traceability. The comparison emphasizes that this work does not treat aspect extraction as the final output. Instead, aspect objects serve as the intermediate entry point for evidence retrieval, report generation, and claim attribution.

| Dimension | Traditional review summarization / ABSA | Proposed system |
| --- | --- | --- |
| Output objective | Sentiment labels, topics, or free-form summaries | Structured VOC reports with evidence attribution |
| Product evidence access | Usually weak or absent | Joint access to text, images, and local visual regions |
| Review handling | Often aggregate statistics or direct summarization | Ratings are preserved and problem reviews are prioritized |
| Traceability | Error sources are difficult to locate | Intermediate artifacts, claim attribution, and feedback/replay are traceable |

Table 2 gives an algorithmic description of the main workflow. The key point is that each stage emits persistent structured objects, so evaluation, replay, and error localization operate over the same object system.

| Step | Input | Operation | Output |
| --- | --- | --- | --- |
| 1 | Raw product directory | Normalize product text, images, image regions, and reviews | Product evidence package |
| 2 | Review records | Filter low-information reviews, perform rating-aware sampling, extract and deduplicate aspects | Review aspect objects |
| 3 | Review aspect objects | Generate text-support, visual-confirmation, and cross-modal explanation questions | Route-aware retrieval questions |
| 4 | Questions and evidence package | Retrieve candidates through text and image routes | Candidate evidence pool |
| 5 | Candidate evidence pool | Select evidence by route, language, relevance, and reranking result | Ranked evidence bundle |
| 6 | Aspect objects and evidence bundles | Aggregate aspect statistics and generate a structured report | Strengths, weaknesses, controversies, gaps, and suggestions |
| 7 | Structured report and evidence objects | Perform claim-level attribution and evidence-gap labeling | Attributed report and run artifacts |

## 4.2 Product Evidence Representation

Product pages contain names, descriptions, categories, specifications, images, and customer reviews. If these inputs are simply concatenated into a long prompt, later conclusions become difficult to trace. The system therefore builds product-level evidence packages in which text blocks, images, image regions, and reviews are represented as stable evidence objects.

Text evidence preserves source sections such as title, description, or category. Image evidence includes whole images and rule-based local regions, enabling local visual access without annotated bounding boxes. Review records preserve rating, language hints, and original text spans. The goal is not to complete semantic interpretation at the data layer, but to establish object boundaries for retrieval, attribution, and evaluation.

## 4.3 Review Aspect Modeling

The review-side task is to convert natural language feedback into aspect-level VOC units. Each aspect contains an attribute, sentiment, opinion, evidence span, usage scene, and confidence. Compared with whole-review summarization, aspect-level representation supports both statistical aggregation and evidence retrieval.

The system uses rating-aware sampling before extraction to avoid spending limited review budget on high-rating short comments. The default policy gives more weight to low-rating reviews because they often contain higher-value product improvement signals. Aspect extraction supports both structured LLM extraction and heuristic extraction, allowing the same workflow to run under full model settings or offline validation settings.

The default sampling profile in the current implementation is `problem_first`. Given a maximum review budget, this profile assigns target weights of 30%, 25%, 20%, 15%, and 10% to 1-star through 5-star reviews, respectively. When a rating bucket cannot satisfy its target quota, the remaining budget is filled according to the fallback order of 1-star, 2-star, 3-star, 4-star, and 5-star reviews. This design does not discard positive feedback; rather, it ensures that low-rating reviews are more likely to enter the aspect extraction stage when the analysis budget is limited, increasing the chance of detecting product defects, insufficient page presentation, and expectation mismatch.

Low-information comments are also handled around the sampling and extraction stage. The system preserves original reviews with ratings, but filters empty comments, overly short comments, and short low-information reviews such as `ok` and `good` before aspect extraction. This makes the review modeling layer depend not only on the number of reviews, but also on whether a review contains diagnostic information that can be converted into aspect objects and evidence-seeking questions. Each aspect entering later stages retains the attribute, sentiment, opinion, evidence span, usage scene, and confidence, providing a unified input for question planning and aspect aggregation.

## 4.4 Aspect-to-Question Planning

The key design is the intermediate planning layer between aspects and retrieval. Aspects such as small capacity, comfortable fit, or child appeal are still subjective and underspecified. Direct retrieval with these phrases often produces broad candidates and does not indicate whether text or images should be searched. The system therefore constructs evidence-seeking questions with explicit retrieval intents.

The questions cover text support, visual confirmation, and cross-modal resolution. Text-support questions ask whether product copy or specifications directly support a claim. Visual-confirmation questions ask whether product images show relevant structures or appearances. Cross-modal questions ask whether text and images together explain a review as a real product issue, insufficient presentation, or expectation mismatch.

![Figure 2. Aspect-to-question planning. Aspect objects are not directly used as retrieval queries; they are decomposed into intent-specific questions that trigger text, image, or cross-modal evidence routes.](图片/图2.png)

## 4.5 Multimodal Recall and Reranking

The evidence alignment layer uses two-stage retrieval. The first stage performs vector-based coarse recall over product text and product images. The second stage reranks the candidate set with higher-cost models. Text and image evidence are managed as separate routes during retrieval, but they are unified in the product evidence space during attribution.

Text evidence is useful for names, descriptions, specifications, and explicit claims. Image evidence is useful for structure, appearance, color, local details, and presentation quality. Whole images and rule-based local crops allow preliminary region-level evidence to enter the VOC pipeline. The candidate pool is balanced by route and language to prevent a single route or language from dominating final evidence selection.

To place textual relevance, visual relevance, and cross-modal consistency in a unified candidate-selection framework, the evidence score between a review aspect $a$ and candidate evidence $e$ can be abstracted as:

$$
S(a,e) = \lambda_t R_t(a,e) + \lambda_v R_v(a,e) + \lambda_c C(a,e)
$$

Here, $R_t(a,e)$ denotes relevance on the text route, $R_v(a,e)$ denotes relevance on the image route, and $C(a,e)$ denotes the cross-modal consistency constraint between the review aspect, product text, and product images. The weights $\lambda_t$, $\lambda_v$, and $\lambda_c$ are tunable. The formula does not require every implementation to use a single linear scoring model. Instead, it makes explicit the three evidence sources that candidate selection should consider: whether the product text makes an explicit commitment, whether the product image visibly supports the claim, and whether the two modalities jointly explain the customer experience. This reduces attribution errors such as treating text-only similarity as visual support or treating visually plausible evidence as a product promise.

## 4.6 Evidence-Constrained Reporting and Claim Attribution

The generation stage does not pass retrieved evidence to the model as ordinary context. It first aggregates aspect signals and retrieval coverage, then generates structured reports containing strengths, weaknesses, controversies, applicable scenes, evidence gaps, and suggestions.

To make the report auditable, the system performs claim-level attribution. Major claims are mapped to review evidence, product text evidence, product image evidence, or their combinations, and are labeled as supported, partially supported, unsupported, or contradicted. If a review claim cannot be verified by current product evidence, the system prefers to expose an evidence gap instead of presenting the claim as confirmed.

![Figure 3. Evidence attribution and evaluation loop. Report claims are mapped to review, product text, and product image evidence, while evaluation measures both retrieval quality and claim grounding quality.](图片/图3.png)

## 4.7 Reproducibility and Explainability

The reproducibility of the method comes from structured intermediate representations and persistent artifacts. Product evidence, review aspects, questions, retrieval records, report claims, and evaluation metrics are represented as typed objects. This allows researchers to freeze earlier stages and replace question generation, retrieval, or reranking strategies for ablation.

The same design improves error analysis. If a final suggestion is unreliable, the error can be traced to sampling, extraction, question planning, candidate recall, reranking, report generation, or attribution calibration. This makes the framework more suitable for human review and iterative system research than black-box summarization.

At the persisted artifact level, the system saves the analysis report, review extraction output, question intents, retrieval questions, retrieval records, retrieval quality, runtime configuration, aspect aggregates, process traces, and replay summaries. The manifest records run configuration, stage artifacts, and evaluation summaries. The feedback sidecar organizes weaknesses, suggestions, and retrieval-quality issues into slots for human review. The replay sidecar stores the previous report, process trace, and retrieval quality so that later runs can identify persistent issues, resolved issues, and new issues, and can reflect accepted or rejected human feedback in report ordering and suggestion notes.

The system also applies signature-bound caching to query embeddings and rerank results. A query embedding cache signature includes the retrieval route, query text, backend type, model name, and service endpoint. A rerank cache signature additionally includes candidate count, candidate digest, reranking backend, and model configuration. The candidate digest is computed from fields such as evidence ID, product ID, route, text block, image, region, language, and score. These signature constraints reduce repeated computation while preventing cache contamination across different backends, models, or candidate sets.
