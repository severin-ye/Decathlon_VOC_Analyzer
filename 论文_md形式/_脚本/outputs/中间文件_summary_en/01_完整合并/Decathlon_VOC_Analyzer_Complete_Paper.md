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

Jaesoo Kim *†
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
† Corresponding Author

# Abstract

E-commerce VOC (Voice of Customer) analysis requires understanding both the subjective user experiences expressed in reviews and the objective evidence presented on product pages. This paper proposes Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system that explicitly aligns product images, product text, and user reviews. The system standardizes product information into evidence packages, preserves raw reviews with ratings, and constructs aspect-level VOC objects through rating-aware sampling and low-information review filtering. It then plans each aspect into questions for text support, visual confirmation, and cross-modal disambiguation, retrieves and reranks candidate evidence along text and image routes, and finally generates structured reports with claim-level evidence attribution and explicit evidence gaps. The current implementation preserves key intermediate artifacts to support reproducibility, error localization, and subsequent replay analysis, and 166 automated tests validate the stability of the core workflow.

## Keywords

multimodal VOC analysis; evidence-constrained generation; image-text retrieval; product review mining; claim attribution

# I. Introduction

User review analysis is a foundational task in intelligent e-commerce operations. Prior research has mainly focused on sentiment classification, topic clustering, and aspect-based sentiment analysis to summarize the positive or negative attitudes that users express toward product attributes. However, relatively less attention has been paid to whether such review opinions can be explained, supported, or contradicted by evidence from the product itself.

From the perspective of product operations and product improvement, it is not enough to know only that users complain about limited capacity. Analysts also need to verify whether the product page clearly states the dimensions, whether the images reveal the spatial structure, and whether the issue reflects an actual product defect or a mismatch in user expectations.

Large language models open new possibilities for product review summarization, but single-stage summarization still has limitations. If product copy, image descriptions, and the full set of reviews are fed directly into a model, the model may produce fluent outputs, yet it becomes difficult to inspect which reviews and which product evidence support a given conclusion. It is also difficult to determine whether an error arose during review understanding, retrieval, evidence interpretation, or final generation.

More broadly, existing product review analysis methods often remain at the level of sentiment statistics, topic clustering, aspect-sentiment extraction, or black-box summarization. Although these methods provide a general overview of user attitudes, they usually devote limited attention to the correspondence between review opinions and product evidence, and they rarely distinguish among product defects, insufficient page descriptions, and mismatches in user expectations. In addition, when review sampling lacks explicit constraints, high-rating or low-information reviews can occupy limited analysis budgets and weaken the representation of issues that matter most for product improvement.

Therefore, product VOC (Voice of Customer) analysis should not be treated as a black-box summarization task. Instead, it should be modeled as a traceable process that connects review needs to product evidence. This paper proposes Decathlon VOC Analyzer to align subjective experiences in user reviews with verifiable evidence from product copy and product images. In methodological terms, the system has three connected characteristics. First, it organizes review modeling, question planning, evidence retrieval, and report generation as a traceable multi-stage process so that intermediate artifacts can be reused and errors can be localized. Second, it preserves raw reviews with ratings and uses rating-aware sampling to prioritize lower-star feedback with higher diagnostic value, making review modeling more suitable for product-improvement scenarios. Third, it jointly retrieves review aspects against product text, product images, and local visual regions, while preserving claim-level evidence attribution and evidence gaps in the final report, thereby improving the inspectability, reproducibility, and actionability of the analysis results.

Figure 1 presents the overall framework of the proposed system. Starting from product evidence construction, the system preserves product text, images, local visual regions, and reviews as reusable evidence objects; it then forms VOC aspect objects through rated-review preservation, rating-aware sampling, and aspect extraction, converts them into retrieval questions with explicit route constraints, and finally generates a structured report with claim-level evidence attribution and evidence gaps.

[Figure 1 placeholder: overall framework of evidence-driven multimodal VOC analysis]

