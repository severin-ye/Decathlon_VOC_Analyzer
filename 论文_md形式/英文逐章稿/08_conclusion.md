# 8 Conclusion

This paper presents Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system for aligning product text and image evidence with customer reviews. The system normalizes raw product data into traceable evidence packages, extracts aspect-level VOC objects from reviews, plans evidence-seeking questions, retrieves and reranks product text and image evidence, and generates structured reports with claim-level attribution.

The central conclusion is that product VOC analysis should not be reduced to one-step review summarization. It is better organized as a multi-stage workflow: review aspect modeling, evidence question planning, product text-image retrieval, and evidence-constrained generation. The current implementation forms a runnable research prototype with consistent structured intermediate representations, evidence attribution, replay mechanisms, and evaluation interfaces. The current codebase passes 166 automated tests.

Future work will add multi-category human-labeled benchmarks, compare retrieval and reranking strategies, improve visual grounding, and close the feedback/replay loop with human review.
