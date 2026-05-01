# 2 Background and Problem Definition

## 2.1 Evidence Needs in Product VOC Analysis

Product VOC analysis is not equivalent to generic review summarization. A useful product report should contain stable analytical objects such as strengths, weaknesses, controversies, applicable scenes, evidence gaps, and improvement suggestions. Each insight should ideally trace back to both customer review evidence and product-page evidence.

If a system only analyzes reviews, it answers what customers say but not whether the product page explains or supports those claims. If a system only retrieves product-page evidence, it lacks the anchor of actual customer concerns. Therefore, the key challenge is connecting subjective review needs with objective product evidence.

## 2.2 Input and Output

Given a product package $P$ containing product text $P_{text}$, product images $P_{image}$, and reviews $C_{reviews}$, the system outputs a structured report $R$:

$$
R = F(P_{text}, P_{image}, C_{reviews})
$$

In this paper, $F$ is not a one-step generation function. It is a staged workflow:

$$
C_{reviews} \rightarrow A_{aspects} \rightarrow I_{intents} \rightarrow Q_{questions} \rightarrow E_{retrieval} \rightarrow G_{aggregates} \rightarrow R_{attributed}
$$

where $A_{aspects}$ denotes review aspects, $I_{intents}$ denotes question intents, $Q_{questions}$ denotes executable retrieval questions, $E_{retrieval}$ denotes retrieved product evidence, $G_{aggregates}$ denotes aspect-level aggregation, and $R_{attributed}$ denotes the final attributed report.

## 2.3 Design Constraints

The system follows five constraints. Product evidence must be object-based and traceable. Reviews must be structured into aspects before retrieval. Retrieval queries should be questionized instead of using raw review text. Text and image evidence should be managed as separate routes. Final report claims should be traceable to review IDs, text block IDs, image IDs, or region IDs; unsupported claims should be represented as evidence gaps.

## 2.4 Difference from Generic RAG QA

Generic RAG systems usually answer a user question. In this task, the query source is a set of review aspects, and the output is a product VOC profile rather than a single answer. The system must manage multiple aspects, questions, evidence routes, report fields, and trace objects, making it closer to an evidence orchestration system than a standard QA pipeline.