*Figure 1. Overall framework of Decathlon VOC Analyzer. The system uses review aspects and product evidence packages as intermediate representations, connects subjective VOC signals with multimodal product evidence through question planning, and performs claim-level attribution during reporting.*

# II. Proposed System

# 2.1 Overall Structure

The proposed system consists of four stages to connect subjective VOC (Voice of Customer) signals in user reviews with product image and text evidence.

First, the product evidence construction stage organizes the title, description, specifications, images, image regions, and reviews from a product page into unified evidence objects. Second, the VOC aspect modeling stage extracts aspect objects from reviews, including attributes, sentiment, opinions, original supporting spans, and usage scenarios. Third, the question-based multimodal retrieval stage converts each aspect object into retrieval questions for text support, visual confirmation, and cross-modal disambiguation, and retrieves candidate evidence from product text and product images. Fourth, the report generation stage produces a structured report containing strengths, weaknesses, improvement suggestions, and evidence gaps based on the retrieved evidence, and links each claim to review evidence, product text evidence, and product image evidence.

This structure applies the design principles of Retrieval-Augmented Generation (RAG) and image-text retrieval to product VOC analysis [1,2]. Unlike single-stage summarization, the proposed system stores the intermediate stages of review aspect extraction, question planning, evidence retrieval, and report generation separately. As a result, it becomes possible to trace which reviews and product evidence support a specific conclusion in the final report, and it also becomes easier to identify the stage at which an error occurred.

Table 1 summarizes the structural characteristics of the proposed system from three perspectives: processing targets, evidence access, and output representation.

| Dimension | Conventional review summarization / ABSA | Proposed system |
| --- | --- | --- |
| Output target | Sentiment labels, topics, or a summary paragraph | Structured VOC reports with evidence attribution |
| Product evidence access | Usually weak or absent | Joint access to text, images, and local visual regions |
| Review processing | Often based on overall statistics or direct aggregation | Preserves ratings and prioritizes problem-oriented reviews |
| Traceability | Difficult to locate the source of errors | Traceable through intermediate artifacts, claim attribution, and replay |

The overall workflow has already been presented in Figure 1, and the key design of each stage is detailed below. The product evidence layer preserves product text, images, local visual regions, and reviews as reusable evidence objects, and assigns stable identifiers to text blocks, images, image regions, and reviews to support subsequent indexing, caching, and attribution. The VOC aspect modeling layer first preserves raw reviews with ratings and then performs rating-aware sampling under a limited computation budget. The current default profile is problem_first, which assigns target quotas of 30%, 25%, 20%, 15%, and 10% to 1-star through 5-star reviews, respectively; when low-star samples are insufficient, the remaining budget is redistributed by a fallback order. At the same time, the system filters empty reviews, overly short reviews, and low-information short comments such as ok and good to improve the diagnostic value of the review sample. The question-based multimodal retrieval layer then converts review aspects into questions with explicit retrieval intents and routes. Finally, the reporting layer links each final claim back to review evidence, product text evidence, and product image evidence.

## 2.2 Question-Planning-Based Multimodal Retrieval

The proposed system does not directly use raw review sentences as retrieval queries. Review sentences are highly context-dependent and unstable in expression, so even the same complaint may appear in different forms, such as “too small,” “not enough storage,” or “documents do not fit.” Therefore, the system first decomposes each review aspect into three evidence intents: explicit text support, visual confirmation, and cross-modal disambiguation [3].

Text support questions are used to verify whether product descriptions and specifications support a review opinion. Visual confirmation questions are used to examine whether product images show the relevant structure or appearance. Cross-modal disambiguation questions are used to determine whether text and images provide the same explanation. By transforming review expressions into verifiable questions, this design reduces the expression drift caused by directly retrieving with raw review sentences and improves both evidence hit rate and interpretability. At the same time, the system explicitly preserves text and image routes during question planning to constrain route-specific retrieval and reranking in later stages [4].

