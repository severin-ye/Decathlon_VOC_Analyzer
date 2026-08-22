import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\6seve\Codelib-severin\1_Research\Decathlon_VOC_Analyzer")
INTERMEDIATE = PROJECT_ROOT / ".understand-anything" / "intermediate"


def read_doc_summary(content, name):
    if not content.strip():
        return f"文档: {name}"
    lines = content.strip().split("\n")
    for line in lines[:10]:
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                return title[:100]
    for line in lines[:5]:
        line = line.strip()
        if line and not line.startswith("!"):
            return line[:100]
    return f"文档: {name}"


def read_config_summary(content, name, ext):
    if ext in (".yaml", ".yml"):
        return f"YAML配置文件: {name}"
    elif ext == ".json":
        return f"JSON配置文件: {name}"
    elif ext == ".toml":
        return f"TOML配置文件: {name}"
    elif ext == ".env":
        return f"环境变量配置: {name}"
    return f"配置文件: {name}"


def read_python_summary(content, name):
    lines = content.split("\n")
    in_docstring = False
    doc_text = []
    for line in lines[:20]:
        line_s = line.strip()
        if line_s.startswith('"""') or line_s.startswith("'''"):
            if in_docstring:
                break
            in_docstring = True
            continue
        if in_docstring and line_s:
            doc_text.append(line_s)
    if doc_text:
        return " ".join(doc_text)[:100]
    
    classes = re.findall(r"class\s+(\w+)", content)
    funcs = re.findall(r"def\s+(\w+)", content)
    
    if classes:
        return f"Python模块: 定义 {len(classes)} 个类, {len(funcs)} 个函数"
    elif funcs:
        return f"Python模块: 定义 {len(funcs)} 个函数"
    return f"Python模块: {name}"


def read_html_summary(content, name):
    title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
    if title_match:
        return f"HTML页面: {title_match.group(1)}"
    return f"HTML页面: {name}"


