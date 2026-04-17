# 9 Limitations

This work must clearly distinguish between what has already been validated and what remains to be established through formal evaluation. First, the present study relies primarily on representative artifacts, script-level validation, and automated tests rather than a frozen large-scale benchmark with human annotations. Therefore, the current results should not be interpreted as statistically representative across all product categories.

Second, retrieval evaluation remains incomplete. Although the system already supports dual-route retrieval, reranking, and artifact persistence, it does not yet report standard retrieval metrics such as Recall@k, MRR, or NDCG, nor does it yet provide a systematic offline comparison between direct review retrieval and question-driven retrieval.

Third, the current image retrieval layer is still object-level rather than region-level. As a result, product properties that depend strongly on local visual structures may not yet be fully explainable.

Fourth, there remains a small gap between multilingual prompt evolution and validation baselines. The only failing automated test in the current environment is caused by a localization mismatch in prompt-template assertions, which suggests that multilingual engineering support and validation assets still need further synchronization.

Fifth, the paper metadata and references remain provisional. A formal submission version would require additional related-work coverage, a more standardized reference style, and finalized author and affiliation information.