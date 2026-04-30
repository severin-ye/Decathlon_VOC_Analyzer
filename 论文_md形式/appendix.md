# 附录

## A. 关键目录与职责

| 目录 | 职责 |
| --- | --- |
| `01_data/` | 原始商品数据与中文审核数据 |
| `02_outputs/` | 标准化结果、方面结果、索引、报告、feedback、replay、HTML 与 manifest |
| `03_configs/` | 评论抽样 profile 与运行策略配置 |
| `04_scripts/` | 工作流、评估、导出、验证和清理脚本 |
| `05_src/` | 核心源码实现 |
| `06_tests/` | API、服务、脚本和工作流测试 |
| `0_docs/03_论文子模块文档/` | 基于当前源码整理的论文模块文档 |
| `论文_md形式/` | 论文分章稿、参考文献和导出脚本 |

## B. API 入口

系统当前包含以下主要 API：

- `/health`
- `/api/v1/dataset/overview`
- `/api/v1/dataset/normalize`
- `/api/v1/index/overview`
- `/api/v1/index/build`
- `/api/v1/reviews/extract`
- `/api/v1/analysis/product`

这些接口覆盖数据集概览、商品标准化、索引构建、评论结构化抽取和单商品综合分析。

## C. 复现命令

端到端运行：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --output-format json --export-html --write-manifest
```

离线运行：

```bash
.venv/bin/python 04_scripts/run_workflow.py --category backpack --product-id backpack_010 --no-llm --output-format json
```

验证多模态运行态：

```bash
.venv/bin/python 04_scripts/validate_multimodal_runtime.py --category backpack --product-id backpack_010
```

评估 manifest：

```bash
.venv/bin/python 04_scripts/evaluate_manifests.py 02_outputs/7_manifests
```

运行测试：

```bash
.venv/bin/python -m pytest
```

合并论文：

```bash
.venv/bin/python 论文_md形式/脚本/build_complete_paper.py
```

导出 PDF：

```bash
.venv/bin/python 论文_md形式/脚本/pipeline.py
```

## D. 主要结构化产物

| 产物 | 默认位置 | 用途 |
| --- | --- | --- |
| 标准化商品证据包 | `02_outputs/1_normalized/` | 后续索引和分析输入 |
| 评论方面结果 | `02_outputs/2_aspects/` | 问题规划和聚合输入 |
| 索引与检索缓存 | `02_outputs/3_indexes/` | 召回和重排复用 |
| 分析报告 | `02_outputs/4_reports/` | 最终结构化 VOC 结果 |
| feedback sidecar | `02_outputs/5_feedback/` | 人工反馈入口 |
| replay sidecar | `02_outputs/5_replay/` | 后续分析回放 |
| HTML 报告 | `02_outputs/6_html/` | 人工审查界面 |
| run manifest | `02_outputs/7_manifests/` | 评估与复现实验入口 |

## E. 当前论文稿适用边界

本稿适用于系统设计说明、方法章节草稿、项目答辩和后续实验规划。不适用于直接作为完整 benchmark 论文终稿，因为仍缺少多品类冻结标注集、正式消融实验和大规模人工评测。