Figure 2 shows the question-planning process from a review aspect to evidence queries. For example, a review such as “too small for travel documents” is converted into an aspect object containing a size aspect, negative sentiment, a usage scenario, and an original evidence span. The system then generates separate questions to determine whether the product description or specifications explicitly mention size limits, whether the main storage compartment can be identified in the images, and whether text and images provide consistent evidence about storage capacity. The key point is not merely to generate multiple questions, but to ensure that each question carries an explicit evidence route and an expected support type, so that subsequent retrieval results can be aligned precisely with the final report claims.

[Figure 2 placeholder: transformation from review aspects to multimodal evidence queries]

*Figure 2. Aspect-to-question planning. Aspect objects are not directly used as retrieval queries; they are decomposed into intent-specific questions that trigger text, image, or cross-modal evidence routes.*

## 2.3 Evidence Scoring and Reranking

To compare the relevance between review aspects and candidate evidence consistently, the proposed system uses an evidence score that combines text relevance, image relevance, and cross-modal consistency. Let a review aspect be denoted by $a$ and candidate evidence by $e$. The evidence score is defined in Equation (1).

$$
S(a,e) = \lambda_t R_t(a,e) + \lambda_v R_v(a,e) + \lambda_c C(a,e) \tag{1}
$$

In Equation (1), $R_t(a,e)$ denotes relevance along the text route, $R_v(a,e)$ denotes relevance along the image route, and $C(a,e)$ denotes the cross-modal consistency constraint between the review aspect and product evidence. The parameters $\lambda_t$, $\lambda_v$, and $\lambda_c$ are tunable weights. This equation is not used to generate the final analysis directly. Instead, it provides a consistent criterion for selecting candidate evidence during retrieval and reranking.

The significance of this formulation is to avoid decisions that rely only on one route score, thereby reducing attribution errors such as cases where the text appears relevant but the image does not support it, or where the image seems plausible but the product specification makes no corresponding promise.

The proposed system first retrieves candidate evidence from the text route and the image route, and then reranks the candidates according to Equation (1). The text route is used to inspect document-based information such as product names, categories, descriptions, specifications, and explicit promises. The image route is used to inspect visual cues such as product structure, appearance, color, storage form, as well as opening styles, connectors, and material textures that are often carried by local components. The cross-modal consistency term is used to determine whether an issue raised in a review can be explained jointly by product text and product images. This route-specific retrieval, route-specific reranking, and late fusion mechanism helps preserve region-level evidence beyond whole-image semantics, reduces interference from background and overall composition, and supports a finer-grained distinction among supported, partially supported, and insufficient-evidence states.

# III. Implementation and Evaluation

The system implementation is designed to preserve multi-stage analysis results as structured objects. The product evidence package represents product names, descriptions, categories, specifications, images, and reviews as objects with stable identifiers. Review aspect objects include aspect names, sentiment, opinions, original evidence, usage scenarios, and confidence. In the retrieval and reporting stages, the system also stores retrieved evidence, question intent, execution settings, aspect aggregation, and report attribution as separate artifacts to support reproducibility and error localization.

The main intermediate artifacts of the proposed system include the product evidence package, review aspect objects, retrieval candidate pools, structured reports, and runtime by-products such as manifest and replay files. The product evidence package provides the basis for index construction and evidence back-referencing, while review aspect objects serve as inputs to question planning and aspect aggregation. Retrieval candidate pools and structured reports support evidence selection for final claims and downstream business decision-making. Meanwhile, manifest and replay preserve execution settings and intermediate outputs for experimental reproducibility and error analysis. Specifically, the manifest records runtime configurations, workflow stages, and evaluation summaries, while replay stores continuity information from previous runs so that human feedback can flow back into subsequent question planning and report refinement.

