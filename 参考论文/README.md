# 论文_md形式

- 标题：CuraView: 基于GraphRAG增强知识验证的医疗幻觉检测多智能体框架
- 作者：YE SEVERIN；Kyungpook National University；6severin9@gmail.com
- 内容来源：论文 LaTeX 主稿（按章节转换）
- 引用形式：正文当前仍保留统一编号引用写法，但导出阶段会自动根据 citation_key_map.md 映射为 ref.bib 中的 BibTeX key；旧版完整编号参考文献仍保留在 11_references.md
- 图表资源：figures/ 目录中的 PNG 图片来自原始论文 PDF 图表导出

## 文件说明

- title_page.md：标题页（标题/作者/单位/邮箱），从脚本硬编码提取为可编辑分章文件
- 00_abstract.md 到 appendix.md：按原始章节命名规则导出的分章节 Markdown
- 11_references.md：完整参考文献列表
- ref.bib：BibTeX 参考文献库，供 LaTeX / BibTeX 导出使用
- citation_key_map.md：编号引用到 BibTeX key 的映射表，供自动迁移和导出转换使用
- 英文逐章稿/：与中文分章文件同名的英文章节目录，可供英文版完整合并与 PDF 导出复用
- 完整合并稿默认不再平铺写回论文根目录，而是输出到 [脚本/outputs/中间文件/01_完整合并/CuraView_Complete_Paper.md](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/01_%E5%AE%8C%E6%95%B4%E5%90%88%E5%B9%B6/CuraView_Complete_Paper.md)

## 脚本目录

- 所有脚本统一位于 [脚本](脚本)
- 最终 PDF 输出目录：[脚本/outputs](脚本/outputs)
- 中间文件目录：[脚本/outputs/中间文件](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6)
- 中间文件分层目录：
	[脚本/outputs/中间文件/01_完整合并](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/01_%E5%AE%8C%E6%95%B4%E5%90%88%E5%B9%B6)、
	[脚本/outputs/中间文件/02_latex](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/02_latex)、
	[脚本/outputs/中间文件/03_pdf](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/03_pdf)

## 分章合并

- 脚本：[脚本/build_complete_paper.py](脚本/build_complete_paper.py)
- 默认输出：[脚本/outputs/中间文件/01_完整合并/CuraView_Complete_Paper.md](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/01_%E5%AE%8C%E6%95%B4%E5%90%88%E5%B9%B6/CuraView_Complete_Paper.md)
- 默认行为：按固定章节顺序合并分章文件，并保留标题、作者、单位、邮箱头部
- 若由 pipeline 调用：合并稿直接写入阶段目录，不再回写论文根目录
- 运行示例：/home/severin/Codelib/CuraView/.venv/bin/python /home/severin/Codelib/CuraView/论文_md形式/脚本/build_complete_paper.py
- 英文分章示例：/home/severin/Codelib/CuraView/.venv/bin/python /home/severin/Codelib/CuraView/论文_md形式/脚本/build_complete_paper.py --section-dir /home/severin/Codelib/CuraView/论文_md形式/英文逐章稿 --output 脚本/outputs/中间文件_en/01_完整合并/CuraView_Complete_Paper.md
- 可选参数：`--no-title-page` 可生成不带标题页的纯正文合并稿

## 一键 Pipeline

- 脚本：[脚本/pipeline.py](脚本/pipeline.py)
- 执行流程：分章稿 -> 完整合并稿 -> LaTeX -> PDF
- 若存在 ref.bib：pipeline 会自动走 BibTeX 流程，即“数字编号引用 -> BibTeX key -> xelatex -> bibtex -> xelatex -> xelatex”
- 默认语言：中文分章稿
- 英文参数：`--en` 或 `--language en`（大小写不敏感）
- 最终 PDF：中文默认生成到 [脚本/outputs/CuraView.pdf](脚本/outputs/CuraView.pdf)，英文默认生成到 [脚本/outputs/CuraView_EN.pdf](脚本/outputs/CuraView_EN.pdf)
- 中间文件：中文默认生成到 [脚本/outputs/中间文件](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6)，英文默认生成到 [脚本/outputs/中间文件_en](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6_en)
- 完整合并阶段：生成 [脚本/outputs/中间文件/01_完整合并/CuraView_Complete_Paper.md](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/01_%E5%AE%8C%E6%95%B4%E5%90%88%E5%B9%B6/CuraView_Complete_Paper.md)
- LaTeX 阶段：生成 [脚本/outputs/中间文件/02_latex/CuraView_Nature_Template.tex](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/02_latex/CuraView_Nature_Template.tex) 及对应的 `.aux/.log/.out`
- PDF 阶段：生成 [脚本/outputs/中间文件/03_pdf/CuraView_Nature_Template.pdf](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/03_pdf/CuraView_Nature_Template.pdf)
- 运行示例：/home/severin/Codelib/CuraView/.venv/bin/python /home/severin/Codelib/CuraView/论文_md形式/脚本/pipeline.py
- 英文导出示例：/home/severin/Codelib/CuraView/.venv/bin/python /home/severin/Codelib/CuraView/论文_md形式/脚本/pipeline.py --en

## LaTeX 导出

- 脚本：[脚本/export_markdown_to_latex.py](脚本/export_markdown_to_latex.py)
- 默认输入：CuraView_Complete_Paper.md 和 11_references.md
- 默认引用资源：若存在 ref.bib 与 citation_key_map.md，则优先使用 BibTeX 导出；否则回退到 11_references.md + thebibliography 的旧模式
- 默认输出：[脚本/outputs/中间文件/02_latex/CuraView_Nature_Template.tex](脚本/outputs/%E4%B8%AD%E9%97%B4%E6%96%87%E4%BB%B6/02_latex/CuraView_Nature_Template.tex)
- 运行示例：/home/severin/Codelib/CuraView/.venv/bin/python /home/severin/Codelib/CuraView/论文_md形式/脚本/export_markdown_to_latex.py
- 生成的 tex 面向 XeLaTeX，保留原始 Markdown 正文内容，只按 Nature 风格主文件结构重组章节与图例；当启用 BibTeX 模式时，脚本会自动把 ref.bib 复制到 LaTeX 阶段目录

## PDF 导出

- 脚本：[脚本/export_complete_paper_pdf.py](脚本/export_complete_paper_pdf.py)
- 默认输入：[CuraView_Complete_Paper.md](CuraView_Complete_Paper.md)
- 默认输出：[脚本/outputs/CuraView.pdf](脚本/outputs/CuraView.pdf)
- 运行示例：/home/severin/Codelib/CuraView/.venv/bin/python /home/severin/Codelib/CuraView/论文_md形式/脚本/export_complete_paper_pdf.py
