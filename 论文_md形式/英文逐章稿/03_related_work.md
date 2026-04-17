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