# 9 Limitations

First, the current results are system validation results. The system supports manifest evaluation and automated testing, but this paper does not build a frozen multi-category human-labeled dataset and therefore does not report cross-product performance rankings.

Second, this paper does not report retrieval-strategy ablations. The implementation supports text routes, image routes, question-driven retrieval, reranking, and caching, but these capabilities are described as system components rather than ranked against one another.

Third, visual evidence granularity is limited. The system supports whole images and fixed-ratio crops, but these regions are not produced by semantic detection, segmentation, or grounding models.

Fourth, LLM outputs still depend on prompts and schema constraints. Structured output, refinement, and heuristic fallbacks reduce but do not eliminate misunderstanding, omission, or overgeneralization.

Fifth, the feedback loop is still mostly an engineering interface. Feedback and replay sidecars exist, but this paper does not quantify the quality impact of replay on later reports.

Sixth, image evidence is still based on whole images and rule-based regions. The relevant claims should be understood as a system interface for local visual evidence rather than proof of precise visual grounding.
