# 8 Conclusion

This paper presents Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system for aligning product text and image evidence with customer reviews. The system normalizes raw product data into traceable evidence packages, extracts aspect-level VOC objects from reviews, plans evidence-seeking questions, retrieves and reranks product text and image evidence, and generates structured reports with claim-level attribution.

The central conclusion is that product VOC analysis should not be reduced to one-step review summarization. It is better organized as a multi-stage workflow: review aspect modeling, evidence question planning, product text-image retrieval, and evidence-constrained generation. The current implementation forms a runnable research prototype with consistent structured intermediate representations, evidence attribution, replay mechanisms, and evaluation interfaces. The current codebase passes 166 automated tests.

The system also preserves original reviews with ratings and strengthens the role of low-rating feedback through problem-first rating-aware sampling and low-information review filtering. This design helps the system represent product-improvement signals more reliably beyond general review summarization, and provides a clearer evidence entry point for distinguishing product defects, missing page information, and expectation mismatch.

Overall, the paper shows a feasible path for turning product VOC analysis from black-box summarization into an evidence workflow. The key contribution is not a single generated report, but the structured connection among reviews, questions, evidence, reports, and evaluation.
