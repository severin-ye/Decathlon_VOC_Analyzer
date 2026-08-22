import json

with open(r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate\assembled-graph.json", "r", encoding="utf-8") as f:
    graph = json.load(f)

with open(r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate\layers.json", "r", encoding="utf-8") as f:
    layers = json.load(f)

with open(r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate\tour.json", "r", encoding="utf-8") as f:
    tour = json.load(f)

graph["layers"] = layers
graph["tour"] = tour

with open(r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate\assembled-graph.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, ensure_ascii=False, indent=2)

print(f"Updated: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, {len(layers)} layers, {len(tour)} tour steps")
