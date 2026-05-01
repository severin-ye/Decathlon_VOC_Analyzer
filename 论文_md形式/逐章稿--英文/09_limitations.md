# 9 Limitations

First, the current results are system validation results rather than a complete benchmark. The system supports manifest evaluation and automated testing, but it does not yet include a frozen multi-category human-labeled dataset.

Second, retrieval strategies still require systematic ablation. The implementation supports text routes, image routes, question-driven retrieval, reranking, and caching, but direct comparisons among raw-review retrieval, aspect retrieval, question-driven retrieval, embedding backends, and reranker backends remain future work.

Third, visual evidence granularity is limited. The system supports whole images and fixed-ratio crops, but these regions are not produced by semantic detection, segmentation, or grounding models.

Fourth, LLM outputs still depend on prompts and schema constraints. Structured output, refinement, and heuristic fallbacks reduce but do not eliminate misunderstanding, omission, or overgeneralization.

Fifth, the feedback loop is still mostly an engineering interface. Feedback and replay sidecars exist, but their quality impact has not yet been quantified through large-scale human review.

Sixth, a submission-ready paper will require a broader related-work section, formal figures, detailed annotation protocols, and statistical analysis.
