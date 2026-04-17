# 附录

## A. 关键目录与对应职责

| 目录 | 职责 |
| --- | --- |
| 01_data | 原始商品数据与中文审查数据 |
| 02_outputs | 标准化结果、Aspect 结果、索引、报告、feedback、replay、HTML 与 manifest |
| 03_docs | 设计文档、技术文档与引用材料 |
| 04_scripts | 运行工作流、导出结果、验证多模态运行时 |
| 05_src | 核心源码实现 |
| 06_tests | API、服务与工作流测试 |

## B. 当前 API 入口

系统当前至少包含以下 API 路由：

- /health
- /api/v1/dataset/overview
- /api/v1/dataset/normalize
- /api/v1/index/overview
- /api/v1/index/build
- /api/v1/reviews/extract
- /api/v1/analysis/product

这些接口分别覆盖数据集概览、标准化、索引构建、评论结构化抽取和单商品综合分析。

## C. 复现主链示例

端到端主链可以通过以下命令触发：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010
```

如需验证真实多模态运行态，可使用：

```bash
.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010
```

如需在本目录合并完整论文稿，可使用：

```bash
.venv/bin/python 论文_md形式/脚本/build_complete_paper.py
```

## D. 当前论文稿适用边界

本稿适用于：

- 系统设计说明
- 阶段性论文初稿
- 项目答辩或中期汇报底稿

本稿暂不适用于：

- 需要大规模 benchmark 统计显著性的正式实验论文终稿
- 需要完整图表、全量人工标注与严格引文规范的投稿版本