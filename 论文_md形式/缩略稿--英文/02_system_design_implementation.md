## II. Methods

This paper organizes product VOC analysis as an evidence-driven methods section. The core objective is not to directly generate a review summary, but to transform subjective feedback in reviews into a retrievable, verifiable, and attributable image-text evidence chain, and to perform question planning, evidence retrieval, experimental description, and figure presentation under a unified structure.

### Overall Architecture

Decathlon VOC Analyzer formalizes product VOC analysis as an evidence-driven multi-stage process. The system first organizes the text, images, and reviews from a product page into a unified evidence space. It then extracts aspect-level user feedback from the review side. Next, question planning converts subjective feedback into executable evidence queries. Finally, the system performs multimodal retrieval, reranking, and evidence-constrained generation across product text and product images [1,2,3,7,8,9]. Unlike one-step large-model summarization, this framework decomposes "what users expressed," "whether product evidence can support it," and "how the final report is attributed" into observable intermediate stages.

The system contains four logical layers. The product evidence layer constructs structured representations of product text, images, and local visual regions. The VOC demand layer converts reviews into aspects, opinions, sentiment, and scenarios. The evidence alignment layer rewrites aspects into questions with explicit modality routes, then retrieves and reranks candidates in the product evidence space. The report attribution layer generates structured insights and maps report claims back to review evidence and product evidence.

### Formula

To unify the ranking of a review aspect $a$ and candidate evidence $e$, this paper combines text relevance, image relevance, and cross-modal consistency into a single evidence score:

$$
S(a, e) = \lambda_t R_t(a, e) + \lambda_v R_v(a, e) + \lambda_c C(a, e)
$$

Here, $R_t(a, e)$ denotes the relevance score of the text route, $R_v(a, e)$ denotes the relevance score of the image route, and $C(a, e)$ denotes the cross-modal consistency constraint between the review aspect and product evidence. $\lambda_t$, $\lambda_v$, and $\lambda_c$ are tunable weights. This expression is not intended to replace the final generative analysis, but to provide a unified evidence selection criterion during retrieval and reranking.

### Experimental Description

In the product evidence representation stage, the system represents product titles, descriptions, categories, specifications, images, and user reviews as evidence objects with stable identifiers. Text evidence retains source fields; image evidence retains both whole images and rule-based local regions; review evidence retains ratings, language hints, and original text snippets. This establishes unified object boundaries for subsequent retrieval, attribution, and evaluation.

In the review modeling stage, the system converts natural-language feedback into aspect-level VOC units [10]. Each aspect unit contains the evaluated attribute, sentiment tendency, opinion description, original evidence snippet, usage scenario, and confidence. Aspect-level representations support both statistical aggregation and evidence-query generation around specific attributes. To prevent a limited review budget from being dominated by high-star short reviews, the system introduces star-aware sampling before review extraction and supports both a structured LLM path and a heuristic path, so as to distinguish model capability from process completeness.

In the question planning stage, the system does not use raw reviews to retrieve product evidence directly. Instead, it converts each aspect into questions with explicit evidence intent. These questions cover three types of needs: text support, visual confirmation, and cross-modal explanation. Text support questions examine whether product copy or specifications support the review opinion. Visual confirmation questions examine whether product images present the relevant structure or appearance. Cross-modal explanation questions judge whether a given feedback item is closer to a real product issue, insufficient page presentation, or a gap in user expectations.

In the retrieval and generation stage, the system adopts two-stage retrieval [11,12]. The first stage uses vector representations to coarsely recall candidate evidence from product text and product images. The second stage uses a reranking model to refine the candidate set. The text route is mainly used to verify product names, categories, descriptions, specifications, and explicit promises. The image route is mainly used to verify structure, appearance, color, and local details. The final report generates strengths, weaknesses, points of disagreement, applicable scenarios, evidence gaps, and improvement suggestions based on aspect aggregation, and marks the support relationships between claims and reviews, product text, or product images through claim-level attribution.

The system implementation uses structured objects to constrain the multi-stage process [4,5,6]. Model calls are handled through a compatible language-model gateway, and the retrieval layer supports both local indexes and vector database backends. To distinguish formal experiments from development validation, the system provides runtime policy control: when the full model pipeline is available, it uses real vector encoders, image encoders, and reranking models; when external capabilities are unavailable and the policy permits it, it falls back to heuristic paths to keep the process executable. This design avoids conflating insufficient model capability with failure of the process design.

The current validation goal of this paper is to confirm whether the system can stably complete evidence-driven VOC analysis, rather than to report final performance on a frozen large-scale benchmark. The results show that the current implementation can sequentially complete product evidence standardization, review aspect modeling, question planning, multimodal recall, candidate reranking, aspect aggregation, report generation, and evidence attribution. A complete analysis includes not only the final natural-language report, but also objects such as review aspects, question intents, retrieval questions, recalled evidence, retrieval quality, runtime configuration, aspect aggregation, process traces, and report attribution, thereby supporting human audit and error localization.

When question-level relevant evidence annotations are available, the system can compute Recall@1, Recall@3, Recall@5, MRR, NDCG@3, and NDCG@5 [13]. For structured reports, the system measures whether claims are supported by reviews, product text, or product images, including claim support rate, claim grounded rate, citation precision, citation contradiction rate, and contribution ratios across different modality routes. The current implementation includes 166 automated tests, all of which pass, indicating that the main interfaces, structured intermediate representations, and workflow assertions remain consistent in the current implementation.

### Figure 1

[Figure 1 placeholder: overall framework of evidence-driven multimodal VOC analysis]

*Figure 1. Overall framework of Decathlon VOC Analyzer. The system uses product evidence packages and review aspects as intermediate representations, connects subjective VOC signals with multimodal product evidence through question planning, and performs claim-level attribution during report generation.*

### Figure 2

[Figure 2 placeholder: transformation mechanism from review aspects to multimodal evidence queries]

*Figure 2. Planning mechanism from review aspects to evidence queries. Aspect objects do not enter retrieval directly; instead, they are first decomposed into questions with different evidence intents, which then trigger the text route, image route, or joint image-text route.*
