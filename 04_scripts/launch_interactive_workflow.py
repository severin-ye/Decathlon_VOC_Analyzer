import json
from dataclasses import dataclass
import os
from pathlib import Path
import re
import signal
import shutil
import socket
import subprocess
import sys
from time import sleep, time
from urllib.parse import quote


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ROOT = ROOT_DIR / "01_data" / "01_raw_products" / "products"
HTML_ROOT = ROOT_DIR / "02_outputs" / "6_html"
LAUNCHER_DIR = HTML_ROOT / "_launcher"
HTTP_PORT = 8765
SHARED_QDRANT_PATH = ROOT_DIR / "02_outputs" / "3_indexes" / "qdrant_store"

RUN_MODE_NORMAL = "normal"
RUN_MODE_RESUME_ASPECTS = "resume_aspects"
RUN_MODE_RESUME_ANALYSIS_CHECKPOINT = "resume_analysis_checkpoint"


@dataclass
class BatchProductState:
    index: int
    product_id: str
    status: str = "pending"
    started_at_epoch: float | None = None
    completed_at_epoch: float | None = None
    detail: str = ""
    exit_code: int | None = None


@dataclass
class BatchRunState:
    category: str
    review_limit: int
    dashboard_url: str
    products: list[BatchProductState]
    started_at_epoch: float
    completed_at_epoch: float | None = None
    status: str = "running"
    current_product_id: str | None = None
    current_product_dashboard_url: str | None = None
    note: str = "准备启动工作流"


@dataclass
class OccupyingProcess:
    pid: int
    user: str = "--"
    elapsed: str = "--"
    command: str = "--"


@dataclass
class ResumeCandidate:
    dashboard_path: Path
    payload: dict[str, object]


def discover_categories(dataset_root: Path = DEFAULT_DATASET_ROOT) -> list[str]:
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root not found: {dataset_root}")
    return sorted(entry.name for entry in dataset_root.iterdir() if entry.is_dir())


def discover_products(category: str, dataset_root: Path = DEFAULT_DATASET_ROOT) -> list[str]:
    category_dir = dataset_root / category
    if not category_dir.exists():
        raise FileNotFoundError(f"Category directory not found: {category_dir}")
    return sorted(entry.name for entry in category_dir.iterdir() if entry.is_dir())


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    values: set[int] = set()
    normalized = selection.replace(" ", "")
    if not normalized:
        raise ValueError("selection is empty")
    for token in normalized.split(","):
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError("range start is greater than end")
            for value in range(start, end + 1):
                if value < 1 or value > max_index:
                    raise ValueError("selection index out of range")
                values.add(value)
            continue
        value = int(token)
        if value < 1 or value > max_index:
            raise ValueError("selection index out of range")
        values.add(value)
    if not values:
        raise ValueError("selection is empty")
    return sorted(values)


def build_batch_dashboard_path(category: str) -> Path:
    return LAUNCHER_DIR / f"{category}_interactive_batch.html"


def build_product_dashboard_relative_path(category: str, product_id: str) -> str:
    return f"_progress/{category}/{product_id}_live_progress.html"


def ensure_http_server() -> str:
    if _port_is_open("127.0.0.1", HTTP_PORT):
        return f"http://127.0.0.1:{HTTP_PORT}"
    subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT), "--directory", str(HTML_ROOT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(ROOT_DIR),
    )
    return f"http://127.0.0.1:{HTTP_PORT}"


def write_batch_dashboard(state: BatchRunState, dashboard_path: Path) -> None:
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(render_batch_dashboard_html(state), encoding="utf-8")
    dashboard_path.with_suffix(".state.json").write_text(json.dumps(build_batch_dashboard_payload(state), ensure_ascii=False, indent=2), encoding="utf-8")


def build_batch_dashboard_payload(state: BatchRunState) -> dict[str, object]:
    return {
        "category": state.category,
        "reviewLimit": state.review_limit,
        "status": state.status,
        "note": state.note,
        "startedAt": _format_iso(state.started_at_epoch),
        "completedAt": _format_iso(state.completed_at_epoch),
        "currentProductId": state.current_product_id,
        "currentProductDashboardUrl": state.current_product_dashboard_url,
        "products": [
            {
                "index": product.index,
                "productId": product.product_id,
                "status": product.status,
                "startedAt": _format_iso(product.started_at_epoch),
                "completedAt": _format_iso(product.completed_at_epoch),
                "detail": product.detail,
                "exitCode": product.exit_code,
            }
            for product in state.products
        ],
    }


