# 6 结果与分析

## 6.1 脚本级与测试级验证结果

系统型论文的首要结果并不只是最终报告文本，而是工作流是否能够被稳定复现。从这一角度看，本文的第一项结果是：标准化、索引、分析和论文导出已经能够被脚本化地组织为完整链路。具体而言，run_workflow.py 能够执行单商品端到端流程，validate_multimodal_runtime.py 能够验证原生多模态运行时是否启用，pipeline.py 则可完成从分章稿到 LaTeX 和 PDF 的导出。这说明系统已经具备统一入口，而非停留在手动拼接实验脚本的阶段。

自动化测试进一步为这一点提供了支撑。在当前环境中，完整测试套件共执行 157 项测试，且全部通过。这说明工作流核心、提示词模板和验证断言已经在当前代码状态下完成同步，因此系统可以被视为工程上稳定可用。

<a id="tab:engineering-results"></a>

| 维度 | 结果 | 解释 |
| --- | --- | --- |
| 端到端工作流 | 成功 | 标准化、索引、分析与导出已形成统一链路 |
| 多模态运行时验证 | 成功 | 运行时可暴露 CLIP 图像 embedding 与 Qwen-VL 图文重排配置 |
| 论文导出链路 | 成功 | 中英文分章稿均可进入合并与 PDF 导出流程 |
| 自动化测试 | 157/157 通过 | 当前验证基线已完全同步 |

*Table 3. 当前阶段的脚本级与测试级验证结果。*

## 6.2 代表性 artifact 的结构化程度

第二项结果来自分析 artifact 本身。两个代表性样例均表明，系统输出已经不再是单段自然语言总结，而是完整的结构化记录。以 backpack_010 为例，分析结果包含 extraction、questions、retrievals、retrieval_quality、retrieval_runtime、aggregates 和 report 等多个阶段对象；即使在 heuristic 模式下，系统仍能输出完整的 source_review_id、source_aspect、text_block_id 或 image_id 等溯源字段。sunglasses_001 样例进一步表明，在 LLM 路径下，系统能够围绕 3 条评论抽取 9 个 aspect，并同时汇总文本证据和图像证据。

在检索基础设施层面，相同配置下的重复运行还可以复用磁盘缓存中的 query embeddings 与 rerank 结果，只要 backend、model、base_url 和候选集保持一致即可。这不会改变分析 schema，但会让重复验证同一配置的成本更低，也更利于复现。当提供 gold labels 时，manifest evaluator 还可以进一步输出 Recall@1/3/5、MRR 和 NDCG@3/5，从而给结构化 artifact 增加更明确的评测层。

这种输出结构带来两点直接收益。首先，分析结果天然可审查，因为 strengths、weaknesses 与 suggestions 都可以回溯到具体评论和商品证据。其次，系统具备明确的错误定位接口。若最终结论存在问题，可以追查是抽样、Aspect 抽取、问题生成、检索还是聚合步骤出现偏差，而不是只能对一段黑盒总结进行整体否定。

## 6.3 案例一：backpack_010 的稀疏负例分析

backpack_010 样例展示了评论稀疏且负向反馈突出的场景。标准化报告表明，该样例包含 200 条评论和 5 张图片；在代表性分析运行中，系统根据 problem_first 抽样策略选中了 1 条 1 星评论，并从中抽取出 portability_size 这一负向 aspect。随后，系统为该 aspect 生成针对文本证据的澄清问题，检索到与 model_description 对应的文本块，并在聚合阶段将该体验维度归纳为主要问题点。

这一案例的意义不在于展示大规模统计结果，而在于表明即使在评论信息相对稀疏、证据覆盖有限的情况下，系统仍能够保持完整结构：负向评论被显式抽样、aspect 被结构化抽取、问题被独立生成、证据被单独检索，最终 weaknesses 与 suggestions 也保留了 supporting evidence 和 confidence breakdown。对于系统论文而言，这一案例说明框架不仅适用于“信息丰富的好例子”，也能够处理低资源、负向且局部证据不足的分析情形。

## 6.4 案例二：sunglasses_001 的多方面正例分析

sunglasses_001 样例则代表另一类场景：评论数量较少，但评价覆盖多个方面且场景分布丰富。在该样例中，系统基于 3 条评论抽取出 9 个正向 aspect，覆盖 value_for_money、durability、child_appeal、temperature suitability、comfort、price、design、overall_experience 和 versatility 等维度，并为这些 aspect 生成多条文本路或图像路问题。检索结果表明，系统不仅能够回收 product_name、category 和 model_description 等文本证据，还能够针对 child_appeal 和 design 等维度调用图像证据。

最终报告显示，该样例的 applicable scenes 覆盖 family use with children、children's daily wear、mild-weather wear、warm-weather or high-activity use 以及 sports, travel 等多个场景。值得注意的是，该案例并非单纯输出“全部正向”的乐观总结，而是进一步识别出 comfort evidence gap 和 design trend specificity 两项弱证据区域，并据此生成更具针对性的建议。这说明本文方法并不把“正向评论较多”简单等同于“证据充分”，而是能够在整体正向的结果中继续识别尚未被商品图文充分支撑的知觉性断言。

## 6.5 对方法主张的支持

上述两个案例共同支持本文的核心方法主张，即问题驱动检索优于评论直召回。原因在于，评论原句通常过于口语化，直接作为 query 时容易产生噪声，而问题化后的 query 更接近“需要被商品证据回答的判断任务”。在 backpack_010 中，这种机制使系统能够将“太小”这一模糊抱怨转写为关于 portability_size 的可检索问题；在 sunglasses_001 中，同一机制则使系统能够针对 child_appeal、design 与 versatility 分别调用文本和图像证据，而不是把所有评价压成单一查询。

更重要的是，问题生成步骤提升了系统可解释性。由于每条 retrieval 都显式记录了 source_question_id 和 source_aspect，最终错误分析可以精确定位到“问题是否合理”“召回是否失败”“证据是否不足”这几个不同层面。这一特征对于后续引入更细粒度检索指标和人工反馈闭环尤为重要。

## 6.6 当前阶段的结果边界

尽管上述结果已经证明系统主链可用，但它们仍属于系统验证结果，而不是完整 benchmark 结论。首先，当前框架已经支持在有标注条件下输出 Recall@1/3/5、MRR 与 NDCG@3/5，但仓库里仍缺少覆盖多品类的冻结评测集，因此本文尚不能严格量化双路召回与 reranker 的总体边际收益。其次，代表性样例能够说明系统在不同类型场景中的可用性，但尚不足以支持面向全部商品类别的统计推广。再次，图像检索虽然已经进入区域级证据 v1 阶段，但当前 region 仍来自固定 crop 而不是更细粒度的语义 grounding，因此某些与局部结构强相关的商品属性仍不能被充分分析。

## 6.7 小结

综上，当前阶段最重要的结果可以概括为三点。第一，商品 VOC 分析确实能够被组织为一条证据驱动的多阶段流程，而不必退化为黑盒总结。第二，Aspect 到问题的中间层是该流程的关键结构桥梁，它使评论理解与多模态检索实现了清晰解耦。第三，脚本、artifact 和测试三者共同表明，该原型已经具备撰写系统论文的基本成熟度，但若要迈向正式 benchmark 论文，仍需进一步扩充样本规模、补充标准检索指标和引入更严格的人工评测。