def extract_python_nodes(content, filepath, seen_ids):
    nodes = []
    edges = []
    
    # Find classes
    class_pattern = re.compile(r"^\s*class\s+(\w+)(?:\(([^)]*)\))?\s*:", re.MULTILINE)
    for match in class_pattern.finditer(content):
        class_name = match.group(1)
        bases_str = match.group(2) or ""
        bases = [b.strip() for b in bases_str.split(",") if b.strip()]
        node_id = f"class:{filepath}:{class_name}"
        
        if node_id in seen_ids:
            continue
        
        # Determine tags for class
        tags = []
        if any("BaseModel" in b for b in bases):
            tags = ["schema", "pydantic-model"]
            node_type = "schema"
        elif any("Enum" in b for b in bases):
            tags = ["enum", "data-model"]
            node_type = "class"
        elif any("Exception" in b or "Error" in b for b in bases):
            tags = ["error", "exception"]
            node_type = "class"
        elif any("BaseSettings" in b or "Settings" in b for b in bases):
            tags = ["configuration", "settings"]
            node_type = "class"
        elif "Service" in class_name:
            tags = ["service"]
            node_type = "class"
        elif "Schema" in class_name or "Model" in class_name:
            tags = ["data-model"]
            node_type = "class"
        elif "Config" in class_name or "Policy" in class_name:
            tags = ["configuration"]
            node_type = "class"
        elif "Gateway" in class_name or "Client" in class_name:
            tags = ["llm", "client"]
            node_type = "class"
        elif "Workflow" in class_name or "Graph" in class_name or "State" in class_name:
            tags = ["workflow", "langgraph"]
            node_type = "class"
        elif "Reporter" in class_name or "Progress" in class_name:
            tags = ["monitoring"]
            node_type = "class"
        elif "Checkpoint" in class_name or "Payload" in class_name or "Signature" in class_name:
            tags = ["data-model", "checkpoint"]
            node_type = "class"
        elif "Record" in class_name or "Bundle" in class_name or "Item" in class_name or "Node" in class_name:
            tags = ["data-model", "record"]
            node_type = "class"
        elif "Request" in class_name or "Response" in class_name:
            tags = ["api", "data-model"]
            node_type = "class"
        elif "Task" in class_name or "Step" in class_name:
            tags = ["pipeline"]
            node_type = "class"
        else:
            tags = ["class"]
            node_type = "class"
        
        summary = f"{class_name}类"
        if bases:
            summary += f"，继承自 {', '.join(bases)}"
        
        # Determine complexity
        class_body = extract_class_body(content, match.start())
        line_count = class_body.count("\n") + 1
        if line_count <= 30:
            complexity = "simple"
        elif line_count <= 100:
            complexity = "moderate"
        else:
            complexity = "complex"
        
        nodes.append({
            "id": node_id,
            "type": node_type,
            "name": class_name,
            "summary": summary,
            "tags": tags,
            "filePath": filepath,
            "complexity": complexity,
            "language": "python"
        })
        
        edges.append({
            "source": f"file:{filepath}",
            "target": node_id,
            "type": "contains",
            "weight": 1.0
        })
        
        # Inherits edges to classes in same file
        for base in bases:
            if base and base != "object" and base != "BaseModel" and base != "Enum" and base != "Exception":
                base_node_id = f"class:{filepath}:{base}"
                if base_node_id in seen_ids:
                    edges.append({
                        "source": node_id,
                        "target": base_node_id,
                        "type": "inherits",
                        "weight": 0.9
                    })
    
    # Find functions
    func_pattern = re.compile(r"^\s*def\s+(\w+)\s*\(", re.MULTILINE)
    for match in func_pattern.finditer(content):
        func_name = match.group(1)
        if func_name.startswith("_"):
            continue
        
        node_id = f"function:{filepath}:{func_name}"
        if node_id in seen_ids:
            continue
        
        # Check for FastAPI decorator
        func_start = match.start()
        context_before = content[max(0, func_start - 400):func_start]
        is_endpoint = bool(re.search(r"@(?:app|router)\.(get|post|put|delete|patch)", context_before))
        is_langgraph_node = bool(re.search(r"@.*(?:node|entry)", context_before, re.IGNORECASE))
        
        if is_endpoint:
            node_type = "endpoint"
            tags = ["api", "endpoint"]
            method_match = re.search(r"@(?:app|router)\.(get|post|put|delete|patch)", context_before)
            method = method_match.group(1).upper() if method_match else "ROUTE"
            summary = f"API端点 {method} {func_name}"
        elif is_langgraph_node:
            tags = ["workflow", "langgraph"]
            node_type = "function"
            summary = f"LangGraph节点: {func_name}"
        elif func_name == "main":
            node_type = "function"
            tags = ["entry-point"]
            summary = f"程序入口: {func_name}"
        elif any(w in func_name.lower() for w in ["parse_arg", "config", "setup", "init"]):
            tags = ["configuration", "cli"]
            node_type = "function"
            summary = f"配置/初始化函数: {func_name}"
        elif any(w in func_name.lower() for w in ["build", "create", "construct", "make"]):
            tags = ["factory"]
            node_type = "function"
            summary = f"构建函数: {func_name}"
        elif any(w in func_name.lower() for w in ["resolve", "load", "get_", "fetch", "read"]):
            tags = ["resolver"]
            node_type = "function"
            summary = f"获取/加载函数: {func_name}"
        elif any(w in func_name.lower() for w in ["validate", "check", "verify", "ensure"]):
            tags = ["validation"]
            node_type = "function"
            summary = f"验证函数: {func_name}"
        elif any(w in func_name.lower() for w in ["extract", "process", "transform", "convert"]):
            tags = ["processing"]
            node_type = "function"
            summary = f"数据处理函数: {func_name}"
        elif any(w in func_name.lower() for w in ["prompt", "render", "display", "show"]):
            tags = ["ui", "display"]
            node_type = "function"
            summary = f"展示/渲染函数: {func_name}"
        elif any(w in func_name.lower() for w in ["run", "execute", "launch", "start", "stop"]):
            tags = ["execution"]
            node_type = "function"
            summary = f"执行函数: {func_name}"
        elif any(w in func_name.lower() for w in ["write", "save", "export", "persist"]):
            tags = ["output", "io"]
            node_type = "function"
            summary = f"输出/保存函数: {func_name}"
        elif any(w in func_name.lower() for w in ["find", "search", "discover", "collect"]):
            tags = ["search"]
            node_type = "function"
            summary = f"搜索/发现函数: {func_name}"
        elif any(w in func_name.lower() for w in ["restore", "resume", "recover"]):
            tags = ["state", "recovery"]
            node_type = "function"
            summary = f"状态恢复函数: {func_name}"
        elif any(w in func_name.lower() for w in ["compute", "calculate", "measure", "score"]):
            tags = ["computation", "metric"]
            node_type = "function"
            summary = f"计算/度量函数: {func_name}"
        else:
            tags = ["function"]
            node_type = "function"
            summary = f"函数: {func_name}"
        
        # Check for function calls within to add call edges
        func_body = extract_function_body(content, match.start())
        
        nodes.append({
            "id": node_id,
            "type": node_type,
            "name": func_name,
            "summary": summary,
            "tags": tags,
            "filePath": filepath,
            "complexity": "moderate",
            "language": "python"
        })
        
        edges.append({
            "source": f"file:{filepath}",
            "target": node_id,
            "type": "contains",
            "weight": 1.0
        })
        
        # Add call edges to other functions in same file
        other_funcs = re.findall(r"\b(\w+)\s*\(", func_body)
        for called in set(other_funcs):
            if called == func_name:
                continue
            called_id = f"function:{filepath}:{called}"
            if called_id in seen_ids:
                edges.append({
                    "source": node_id,
                    "target": called_id,
                    "type": "calls",
                    "weight": 0.8
                })
    
    return nodes, edges