def render_batch_dashboard_html(state: BatchRunState) -> str:
    payload = build_batch_dashboard_payload(state)
    payload_json = json.dumps(payload, ensure_ascii=False)
    template = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__TITLE__</title>
  <style>
        :root {
      --bg: #f5f5f7;
      --panel: rgba(255,255,255,0.82);
      --panel-strong: rgba(255,255,255,0.94);
      --ink: #1d1d1f;
      --muted: #6e6e73;
      --line: rgba(60,60,67,0.12);
      --blue: #0071e3;
      --green: #248a3d;
      --orange: #b26b00;
      --red: #c9342f;
      --shadow: 0 18px 48px rgba(0,0,0,0.08);
        }
        * { box-sizing: border-box; }
        body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(0,113,227,0.10), transparent 28%),
        radial-gradient(circle at top right, rgba(255,159,10,0.10), transparent 30%),
        linear-gradient(180deg, #fbfbfd 0%, var(--bg) 100%);
      font: 14px/1.5 -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
        }
        .wrap { max-width: 1440px; margin: 0 auto; padding: 28px; }
        .banner { margin-bottom: 14px; padding: 16px 18px; border-radius: 18px; border: 1px solid var(--line); background: var(--panel-strong); box-shadow: var(--shadow); }
        .banner.running { background: linear-gradient(180deg, rgba(0,113,227,0.08), rgba(255,255,255,0.96)); border-color: rgba(0,113,227,0.18); }
        .banner.completed { background: linear-gradient(180deg, rgba(36,138,61,0.12), rgba(255,255,255,0.96)); border-color: rgba(36,138,61,0.22); }
        .banner.failed { background: linear-gradient(180deg, rgba(201,52,47,0.10), rgba(255,255,255,0.96)); border-color: rgba(201,52,47,0.22); }
        .eyebrow { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
        .headline { margin-top: 4px; font-size: 26px; font-weight: 700; letter-spacing: -0.03em; }
        .caption { margin-top: 6px; color: var(--muted); font-size: 13px; }
        .hero { padding: 20px 22px 18px; border-radius: 28px; border: 1px solid var(--line); background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.72)); backdrop-filter: blur(18px) saturate(140%); box-shadow: var(--shadow); }
        h1 { margin: 0 0 10px; font-size: 30px; font-weight: 700; letter-spacing: -0.03em; }
        .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
        .card { min-height: 100px; padding: 14px 16px; border-radius: 20px; border: 1px solid var(--line); background: var(--panel-strong); }
        .label { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
        .value { margin-top: 6px; font-size: 24px; font-weight: 700; letter-spacing: -0.03em; }
        .sub { margin-top: 8px; color: var(--muted); font-size: 13px; }
        .grid { display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 18px; margin-top: 18px; align-items: start; }
        .panel { padding: 20px; border-radius: 24px; border: 1px solid var(--line); background: var(--panel); backdrop-filter: blur(14px) saturate(135%); box-shadow: var(--shadow); }
        .panel h2 { margin: 0 0 14px; font-size: 20px; letter-spacing: -0.02em; }
        .products { display: grid; gap: 12px; }
        .product { border-radius: 18px; border: 1px solid var(--line); background: rgba(255,255,255,0.82); padding: 14px 16px; }
        .row { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; flex-wrap: wrap; }
        .status { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
        .status.pending { color: var(--muted); }
        .status.running { color: var(--blue); }
        .status.completed { color: var(--green); }
        .status.failed { color: var(--red); }
        .detail { margin-top: 8px; color: var(--muted); font-size: 13px; }
        .viewer-note { margin-bottom: 10px; color: var(--muted); font-size: 13px; }
        .viewer-frame { width: 100%; min-height: 820px; border: 0; border-radius: 18px; background: rgba(255,255,255,0.9); }
        .viewer-link { color: var(--blue); text-decoration: none; font-weight: 600; }
        @media (max-width: 1120px) { .grid { grid-template-columns: 1fr; } .viewer-frame { min-height: 640px; } }
  </style>
</head>
<body>
  <div class="wrap">
        <section id="status-banner" class="banner running">
      <div class="eyebrow">Interactive Batch Runner</div>
            <div id="headline" class="headline">--</div>
            <div id="caption" class="caption">--</div>
    </section>
    <section class="hero">
                        <h1><span id="category-name">--</span> 一键工作流</h1>
      <div class="meta">
                                <div class="card"><div class="label">Category</div><div id="category-card" class="value">--</div><div class="sub">本次只处理一个品类</div></div>
                                <div class="card"><div class="label">Products</div><div id="product-count" class="value">--</div><div class="sub">已选商品数量</div></div>
                                <div class="card"><div class="label">Review Limit</div><div id="review-limit" class="value">--</div><div class="sub">每个商品审核评论数</div></div>
                <div class="card"><div class="label">Current Product</div><div id="current-product" class="value">--</div><div id="current-note" class="sub">--</div></div>
      </div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Selected Products</h2>
        <div class="products" id="products"></div>
      </div>
      <div class="panel">
        <h2>Current Product Dashboard</h2>
        <div class="viewer-note">这里会显示当前正在执行的商品进度页。工作流全部完成后，页面会停留在最终完成状态。</div>
        <div id="viewer"></div>
      </div>
    </section>
  </div>
  <script>
                const initialPayload = __PAYLOAD__;
        const stateUrl = new URL(window.location.pathname.replace(/\.html$/, '.state.json'), window.location.origin).toString();
        const productsEl = document.getElementById('products');
        const viewer = document.getElementById('viewer');
        let pollTimer = null;

        const statusHeadline = payload => payload.status === 'completed' ? '已完成所有流程' : (payload.status === 'failed' ? '流程执行失败' : '工作流运行中');
        const statusCaption = payload => payload.status === 'completed'
            ? `本页面会停留在最终完成状态。开始于 ${payload.startedAt ?? '--'}，完成于 ${payload.completedAt ?? '--'}。`
            : (payload.status === 'failed'
                ? `执行在 ${payload.currentProductId ?? '--'} 处失败。可以根据下方状态和终端日志继续排查。`
                : `页面已自动弹出，并会持续更新当前商品的 live 进度页。开始于 ${payload.startedAt ?? '--'}。`);

        function render(payload) {
            const bannerClass = payload.status === 'completed' ? 'completed' : (payload.status === 'failed' ? 'failed' : 'running');
            const banner = document.getElementById('status-banner');
            banner.className = `banner ${bannerClass}`;
            document.getElementById('headline').textContent = statusHeadline(payload);
            document.getElementById('caption').textContent = statusCaption(payload);
            document.getElementById('category-name').textContent = payload.category ?? '--';
            document.getElementById('category-card').textContent = payload.category ?? '--';
            document.getElementById('product-count').textContent = String((payload.products || []).length);
            document.getElementById('review-limit').textContent = String(payload.reviewLimit ?? '--');
            document.getElementById('current-product').textContent = payload.currentProductId ?? '--';
            document.getElementById('current-note').textContent = payload.note ?? '--';

            productsEl.innerHTML = '';
            for (const product of payload.products || []) {
                const productEl = document.createElement('div');
                productEl.className = 'product';
                productEl.innerHTML = `
                    <div class="row"><strong>${product.index}. ${product.productId}</strong><span class="status ${product.status}">${product.status}</span></div>
                    <div class="detail">${product.detail || ''}</div>
                    <div class="detail">Start ${product.startedAt || '--'} · End ${product.completedAt || '--'}${product.exitCode === null ? '' : ` · Exit ${product.exitCode}`}</div>
                `;
                productsEl.appendChild(productEl);
            }

            if (payload.currentProductDashboardUrl) {
                const existingFrame = viewer.querySelector('iframe');
                const currentSrc = existingFrame?.getAttribute('src');
                if (currentSrc !== payload.currentProductDashboardUrl) {
                    viewer.innerHTML = `
                        <div class="viewer-note"><a class="viewer-link" href="${payload.currentProductDashboardUrl}" target="_blank" rel="noreferrer">在新标签中打开当前商品进度页</a></div>
                        <iframe class="viewer-frame" src="${payload.currentProductDashboardUrl}" title="current-product-progress"></iframe>
                    `;
                }
            } else {
                viewer.innerHTML = '<div class="viewer-note">当前还没有商品进度页。</div>';
            }
        }

        async function pollState() {
            try {
                const response = await fetch(`${stateUrl}?t=${Date.now()}`, { cache: 'no-store' });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const payload = await response.json();
                render(payload);
                if (payload.status === 'completed' || payload.status === 'failed') {
                    return;
                }
            } catch (_error) {
            }
            pollTimer = window.setTimeout(pollState, 2000);
        }

        render(initialPayload);
        if (initialPayload.status !== 'completed' && initialPayload.status !== 'failed') {
            pollTimer = window.setTimeout(pollState, 2000);
        }
  </script>
</body>
</html>
    """
    return (
    template.replace("__TITLE__", f"{state.category} Interactive Workflow")
    .replace("__PAYLOAD__", payload_json)
    )


def run_interactive_batch() -> int:
    run_mode = prompt_run_mode()

    if run_mode == RUN_MODE_NORMAL:
        categories = discover_categories()
        category = prompt_category(categories)
        products = discover_products(category)
        selected_products = prompt_products(category, products)
        review_limit = prompt_review_limit()
        state = _build_new_batch_state(category=category, selected_products=selected_products, review_limit=review_limit)
    else:
        resume_candidate = find_latest_resumable_batch()
        if resume_candidate is None:
            print("[未找到] 当前没有可继续的未完成批次。请先使用“正常跑”建立一次任务。")
            return 130
        if not prompt_continue_previous_batch(resume_candidate.payload, run_mode):
            print("[取消] 未继续上一次未完成任务。")
            return 130
        state = restore_batch_state(resume_candidate.payload)
        category = state.category
        review_limit = state.review_limit

    base_url = ensure_http_server()
    dashboard_path = build_batch_dashboard_path(category)
    dashboard_url = f"{base_url}/_launcher/{dashboard_path.name}"
    state.dashboard_url = dashboard_url
    if state.started_at_epoch is None:
        state.started_at_epoch = time()
    if run_mode == RUN_MODE_NORMAL:
        state.note = "等待启动第一个商品"
    else:
        state.status = "running"
        state.completed_at_epoch = None
        state.note = "正在继续上一次未完成任务"
    write_batch_dashboard(state, dashboard_path)
    _open_browser(dashboard_url)

    try:
        for product_state in state.products:
            if product_state.status == "completed":
                continue
            product_state.status = "running"
            product_state.started_at_epoch = time()
            state.current_product_id = product_state.product_id
            state.current_product_dashboard_url = f"{base_url}/{build_product_dashboard_relative_path(category, product_state.product_id)}"
            state.note = f"正在执行 {product_state.product_id}"
            write_batch_dashboard(state, dashboard_path)

            exit_code = run_product_workflow(category=category, product_id=product_state.product_id, max_reviews=review_limit, run_mode=run_mode)

            product_state.exit_code = exit_code
            product_state.completed_at_epoch = time()
            if exit_code == 0:
                product_state.status = "completed"
                product_state.detail = "执行完成"
                state.note = f"{product_state.product_id} 已完成"
            else:
                product_state.status = "failed"
                product_state.detail = "执行失败，请查看终端输出"
                state.status = "failed"
                state.note = f"{product_state.product_id} 执行失败"
                state.completed_at_epoch = time()
                write_batch_dashboard(state, dashboard_path)
                return exit_code
            write_batch_dashboard(state, dashboard_path)

        state.status = "completed"
        state.completed_at_epoch = time()
        state.note = "所有商品都已完成，本页面会停留在最终完成状态。"
        write_batch_dashboard(state, dashboard_path)
        print(f"[完成] 已处理 {len(state.products)} 个商品。总控页面: {dashboard_url}")
        return 0
    except KeyboardInterrupt:
        state.status = "failed"
        state.completed_at_epoch = time()
        state.note = "工作流已手动中断。"
        write_batch_dashboard(state, dashboard_path)
        raise


def _build_new_batch_state(category: str, selected_products: list[str], review_limit: int) -> BatchRunState:
    return BatchRunState(
        category=category,
        review_limit=review_limit,
        dashboard_url="",
        products=[BatchProductState(index=index, product_id=product_id) for index, product_id in enumerate(selected_products, start=1)],
        started_at_epoch=time(),
        note="等待启动第一个商品",
    )


def restore_batch_state(payload: dict[str, object]) -> BatchRunState:
    raw_products = payload.get("products")
    products_payload = raw_products if isinstance(raw_products, list) else []
    raw_review_limit = payload.get("reviewLimit")
    review_limit = raw_review_limit if isinstance(raw_review_limit, int) else 0
    products = [
        BatchProductState(
            index=int(product.get("index") or index),
            product_id=str(product.get("productId") or ""),
            status=str(product.get("status") or "pending"),
            started_at_epoch=_parse_iso_epoch(product.get("startedAt")),
            completed_at_epoch=_parse_iso_epoch(product.get("completedAt")),
            detail=str(product.get("detail") or ""),
            exit_code=product.get("exitCode") if isinstance(product.get("exitCode"), int) else None,
        )
        for index, product in enumerate(products_payload, start=1)
        if isinstance(product, dict) and product.get("productId")
    ]
    return BatchRunState(
        category=str(payload.get("category") or ""),
        review_limit=review_limit,
        dashboard_url="",
        products=products,
        started_at_epoch=_parse_iso_epoch(payload.get("startedAt")) or time(),
        completed_at_epoch=_parse_iso_epoch(payload.get("completedAt")),
        status=str(payload.get("status") or "running"),
        current_product_id=str(payload.get("currentProductId")) if payload.get("currentProductId") else None,
        current_product_dashboard_url=str(payload.get("currentProductDashboardUrl")) if payload.get("currentProductDashboardUrl") else None,
        note=str(payload.get("note") or "正在继续上一次未完成任务"),
    )


def find_latest_resumable_batch(launcher_dir: Path = LAUNCHER_DIR) -> ResumeCandidate | None:
    candidates: list[ResumeCandidate] = []
    if launcher_dir.exists():
        for state_path in sorted(launcher_dir.glob("*.state.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True):
            payload = _read_batch_payload_from_state(state_path)
            if payload is not None and _is_resumable_payload(payload):
                dashboard_path = state_path.with_suffix("").with_suffix(".html")
                candidates.append(ResumeCandidate(dashboard_path=dashboard_path, payload=payload))
        if candidates:
            return candidates[0]
        for html_path in sorted(launcher_dir.glob("*.html"), key=lambda path: path.stat().st_mtime_ns, reverse=True):
            payload = _read_batch_payload_from_html(html_path)
            if payload is not None and _is_resumable_payload(payload):
                candidates.append(ResumeCandidate(dashboard_path=html_path, payload=payload))
    return candidates[0] if candidates else None


def prompt_continue_previous_batch(payload: dict[str, object], run_mode: str, input_func=input, print_func=print) -> bool:
    raw_products = payload.get("products")
    products_payload = raw_products if isinstance(raw_products, list) else []
    unfinished = [
        str(product.get("productId"))
        for product in products_payload
        if isinstance(product, dict) and product.get("productId") and str(product.get("status") or "pending") != "completed"
    ]
    mode_label = "从 aspects 续跑" if run_mode == RUN_MODE_RESUME_ASPECTS else "从 analysis checkpoint 续跑"
    print_func(f"\n已选择运行模式: {mode_label}")
    print_func("检测到最近一次未完成批次：")
    print_func(f"  品类: {payload.get('category') or '--'}")
    print_func(f"  评论数: {payload.get('reviewLimit') or '--'}")
    print_func(f"  未完成商品: {', '.join(unfinished) if unfinished else '--'}")
    while True:
        raw = input_func("是否继续上一次未完成任务？输入 y 继续，输入 n 取消: ").strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print_func("输入无效，请输入 y 或 n。")


def _read_batch_payload_from_state(state_path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_batch_payload_from_html(html_path: Path) -> dict[str, object] | None:
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return None
    patterns = [
        r"const initialPayload = (\{.*?\});",
        r"const payload = (\{.*?\});",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _is_resumable_payload(payload: dict[str, object] | None) -> bool:
    if not payload or str(payload.get("status") or "") == "completed":
        return False
    products_payload = payload.get("products")
    if not isinstance(products_payload, list):
        return False
    return any(isinstance(product, dict) and str(product.get("status") or "pending") != "completed" for product in products_payload)


def _parse_iso_epoch(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def run_product_workflow(category: str, product_id: str, max_reviews: int, run_mode: str = RUN_MODE_NORMAL) -> int:
    if not _ensure_shared_qdrant_access():
        return 130
    command = [
        sys.executable,
        str(ROOT_DIR / "04_scripts" / "run_workflow.py"),
        "--category",
        category,
        "--product-id",
        product_id,
        "--max-reviews",
        str(max_reviews),
        "--qdrant-scope",
        "shared",
        "--export-html",
        "--write-manifest",
    ]
    command.extend(_run_mode_args(run_mode))
    completed = subprocess.run(command, cwd=str(ROOT_DIR), check=False)
    return int(completed.returncode)


def prompt_category(categories: list[str]) -> str:
    print("请选择要处理的品类：")
    for index, category in enumerate(categories, start=1):
        print(f"  {index}. {category}")
    while True:
        raw = input("请输入品类编号，例如 1: ").strip()
        try:
            choice = int(raw)
        except ValueError:
            print("输入无效，请输入数字编号。")
            continue
        if 1 <= choice <= len(categories):
            return categories[choice - 1]
        print("编号超出范围，请重新输入。")


def prompt_products(category: str, products: list[str]) -> list[str]:
    print(f"\n已选择品类: {category}")
    print("该品类下的商品编号如下：")
    for index, product_id in enumerate(products, start=1):
        print(f"  {index:>3}. {product_id}")
    while True:
        raw = input("请输入要处理的商品编号，可用 2-10 或 2,5,8-12: ").strip()
        try:
            selected_indexes = parse_index_selection(raw, len(products))
        except ValueError as exc:
            print(f"输入无效: {exc}")
            continue
        return [products[index - 1] for index in selected_indexes]


def prompt_review_limit() -> int:
    while True:
        raw = input("\n每个商品审核多少条评论？请输入一个整数，例如 25: ").strip()
        try:
            review_limit = int(raw)
        except ValueError:
            print("输入无效，请输入整数。")
            continue
        if review_limit > 0:
            return review_limit
        print("评论数必须大于 0。")


def prompt_run_mode(input_func=input, print_func=print) -> str:
    print_func("\n请选择运行模式：")
    print_func("  1. 正常跑")
    print_func("  2. 从 aspects 续跑")
    print_func("  3. 从 analysis checkpoint 续跑")
    while True:
        raw = input_func("请输入模式编号，例如 1: ").strip()
        if raw == "1":
            return RUN_MODE_NORMAL
        if raw == "2":
            return RUN_MODE_RESUME_ASPECTS
        if raw == "3":
            return RUN_MODE_RESUME_ANALYSIS_CHECKPOINT
        print_func("输入无效，请输入 1、2 或 3。")


def _run_mode_args(run_mode: str) -> list[str]:
    if run_mode == RUN_MODE_RESUME_ASPECTS:
        return ["--skip-normalize", "--skip-index", "--resume-from-aspects"]
    if run_mode == RUN_MODE_RESUME_ANALYSIS_CHECKPOINT:
        return ["--skip-normalize", "--skip-index", "--resume-from-analysis-checkpoint"]
    return []


def _status_css_class(status: str) -> str:
    return "completed" if status == "completed" else ("failed" if status == "failed" else "running")


def _status_headline(status: str) -> str:
    if status == "completed":
        return "已完成所有流程"
    if status == "failed":
        return "流程执行失败"
    return "工作流运行中"


def _status_caption(state: BatchRunState) -> str:
    started_at = _format_iso(state.started_at_epoch)
    if state.status == "completed":
        return f"本页面会停留在最终完成状态。开始于 {started_at or '--'}，完成于 {_format_iso(state.completed_at_epoch) or '--'}。"
    if state.status == "failed":
        return f"执行在 {state.current_product_id or '--'} 处中断或失败。总控页面仍会保留最后状态。"
    return f"页面已自动弹出，并会持续更新当前商品进度页。开始于 {started_at or '--'}。"


def _format_iso(epoch_seconds: float | None) -> str | None:
    if epoch_seconds is None:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(epoch_seconds).isoformat(timespec="seconds")


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _find_shared_qdrant_occupants(qdrant_path: Path = SHARED_QDRANT_PATH) -> list[OccupyingProcess]:
    lock_path = qdrant_path / ".lock"
    target_path = lock_path if lock_path.exists() else qdrant_path
    pid_texts: list[str] = []

    lsof_path = shutil.which("lsof")
    if lsof_path:
        completed = subprocess.run(
            [lsof_path, "-t", str(target_path)],
            cwd=str(ROOT_DIR),
            check=False,
            capture_output=True,
            text=True,
        )
        pid_texts = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    elif shutil.which("fuser"):
        completed = subprocess.run(
            ["fuser", str(target_path)],
            cwd=str(ROOT_DIR),
            check=False,
            capture_output=True,
            text=True,
        )
        pid_texts = [token for token in completed.stdout.split() if token.isdigit()]

    pids = sorted({int(pid_text) for pid_text in pid_texts if pid_text.isdigit() and int(pid_text) != os.getpid()})
    return [_describe_process(pid) for pid in pids if _process_exists(pid)]


def _describe_process(pid: int) -> OccupyingProcess:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid=,user=,etime=,command="],
        cwd=str(ROOT_DIR),
        check=False,
        capture_output=True,
        text=True,
    )
    line = completed.stdout.strip()
    if not line:
        return OccupyingProcess(pid=pid)
    parts = line.split(None, 3)
    return OccupyingProcess(
        pid=int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else pid,
        user=parts[1] if len(parts) >= 2 else "--",
        elapsed=parts[2] if len(parts) >= 3 else "--",
        command=parts[3] if len(parts) >= 4 else "--",
    )


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _ensure_shared_qdrant_access(qdrant_path: Path = SHARED_QDRANT_PATH) -> bool:
    occupants = _find_shared_qdrant_occupants(qdrant_path)
    if not occupants:
        return True
    action = _prompt_for_qdrant_conflict_resolution(qdrant_path, occupants)
    if action == "terminate":
        _terminate_processes(occupants)
        return True
    if action == "continue":
        return True
    print("[取消] 已保留现有进程，当前启动器不再继续。")
    return False


def _prompt_for_qdrant_conflict_resolution(
    qdrant_path: Path,
    occupants: list[OccupyingProcess],
    input_func=input,
    print_func=print,
) -> str:
    print_func(f"[冲突] 共享 Qdrant 目录已被其他进程占用: {qdrant_path}")
    for process in occupants:
        print_func(f"  - PID {process.pid} | USER {process.user} | ELAPSED {process.elapsed}")
        print_func(f"    {process.command}")
    print_func("请选择后续操作：")
    print_func("  1. 关闭上述进程，并由当前启动器接管")
    print_func("  2. 继续当前启动（不关闭旧进程，可能仍会失败）")
    print_func("  3. 取消当前启动")
    while True:
        choice = input_func("请输入编号 1 / 2 / 3: ").strip()
        if choice == "1":
            return "terminate"
        if choice == "2":
            return "continue"
        if choice == "3":
            return "cancel"
        print_func("输入无效，请输入 1、2 或 3。")


def _terminate_processes(processes: list[OccupyingProcess]) -> None:
    for process in processes:
        try:
            os.kill(process.pid, signal.SIGTERM)
        except OSError:
            continue
    deadline = time() + 3.0
    remaining = {process.pid for process in processes}
    while remaining and time() < deadline:
        remaining = {pid for pid in remaining if _process_exists(pid)}
        if remaining:
            sleep(0.1)
    for pid in sorted(remaining):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            continue
    if processes:
        print("[接管] 已尝试结束占用共享 Qdrant 的现有进程，当前启动器继续执行。")


def _build_vscode_simple_browser_uri(url: str) -> str:
    encoded_args = quote(json.dumps([url], ensure_ascii=False), safe="")
    return f"command:simpleBrowser.show?{encoded_args}"


def _open_browser(url: str) -> None:
    code_cli = shutil.which("code")
    if code_cli:
        command_uri = _build_vscode_simple_browser_uri(url)
        try:
            subprocess.run(
                [code_cli, "-r", command_uri],
                cwd=str(ROOT_DIR),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[页面] 已在 VS Code 内部打开总控页面: {url}")
            return
        except Exception:
            pass
    try:
        print(f"[页面] 总控页面已准备好，请在 VS Code 内部打开: {url}")
    except Exception:
        pass


def main() -> None:
    try:
        exit_code = run_interactive_batch()
    except KeyboardInterrupt:
        print("\n[中断] 交互式批量任务已手动取消。", file=sys.stderr)
        raise SystemExit(130)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()