The current implementation includes APIs for inspecting dataset overviews, normalizing product data, building indexes, extracting review aspects, and conducting integrated single-product analysis. It also provides scripts for full workflow execution, offline execution, multimodal runtime validation, manifest evaluation, and automated testing. This structure makes it possible to trace which intermediate artifacts were produced for the same input product even when the experimental environment changes, and it helps distinguish insufficient model capability from failures in process design. To reduce repeated execution costs, the system also applies signature-bound disk caching to query embeddings and reranking results, so that cache entries are jointly constrained by backend, model, and candidate-set summaries. This design reduces redundant computation during repeated experiments while avoiding cache pollution across different runtime configurations.

From the evaluation perspective, the proposed system examines retrieval quality and attribution quality separately. When question-level relevant evidence annotations are available, retrieval performance can be evaluated using Recall@K, MRR (Mean Reciprocal Rank), and NDCG (Normalized Discounted Cumulative Gain) [5]. Recall@K measures whether the correct evidence appears within the top-K candidates, MRR averages the reciprocal rank of the first correct evidence, and NDCG evaluates whether highly relevant evidence is placed near the top of the ranking.

For structured reports, the proportion of claims supported by reviews, product text, and product images can be computed. In addition, metrics such as citation precision, contradiction rate, and modality contribution can be used to assess the sufficiency of the evidence behind report claims and the contribution of each modality. These metrics reflect not only whether the system retrieved relevant evidence, but also whether the final conclusions are adequately supported. The present evaluation focuses on the stable operation of an evidence-driven VOC analysis prototype and on the separability of individual modules for future ablation and comparison studies. Under this setting, later experiments can evaluate the impact of removing question planning, disabling the image route, removing reranking, or turning off claim attribution on evidence hit rate, attribution error rate, and report auditability.

Figure 3 illustrates how retrieved review evidence, product text evidence, and product image evidence are connected to strength claims, weakness claims, improvement-suggestion claims, and evidence-gap claims in the structured report. Each connection can be labeled as supported, partial, unsupported, or contradicted, and human review results can be fed back into question planning and report refinement through the feedback/replay loop. For review opinions that cannot be sufficiently supported by product text or images, the system does not force a seemingly plausible conclusion but instead preserves an explicit evidence gap to represent insufficient support. The current implementation has passed 166 automated tests, indicating that the main interfaces and workflow assertions remain consistent and that the system has achieved sufficient engineering stability as a research prototype for subsequent controlled experiments.

[Figure 3 placeholder: evidence attribution and evaluation loop]

*Figure 3. Evidence attribution and evaluation loop. Report claims are mapped to review, product text, and product image evidence, while evaluation measures both retrieval quality and claim grounding quality.*

# IV. Conclusion

This paper proposed Decathlon VOC Analyzer, an evidence-driven multimodal VOC (Voice of Customer) analysis system for aligning product image-text evidence with user reviews. The proposed system standardizes raw product data into traceable evidence packages, extracts user reviews into aspect-level VOC objects, and then generates structured product analysis results through question planning, multimodal candidate retrieval, reranking, report generation, and claim-level attribution.

The core conclusion of this study is that product VOC analysis should not be compressed into a single-stage review summarization task, but should instead be constructed as a multi-stage process that combines review aspect modeling, evidence question planning, product image-text retrieval, and evidence-constrained generation. The proposed system organizes what reviews say, whether product evidence supports those opinions, and how final conclusions establish evidence correspondence into connected analytical steps, thereby providing a unified interface for evidence matching, error localization, and subsequent comparative experiments.

At the same time, the system preserves raw reviews with ratings and strengthens the role of lower-star feedback in review modeling through problem-oriented rating-aware sampling and low-information review filtering. This design allows the system to represent issue signals that are more directly related to product improvement more stably, rather than merely producing an overall summary of reviews.

Future work will extend manually annotated datasets across multiple product categories, conduct comparative experiments on modules such as question planning, the image route, reranking, and claim attribution, and strengthen finer-grained visual evidence linking together with feedback-driven re-execution mechanisms so that the system can be further developed into a VOC analysis platform that better serves product-improvement decisions.
