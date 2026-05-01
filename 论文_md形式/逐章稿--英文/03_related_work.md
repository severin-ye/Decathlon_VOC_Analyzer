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
