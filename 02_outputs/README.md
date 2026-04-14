# 02_outputs 目录说明

本目录用于存放项目运行过程中生成的中间结果、索引数据、分析报告与人工审核产物。

它不是原始数据区，也不是源码区，而是整个分析链路的“产出物落盘目录”。

## 总体分工

- `1_normalized/`：原始数据集的标准化输出。
- `CN/1_normalized/`：中文审查数据集的标准化输出。
- `2_aspects/`：原始语言数据跑完评论建模后的 aspect 结果。
- `CN/2_aspects/`：中文审查数据跑完评论建模后的 aspect 结果。
- `3_indexes/`：原始语言数据对应的检索索引与向量库运行目录。
- `CN/3_indexes/`：中文审查数据对应的检索索引。
- `4_reports/`：面向原始数据集生成的最终分析报告。
- `CN/4_reports/`：面向中文审查数据集生成的最终报告与人工审核文件。

## 子目录详解

### 1_normalized

该目录存放“数据标准化”阶段的输出。常见内容包括：

- 商品基础信息的统一结构化结果
- 评论、图片、商品描述之间的对齐结果
- 数据质量检查后的标准化证据包

它主要服务于后续几个阶段：

- 评论抽取与 aspect 建模
- 检索索引构建
- 生成最终商品分析报告

如果你要排查“原始数据进入系统后被整理成了什么样”，通常先看这里。

### 2_aspects

该目录存放针对原始商品数据跑出的评论结构化结果。通常表示：

- 评论中提取出的 aspect
- 每个 aspect 对应的情感倾向、证据评论、摘要信息
- 后续问题生成和检索所需的中间建模结果

可以把它理解成“评论建模层的落盘结果”。

### CN/2_aspects

该目录与 `2_aspects/` 含义相同，但服务于中文审查数据集。它主要用于：

- 单商品中文审查
- 人工校对模型抽取结果
- 对比中文化后的分析链路是否稳定

当你在审核 `backpack_010` 的中文链路时，优先看这里和 `CN/4_reports/`。

### 3_indexes

该目录存放原始数据集对应的检索索引与向量库运行结果。

当前可以看到两类内容：

- `local_evidence_index.json`
- 多个 `qdrant_*` 目录

#### local_evidence_index.json

这是本地持久化索引的落盘文件，用于保存商品图文证据的索引信息。适用于：

- 本地检索后端
- 快速调试
- 不依赖独立向量数据库时的 MVP 跑通

#### qdrant_store

这是当前默认或长期保留的 Qdrant 本地存储目录。里面包含：

- `.lock`
- `manifest.json`
- `meta.json`
- `collection/product_evidence/`

它代表一个可持续复用的本地 Qdrant 数据目录。

#### qdrant_runtime_backpack_010*

这些目录是针对 `backpack_010` 做运行时验证时产生的 Qdrant 数据目录，通常用于：

- 单次实验
- 回归验证
- 不同版本的召回/精排效果对比

命名中的 `v2`、`v3`、`v4`、`v5` 表示同一商品在不同实验轮次下的运行目录。

这类目录更偏“实验态产物”，不是长期必须保留的核心成果。

#### qdrant_validation_backpack_010_20260408*

这类目录是带日期标记的验证索引目录，说明它们对应某次明确记录的验证批次。相比 `runtime` 目录，它们更偏：

- 验证留档
- 阶段性结果追溯
- 与报告文件相互对应

如果后续需要清理索引目录，建议优先保留：

- `qdrant_store/`
- 带明确日期和用途的 `qdrant_validation_*`

### CN/3_indexes

该目录用于中文审查数据集的索引存储。当前包含：

- `local_evidence_index.json`

它服务于中文链路中的问题驱动检索，用于验证：

- 翻译后的商品文案和评论是否能正常建索引
- 中文 prompt 驱动下的召回链路是否可运行

### 4_reports

该目录存放针对原始数据集生成的最终分析结果。

当前示例：

- `backpack/backpack_010_analysis.json`：商品 `backpack_010` 的完整分析结果
- `backpack/backpack_010_validation_qdrant_20260408.json`：针对 Qdrant 验证批次生成的结果记录

这些文件通常是“最终可消费结果”，比中间层更接近业务结论。

### CN/4_reports

该目录存放中文审查链路的最终结果，当前包括：

- `backpack/backpack_010_analysis.json`：中文链路完整分析结果
- `backpack/backpack_010_analysis_summary.json`：摘要版分析结果
- `backpack/backpack_010_human_review.md`：给人直接阅读和审查的 Markdown 文件

如果你要做人工审稿、验证模型输出、检查中文建议是否可信，这个目录是最直接的入口。

## 典型产出链路

一个商品从输入到输出，通常会经过下面几层：

1. 原始数据进入系统后，被整理到 `1_normalized/` 或 `CN/1_normalized/`
2. 评论被抽取和建模后，结果落到 `2_aspects/` 或 `CN/2_aspects/`
3. 图文证据被建立索引后，结果落到 `3_indexes/` 或 `CN/3_indexes/`
4. 问题驱动检索、证据聚合、建议生成完成后，最终报告落到 `4_reports/` 或 `CN/4_reports/`
5. 如果需要人工审核，再额外生成 `human_review.md` 这类面向人阅读的文件

## 当前目录里的重点文件

如果你只是想快速理解现在这批输出，建议优先看这几个文件：

- `4_reports/backpack/backpack_010_analysis.json`
- `4_reports/backpack/backpack_010_validation_qdrant_20260408.json`
- `CN/4_reports/backpack/backpack_010_analysis.json`
- `CN/4_reports/backpack/backpack_010_analysis_summary.json`
- `CN/4_reports/backpack/backpack_010_human_review.md`

其中：

- 原始分析看 `4_reports/`
- 中文审查看 `CN/4_reports/`
- 检索层验证痕迹看 `3_indexes/`

## 清理建议

本目录会随着实验推进持续增长，尤其是 `3_indexes/` 下的运行态 Qdrant 目录。

建议按下面原则维护：

- 长期保留最终报告与人工审核文件
- 长期保留主索引目录和带日期标签的验证目录
- 临时 `runtime` 目录在确认不再使用后可以清理
- 清理前先确保对应验证结果已经沉淀到 `4_reports/` 或 `CN/4_reports/`

## 一句话理解

`02_outputs/` 记录的是“系统跑过之后留下来的东西”：中间建模结果、检索索引、最终报告，以及人工审核材料。