def extract_class_body(content, class_start):
    """Extract the body of a class definition."""
    lines = content[class_start:].split("\n")
    body_lines = []
    indent = None
    for i, line in enumerate(lines):
        if i == 0:
            body_lines.append(line)
            continue
        stripped = line.rstrip()
        if not stripped:
            body_lines.append(stripped)
            continue
        leading = len(line) - len(line.lstrip())
        if indent is None:
            if leading > 0:
                indent = leading
        if indent is not None and leading < indent and stripped:
            break
        body_lines.append(stripped)
    return "\n".join(body_lines)


def extract_function_body(content, func_start):
    """Extract the body of a function definition."""
    lines = content[func_start:].split("\n")
    body_lines = []
    indent = None
    for i, line in enumerate(lines):
        if i == 0:
            body_lines.append(line)
            continue
        stripped = line.rstrip()
        if not stripped:
            body_lines.append(stripped)
            continue
        leading = len(line) - len(line.lstrip())
        if indent is None:
            if leading > 0:
                indent = leading
        if indent is not None and stripped and leading < indent:
            break
        body_lines.append(stripped)
    return "\n".join(body_lines)


def extract_import_edges(content, filepath):
    """Extract import relationships as edges."""
    edges = []
    seen_targets = set()
    
    # from X import Y
    from_imports = re.findall(r"^\s*from\s+([\w.]+)\s+import", content, re.MULTILINE)
    imports = re.findall(r"^\s*import\s+([\w.]+)", content, re.MULTILINE)
    
    proj_pkg = "decathlon_voc_analyzer"
    
    for imp in from_imports + imports:
        if not imp.startswith(proj_pkg):
            continue
        rel = imp.replace(".", "/")
        for ext in [".py", "/__init__.py"]:
            candidate = f"05_src/{rel}{ext}"
            target_id = f"file:{candidate}"
            if target_id not in seen_targets:
                seen_targets.add(target_id)
                edges.append({
                    "source": f"file:{filepath}",
                    "target": target_id,
                    "type": "imports",
                    "weight": 0.7
                })
                break
    
    return edges


# ====== MAIN ======

data = json.load(open(INTERMEDIATE / "batches.json", "r", encoding="utf-8"))
batches = data.get("batches", [])
exports = data.get("exportsByPath", {})

print(f"Total batches: {len(batches)}")

