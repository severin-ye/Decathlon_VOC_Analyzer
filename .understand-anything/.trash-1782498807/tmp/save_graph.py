import json

intermediate = r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate"
output = r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything"

with open(f"{intermediate}/assembled-graph.json", "r", encoding="utf-8") as f:
    graph = json.load(f)

kg = {
    "version": "1.0.0",
    "project": {
        "name": "decathlon-voc-analyzer",
        "languages": ["python", "markdown", "yaml", "shell", "html", "css", "javascript"],
        "frameworks": ["langchain", "langgraph", "fastapi", "pydantic", "openai"],
        "description": "证据驱动的多模态电商VOC分析系统，从商品描述、图片和评论中自动生成结构化分析报告，每条结论可追溯到具体证据。",
        "analyzedAt": "2026-06-26T18:32:54.692Z",
        "gitCommitHash": "4ab65522714c43c551797f42012504c0e8cd82a4"
    },
    "nodes": graph["nodes"],
    "edges": graph["edges"],
    "layers": graph["layers"],
    "tour": graph["tour"]
}

with open(f"{output}/knowledge-graph.json", "w", encoding="utf-8") as f:
    json.dump(kg, f, ensure_ascii=False, indent=2)

print(f"Knowledge graph written: {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")
