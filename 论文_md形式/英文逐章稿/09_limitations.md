# 9 Limitations

This work must clearly distinguish between what has already been validated and what remains to be established through formal evaluation. First, the present study relies primarily on representative artifacts, script-level validation, and automated tests rather than a frozen large-scale benchmark with human annotations. Therefore, the current results should not be interpreted as statistically representative across all product categories.

Second, retrieval evaluation is still not fully closed. The current system can already report Recall@1/3/5, MRR, and NDCG@3/5 in the manifest evaluator when gold labels are available, but the repository still lacks a frozen multi-category benchmark and a systematic offline comparison between direct review retrieval and question-driven retrieval.

Third, visual evidence granularity remains relatively coarse. The main pipeline now supports region-level image evidence v1 through fixed crops used in indexing, retrieval, and reranking, but this is still a rule-based approximation rather than detector- or segmentation-driven visual grounding. As a result, product properties that depend strongly on highly localized structures may not yet be fully explainable.

Fourth, prompt and validation baselines still require periodic upkeep as the system evolves. The current automated test suite passes, but future multilingual or prompt-template updates may still require corresponding assertion refreshes to keep documentation and validation aligned.

Fifth, the paper metadata and references remain provisional. A formal submission version would require additional related-work coverage, a more standardized reference style, and finalized author and affiliation information.