for batch_idx, batch in enumerate(batches):
    nodes = []
    edges = []
    seen_ids = set()
    
    for bf in batch.get("files", []):
        filepath = bf["path"]
        language = bf["language"]
        size_lines = bf["sizeLines"]
        file_category = bf["fileCategory"]
        full_path = PROJECT_ROOT / filepath
        
        ext = Path(filepath).suffix.lower()
        name = Path(filepath).name
        
        # Determine node type
        if file_category == "docs":
            node_type = "document"
        elif file_category == "config":
            node_type = "config"
        elif ext in (".yaml", ".yml", ".json", ".toml", ".env"):
            node_type = "config"
        elif ext == ".md":
            node_type = "document"
        elif "docker" in filepath.lower() or "Dockerfile" in filepath:
            node_type = "service"
        else:
            node_type = "file"
        
        # Complexity
        if size_lines <= 50:
            complexity = "simple"
        elif size_lines <= 300:
            complexity = "moderate"
        else:
            complexity = "complex"
        
        # Tags
        tags = []
        parts = Path(filepath).parts
        
        if "stage1" in filepath.lower() or "dataset" in filepath.lower():
            tags.append("pipeline-stage1")
        if "stage2" in filepath.lower() or "review_modeling" in filepath.lower():
            tags.append("pipeline-stage2")
        if "stage3" in filepath.lower() or "retrieval" in filepath.lower():
            tags.append("pipeline-stage3")
        if "stage4" in filepath.lower() or "generation" in filepath.lower():
            tags.append("pipeline-stage4")
        
        if "app" in parts or "api" in parts:
            tags.append("api-service")
        if "schemas" in parts:
            tags.append("data-model")
        if "evaluation" in parts:
            tags.append("evaluation")
        if "llm" in parts or "gateway" in filepath:
            tags.append("llm")
        if "prompts" in parts:
            tags.append("prompts")
        if "workflow" in filepath.lower():
            tags.append("workflow")
        if "retrieval" in filepath.lower():
            tags.append("retrieval")
        if "docker" in filepath.lower():
            tags.append("infrastructure")
        if "test" in filepath.lower() or filepath.startswith("06_tests/"):
            tags.append("testing")
        if "script" in parts or filepath.startswith("04_scripts/"):
            tags.append("script")
        if "doc" in parts or filepath.startswith("0_docs/"):
            tags.append("documentation")
        if "config" in parts or filepath.startswith("03_configs/"):
            tags.append("configuration")
        if "data" in filepath.lower() or filepath.startswith("01_data/"):
            tags.append("data")
        if "output" in filepath.lower() or filepath.startswith("02_outputs/"):
            tags.append("output")
        if "runtime_progress" in filepath.lower() or "dashboard" in filepath.lower():
            tags.append("dashboard")
        if "launcher" in filepath.lower():
            tags.append("launcher")
        if "ui" in filepath.lower() or "experiment_ui" in filepath.lower():
            tags.append("ui")
        
        if not tags:
            tags = ["untagged"]
        
        # Read file content if exists
        content = ""
        if os.path.exists(full_path):
            try:
                content = open(full_path, "r", encoding="utf-8", errors="replace").read()
            except Exception:
                content = ""
        
        node_id = f"file:{filepath}"
        
        # Summary
        if file_category == "docs":
            summary = read_doc_summary(content, name)
        elif file_category == "config":
            summary = read_config_summary(content, name, ext)
        elif language == "python" and content:
            summary = read_python_summary(content, name)
        elif language == "javascript" and content:
            funcs = re.findall(r"function\s+(\w+)", content)
            consts = re.findall(r"(?:const|let|var)\s+(\w+)\s*=", content)
            total = len(funcs) + len(consts)
            summary = f"JavaScript模块: 定义 {len(funcs)} 个函数, {len(consts)} 个变量" if total > 0 else f"JavaScript模块: {name}"
        elif language == "html" and content:
            summary = read_html_summary(content, name)
        elif language == "css":
            summary = f"CSS样式表: {name}"
        elif language == "shell":
            summary = f"Shell脚本: {name}"
        else:
            summary = f"项目文件: {name}"
        
        node = {
            "id": node_id,
            "type": node_type,
            "name": name,
            "summary": summary,
            "tags": tags,
            "filePath": filepath,
            "complexity": complexity,
            "language": language
        }
        seen_ids.add(node_id)
        nodes.append(node)
        
        # Extract sub-nodes and edges for Python files
        if language == "python" and content:
            py_nodes, py_edges = extract_python_nodes(content, filepath, seen_ids)
            for n in py_nodes:
                seen_ids.add(n["id"])
            nodes.extend(py_nodes)
            edges.extend(py_edges)
        
        # Extract import edges
        if language == "python" and content:
            import_edges = extract_import_edges(content, filepath)
            edges.extend(import_edges)
    
    # Add edges from batchImportData
    batch_imports = batch.get("batchImportData", {})
    for source_path, imports in batch_imports.items():
        if isinstance(imports, list):
            for imp in imports:
                if isinstance(imp, str):
                    edges.append({
                        "source": f"file:{source_path}",
                        "target": f"file:{imp}",
                        "type": "imports",
                        "weight": 0.7
                    })
    
    output = {"nodes": nodes, "edges": edges}
    out_path = INTERMEDIATE / f"batch-{batch_idx}.json"
    json.dump(output, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Batch {batch_idx}: {len(nodes)} nodes, {len(edges)} edges -> {out_path.name}")

print("\nAll batches processed!")
