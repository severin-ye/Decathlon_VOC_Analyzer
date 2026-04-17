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