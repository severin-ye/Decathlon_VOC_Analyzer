import json
data = json.load(open(r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer\.understand-anything\intermediate\batches.json", "r", encoding="utf-8"))
batches = data.get("batches", [])
print(f"Total batches: {len(batches)}")
for i, b in enumerate(batches):
    files = b.get("batchFiles", [])
    print(f"Batch {i}: {len(files)} files")
    for f in files[:3]:
        p = f["path"]
        l = f["language"]
        s = f["sizeLines"]
        c = f["fileCategory"]
        print(f"  {p} ({l}, {s} lines, {c})")
    if len(files) > 3:
        print(f"  ... +{len(files)-3} more")
