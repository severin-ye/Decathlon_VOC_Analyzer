import json
import re

intermediate = r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate"

# Load graph
with open(f"{intermediate}/assembled-graph.json", "r", encoding="utf-8") as f:
    graph = json.load(f)

# Build type-based ID prefix mapping: for nodes where type != id prefix, fix the id
prefix_map = {
    "document": "document:",
    "config": "config:",
    "service": "service:",
    "endpoint": "endpoint:",
    "schema": "schema:",
}

id_remap = {}
for node in graph["nodes"]:
    old_id = node["id"]
    node_type = node["type"]
    # Determine correct prefix
    correct_prefix = prefix_map.get(node_type)
    if correct_prefix:
        # Get path from old ID (strip current prefix)
        if ":" in old_id:
            current_prefix, path = old_id.split(":", 1)
        else:
            path = old_id
        new_id = f"{correct_prefix}{path}"
    else:
        new_id = old_id
    
    if new_id != old_id:
        id_remap[old_id] = new_id
        node["id"] = new_id

print(f"Remapped {len(id_remap)} node IDs")

# Update edge references
for edge in graph["edges"]:
    if edge["source"] in id_remap:
        edge["source"] = id_remap[edge["source"]]
    if edge["target"] in id_remap:
        edge["target"] = id_remap[edge["target"]]

# Update layers nodeIds
for layer in graph.get("layers", []):
    new_ids = []
    for nid in layer.get("nodeIds", []):
        if nid in id_remap:
            new_ids.append(id_remap[nid])
        else:
            # Check if any node matches this path
            # e.g., if layer refs "document:X" but node is "file:X"
            new_ids.append(nid)
    layer["nodeIds"] = new_ids

# Update tour nodeIds
for step in graph.get("tour", []):
    new_ids = []
    for nid in step.get("nodeIds", []):
        if nid in id_remap:
            new_ids.append(id_remap[nid])
        else:
            new_ids.append(nid)
    step["nodeIds"] = new_ids

# Also fix layers that reference nodes with wrong prefix
# Check layer refs against actual nodes
node_ids = {n["id"] for n in graph["nodes"]}

# For remaining layer issues, try to find matching nodes by path
for layer in graph.get("layers", []):
    fixed_ids = []
    for nid in layer.get("nodeIds", []):
        if nid in node_ids:
            fixed_ids.append(nid)
            continue
        # Try to find a node with matching path
        if ":" in nid:
            __, path = nid.split(":", 1)
            for prefix in ["file:", "document:", "config:", "service:", "endpoint:", "schema:"]:
                candidate = f"{prefix}{path}"
                if candidate in node_ids:
                    fixed_ids.append(candidate)
                    break
            else:
                # Keep original if no match found
                fixed_ids.append(nid)
        else:
            fixed_ids.append(nid)
    layer["nodeIds"] = fixed_ids

# Same for tour
for step in graph.get("tour", []):
    fixed_ids = []
    for nid in step.get("nodeIds", []):
        if nid in node_ids:
            fixed_ids.append(nid)
            continue
        if ":" in nid:
            __, path = nid.split(":", 1)
            for prefix in ["file:", "document:", "config:", "service:", "endpoint:", "schema:"]:
                candidate = f"{prefix}{path}"
                if candidate in node_ids:
                    fixed_ids.append(candidate)
                    break
            else:
                fixed_ids.append(nid)
        else:
            fixed_ids.append(nid)
    step["nodeIds"] = fixed_ids

# Remove dangling layer/tour refs
for layer in graph.get("layers", []):
    layer["nodeIds"] = [nid for nid in layer["nodeIds"] if nid in node_ids]

for step in graph.get("tour", []):
    step["nodeIds"] = [nid for nid in step["nodeIds"] if nid in node_ids]

# Write back
with open(f"{intermediate}/assembled-graph.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, ensure_ascii=False, indent=2)

# Also fix layers.json and tour.json
for filename in ["layers.json", "tour.json"]:
    with open(f"{intermediate}/{filename}", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = data if isinstance(data, list) else data.get("layers", data.get("steps", data.get("tour", [])))
    fixed_count = 0
    for item in items:
        fixed_ids = []
        for nid in item.get("nodeIds", []):
            if nid in node_ids:
                fixed_ids.append(nid)
            elif ":" in nid:
                __, path = nid.split(":", 1)
                found = False
                for prefix in ["file:", "document:", "config:", "service:", "endpoint:", "schema:"]:
                    candidate = f"{prefix}{path}"
                    if candidate in node_ids:
                        fixed_ids.append(candidate)
                        fixed_count += 1
                        found = True
                        break
                if not found:
                    fixed_ids.append(nid)
            else:
                fixed_ids.append(nid)
        item["nodeIds"] = fixed_ids
    
    with open(f"{intermediate}/{filename}", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Fixed {fixed_count} refs in {filename}")

# Re-count node types
ntypes = {}
for n in graph["nodes"]:
    ntypes[n["type"]] = ntypes.get(n["type"], 0) + 1
print(f"Node types after fix: {ntypes}")
print(f"Total nodes: {len(graph['nodes'])}, edges: {len(graph['edges'])}")
