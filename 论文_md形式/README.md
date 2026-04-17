# 论文_md形式

- 标题：Decathlon VOC Analyzer：面向商品图文证据与用户评论对齐的证据驱动多模态 VOC 分析系统
- 内容定位：基于当前仓库真实代码、设计文档、脚本与输出产物撰写的中文论文初稿
- 结构来源：对齐 [参考论文](/home/severin/Codelib/Decathlon_VOC_Analyzer/参考论文/README.md) 的分章 Markdown 组织方式，但正文内容完全改写为当前项目
- 写作原则：优先陈述已实现事实、已存在产物和已验证主链路；对于尚未完成的大规模实验，明确标注为后续工作而非既成结果

## 文件说明

- title_page.md：标题页与作者信息占位
- 00_abstract.md 到 10_acknowledgments.md：中文分章正文
- appendix.md：补充的系统接口、产物与复现实验说明
- 11_references.md：初版参考文献与工程引用
- 脚本/build_complete_paper.py：合并分章 Markdown 的脚本
- 脚本/export_markdown_to_latex.py：将完整 Markdown 转为 LaTeX
- 脚本/export_complete_paper_pdf.py：将完整 Markdown 直接导出为 PDF
- 脚本/pipeline.py：按参考论文同样的链路执行“分章合并 -> LaTeX -> PDF”

## 当前定位

这是一篇“系统型论文”初稿，重点描述以下内容：

- 为什么电商商品 VOC 分析需要证据驱动与多模态设计
- 当前仓库如何把标准化、Aspect 抽取、问题生成、双路检索、聚合和报告串成闭环
- 当前项目已经有哪些可复现脚本、测试与落盘产物
- 当前结果能说明什么，不能说明什么

## 合并全文

运行：

```bash
.venv/bin/python 论文_md形式/脚本/build_complete_paper.py
```

默认输出：

- `论文_md形式/脚本/outputs/中间文件/01_完整合并/Decathlon_VOC_Analyzer_Complete_Paper.md`

## 导出 PDF

使用与参考论文相同的一键链路：

```bash
.venv/bin/python 论文_md形式/脚本/pipeline.py
```

默认会生成：

- `论文_md形式/脚本/outputs/Decathlon_VOC_Analyzer.pdf`
- `论文_md形式/脚本/outputs/中间文件/02_latex/Decathlon_VOC_Analyzer_Nature_Template.tex`
- `论文_md形式/脚本/outputs/中间文件/03_pdf/Decathlon_VOC_Analyzer_Nature_Template.pdf`

如果只想单独导出 LaTeX，可运行：

```bash
.venv/bin/python 论文_md形式/脚本/export_markdown_to_latex.py --input 论文_md形式/脚本/outputs/中间文件/01_完整合并/Decathlon_VOC_Analyzer_Complete_Paper.md
```

如果只想将完整 Markdown 直接转成 PDF，可运行：

```bash
.venv/bin/python 论文_md形式/脚本/export_complete_paper_pdf.py
```

## 说明

本目录暂不直接复用 [参考论文](/home/severin/Codelib/Decathlon_VOC_Analyzer/参考论文/README.md) 下的正文与图表，也不修改其中历史材料；参考论文仅作为章节组织和写作粒度模板保留。