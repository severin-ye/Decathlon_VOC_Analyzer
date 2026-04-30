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
