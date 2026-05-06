# IV. Conclusion

This paper proposed Decathlon VOC Analyzer, an evidence-driven multimodal VOC (Voice of Customer) analysis system for aligning product image-text evidence with user reviews. The proposed system standardizes raw product data into traceable evidence packages, extracts user reviews into aspect-level VOC objects, and then generates structured product analysis results through question planning, multimodal candidate retrieval, reranking, report generation, and claim-level attribution.

The central conclusion of this study is that product VOC analysis should not be reduced to a single-stage review summarization task. Instead, it should be constructed as a multi-stage process that combines review aspect modeling, evidence question planning, product image-text retrieval, and evidence-constrained generation. By preserving structured intermediate artifacts and evidence attribution information, the current implementation improves the inspectability and reproducibility of analysis results.

Future work will extend manually annotated datasets across multiple product categories, conduct comparative experiments on retrieval and reranking strategies, and strengthen finer-grained visual evidence linking together with human-feedback-driven re-execution mechanisms so that the system can better support product improvement decisions.
