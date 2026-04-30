# 论文子模块文档总览

本目录基于当前源码实现整理，用于后续论文写作。旧设计文档中有些内容已经与实现脱节，因此本目录不直接复述旧方案，而是按 `05_src/decathlon_voc_analyzer/` 的真实模块边界重新组织。

## 模块划分

- `01_数据集与商品证据标准化.md`：对应 `stage1_dataset`，说明原始商品、评论、图像如何被标准化为可追踪证据包。
- `02_评论建模与抽样.md`：对应 `stage2_review_modeling`，说明评论清洗、星级抽样、方面级结构化抽取和去重。
- `03_多模态索引与召回.md`：对应 `stage3_retrieval` 的索引、embedding、双路召回和语言均衡候选池。
- `04_重排缓存与本地推理.md`：对应 `stage3_retrieval` 的 reranker、检索缓存、本地模型与 OpenVINO 相关能力。
- `05_问题规划与证据查询生成.md`：对应 `stage4_generation/question_service.py`，说明如何把评论方面转成可检索问题。
- `06_报告生成证据归因与回放.md`：对应 `stage4_generation/analysis_service.py`、报告 refine、侧边车与 HTML 输出。
- `07_工作流编排与批处理.md`：对应 `workflows` 与脚本入口，说明 LangGraph 单产品流水线。
- `08_API配置LLM与提示词层.md`：对应 `app`、`llm`、`prompts` 与运行策略。
- `09_Schema与可解释性数据结构.md`：对应 `schemas`，说明系统为什么以结构化 schema 作为论文方法的核心约束。
- `10_评估模块与实验指标.md`：对应 `evaluation`，说明 manifest 评测、检索指标和证据归因指标。

## 写作用途

这些文档可拆入论文的方法章节、系统实现章节和实验章节。建议后续论文中把本项目的核心创新概括为：面向电商 VOC 的证据驱动多模态 RAG 框架，以评论方面为需求入口，以商品图文为证据空间，以问题规划、双路召回、重排、证据归因和回放机制降低生成式分析的幻觉风险。
