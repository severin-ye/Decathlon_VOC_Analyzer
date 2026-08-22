import json

intermediate = r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate"

with open(f"{intermediate}/assembled-graph.json", "r", encoding="utf-8") as f:
    graph = json.load(f)

node_ids = {n["id"] for n in graph["nodes"]}
file_level_types = {"file", "config", "document", "service", "pipeline", "table", "schema", "resource", "endpoint"}
file_nodes = {n["id"] for n in graph["nodes"] if n["type"] in file_level_types}

# Find which file nodes are assigned to layers
assigned = set()
for layer in graph.get("layers", []):
    for nid in layer.get("nodeIds", []):
        assigned.add(nid)

unassigned = file_nodes - assigned
print(f"File-level nodes: {len(file_nodes)}, assigned: {len(assigned)}, unassigned: {len(unassigned)}")

# Add unassigned file nodes to the "configuration-and-data" layer or create new catch-all
# Find the data layer
data_layer = None
for layer in graph["layers"]:
    if layer["id"] == "layer:configuration-and-data":
        data_layer = layer
        break

if data_layer:
    data_layer["nodeIds"] = sorted(list(unassigned))
    print(f"Added {len(unassigned)} nodes to configuration-and-data layer")
else:
    graph["layers"].append({
        "id": "layer:other-artifacts",
        "name": "其他产物",
        "description": "未分类到其他层的文件、数据产物、配置文件等",
        "nodeIds": sorted(list(unassigned))
    })
    print(f"Created other-artifacts layer with {len(unassigned)} nodes")

# Also fix egg-info and prompt markdown files to have proper types
with open(f"{intermediate}/assembled-graph.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, ensure_ascii=False, indent=2)

print(f"Done. Graph updated with {len(graph['layers'])} layers.")
