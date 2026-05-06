# II. Proposed System

## 2.1 Overall Structure

The proposed system consists of four stages to connect subjective VOC (Voice of Customer) signals in user reviews with product image and text evidence.

First, the product evidence construction stage organizes the title, description, specifications, images, image regions, and reviews from a product page into unified evidence objects. Second, the VOC aspect modeling stage extracts aspect objects from reviews, including attributes, sentiment, opinions, original supporting spans, and usage scenarios. Third, the question-based multimodal retrieval stage converts each aspect object into retrieval questions for text support, visual confirmation, and cross-modal disambiguation, and retrieves candidate evidence from product text and product images. Fourth, the report generation stage produces a structured report containing strengths, weaknesses, improvement suggestions, and evidence gaps based on the retrieved evidence, and links each claim to review evidence, product text evidence, and product image evidence.

This structure applies the design principles of Retrieval-Augmented Generation (RAG) and image-text retrieval to product VOC analysis [1,2]. Unlike single-stage summarization, the proposed system stores the intermediate stages of review aspect extraction, question planning, evidence retrieval, and report generation separately. As a result, it becomes possible to trace which reviews and product evidence support a specific conclusion in the final report, and it also becomes easier to identify the stage at which an error occurred.

Figure 1 illustrates the overall framework of the proposed system. The product evidence layer preserves product text, images, local visual regions, and reviews as reusable evidence objects. The VOC aspect modeling layer filters reviews, performs rating-aware sampling, and then creates aspect objects. The question-based multimodal retrieval layer converts review aspects into questions with explicit retrieval intent and route. Finally, the report layer links each final claim back to review evidence, product text evidence, and product image evidence.

## 2.2 Question-Planning-Based Multimodal Retrieval

The proposed system does not directly use raw review sentences as retrieval queries. Review sentences are highly context-dependent and unstable in expression, so even the same complaint may appear in different forms, such as “too small,” “not enough storage,” or “documents do not fit.” Therefore, the system first decomposes each review aspect into three evidence intents: explicit text support, visual confirmation, and cross-modal disambiguation [3].

Text support questions verify whether product descriptions and specifications support the review opinion. Visual confirmation questions examine whether product images show the relevant structure or appearance. Cross-modal disambiguation questions verify whether text and images provide the same interpretation. This design makes it possible to trace which claim in the final report is supported by a retrieval result, and it improves the inspectability of generated outputs through structured output constraints [4].

Figure 2 shows the question-planning process from a review aspect to evidence queries. For example, a review such as “too small for travel documents” is converted into an aspect object containing a size aspect, negative sentiment, a usage scenario, and an original evidence span. The system then generates separate questions to determine whether the product description or specifications explicitly mention size limits, whether the main storage compartment can be identified in the images, and whether text and images provide consistent evidence about storage capacity.

## 2.3 Evidence Scoring and Reranking

To compare the relevance between review aspects and candidate evidence consistently, the proposed system uses an evidence score that combines text relevance, image relevance, and cross-modal consistency. Let a review aspect be denoted by $a$ and candidate evidence by $e$. The evidence score is defined in Equation (1).

$$
S(a,e) = \lambda_t R_t(a,e) + \lambda_v R_v(a,e) + \lambda_c C(a,e) \tag{1}
$$

In Equation (1), $R_t(a,e)$ denotes relevance along the text route, $R_v(a,e)$ denotes relevance along the image route, and $C(a,e)$ denotes the cross-modal consistency constraint between the review aspect and product evidence. The parameters $\lambda_t$, $\lambda_v$, and $\lambda_c$ are tunable weights. This equation is not used to generate the final analysis directly. Instead, it provides a consistent criterion for selecting candidate evidence during retrieval and reranking.

The proposed system first retrieves candidate evidence from the text route and the image route, and then reranks the candidates using Equation (1). The text route is used to inspect document-based information such as product names, categories, descriptions, specifications, and explicit promises. The image route is used to inspect product structure, appearance, color, storage form, and local visual regions. The cross-modal consistency term is used to determine whether an issue raised in a review can be explained jointly by product text and product images.

# III. Implementation and Evaluation

The system implementation is designed to preserve multi-stage analysis results as structured objects. The product evidence package represents product names, descriptions, categories, specifications, images, and reviews as objects with stable identifiers. Review aspect objects include aspect names, sentiment, opinions, original evidence, usage scenarios, and confidence. In the retrieval and reporting stages, the system also stores retrieved evidence, question intent, execution settings, aspect aggregation, and report attribution as separate artifacts to support reproducibility and error localization.

The main intermediate artifacts of the proposed system are summarized in Table 1. In Table 1, the product evidence package serves as the basis for index construction and evidence back-referencing, while review aspect objects are used as inputs to question planning and aspect aggregation. The retrieval candidate pool and structured report are used for evidence selection behind final claims and for business decision support. In addition, manifest/replay preserves execution settings and intermediate results to support experimental reproducibility and error analysis.

The current implementation includes APIs for inspecting dataset overviews, normalizing product data, building indexes, extracting review aspects, and conducting integrated single-product analysis. It also provides scripts for full workflow execution, offline execution, multimodal runtime validation, manifest evaluation, and test execution. This structure makes it possible to trace which intermediate artifacts were produced for the same input product even when the experimental environment changes, and it helps distinguish insufficient model capability from failure in process design.

From the evaluation perspective, the proposed system examines retrieval quality and attribution quality separately. When question-level relevant evidence annotations are available, retrieval performance can be evaluated using Recall@K, MRR (Mean Reciprocal Rank), and NDCG (Normalized Discounted Cumulative Gain) [5]. Recall@K measures whether the correct evidence appears within the top-K candidates, MRR averages the reciprocal rank of the first correct evidence, and NDCG evaluates whether highly relevant evidence is placed near the top of the ranking.

For structured reports, the proportion of claims supported by reviews, product text, and product images can be computed. In addition, metrics such as citation precision, contradiction rate, and modality contribution can be used to assess the groundedness of report claims and the contribution of each modality. At the current stage, the focus is not on reporting final performance on a large manually annotated benchmark, but on verifying whether the evidence-based VOC analysis prototype can run stably.

Figure 3 illustrates how retrieved review evidence, product text evidence, and product image evidence are connected to strength claims, weakness claims, improvement-suggestion claims, and evidence-gap claims in the structured report. Each connection can be labeled as supported, partial, unsupported, or contradicted, and human review results can be fed back into question planning and report refinement through the feedback/replay loop. The current implementation passes 166 automated tests, indicating that the main interfaces and workflow assertions remain consistent.
