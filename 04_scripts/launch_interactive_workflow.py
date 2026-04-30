import json
import argparse
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
LAUNCHER_UI_SOURCE_DIR = ROOT_DIR / "04_scripts" / "launcher_ui"
LAUNCHER_ASSET_DIR = HTML_ROOT / "_launcher_assets"
LAUNCHER_ASSET_PREFIX = "_launcher_assets"
HTTP_PORT = 8765
SHARED_QDRANT_PATH = ROOT_DIR / "02_outputs" / "3_indexes" / "qdrant_store"

RUN_MODE_NORMAL = "normal"
RUN_MODE_RESUME_ASPECTS = "resume_aspects"
RUN_MODE_RESUME_ANALYSIS_CHECKPOINT = "resume_analysis_checkpoint"


@dataclass
class BatchProductState:
    index: int
    product_id: str
    review_limit: int
    status: str = "pending"
    started_at_epoch: float | None = None
    completed_at_epoch: float | None = None
    detail: str = ""
    exit_code: int | None = None


@dataclass
class CategoryRunState:
    category: str
    review_limit: int
    products: list[BatchProductState]
    started_at_epoch: float | None = None
    completed_at_epoch: float | None = None
    status: str = "pending"
    current_product_id: str | None = None
    detail: str = "准备启动该品类"


@dataclass
class LauncherRunState:
    dashboard_url: str
    categories: list[CategoryRunState]
    started_at_epoch: float
    completed_at_epoch: float | None = None
    status: str = "running"
    run_mode: str = RUN_MODE_NORMAL
    current_category: str | None = None
    current_product_id: str | None = None
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


@dataclass(frozen=True)
class ResumeModeOption:
    code: str
    label: str


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


def build_overview_dashboard_path() -> Path:
    return LAUNCHER_DIR / "index.html"


def build_overview_entry_relative_url() -> str:
    return f"/{LAUNCHER_DIR.relative_to(HTML_ROOT).as_posix()}/"


def build_batch_dashboard_path(category: str) -> Path:
    return LAUNCHER_DIR / f"{category}_interactive_batch.html"


def build_product_detail_path(category: str, product_id: str) -> Path:
    return LAUNCHER_DIR / "products" / category / f"{product_id}.html"


def build_launcher_relative_url(path: Path) -> str:
    return f"/{path.relative_to(HTML_ROOT).as_posix()}"


def build_product_dashboard_relative_path(category: str, product_id: str) -> str:
    return f"/_progress/{category}/{product_id}_live_progress.html"


def build_product_dashboard_state_relative_path(category: str, product_id: str) -> str:
    return f"/_progress/{category}/{product_id}_live_progress.state.json"


def ensure_http_server() -> str:
    if _port_is_open("127.0.0.1", HTTP_PORT):
        return f"http://localhost:{HTTP_PORT}"
    subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT), "--directory", str(HTML_ROOT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(ROOT_DIR),
    )
    return f"http://localhost:{HTTP_PORT}"

def ensure_launcher_assets() -> None:
    LAUNCHER_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for asset_path in LAUNCHER_UI_SOURCE_DIR.iterdir():
        if asset_path.is_file():
            shutil.copy2(asset_path, LAUNCHER_ASSET_DIR / asset_path.name)


def _render_launcher_template(template_name: str, replacements: dict[str, str]) -> str:
    template = (LAUNCHER_UI_SOURCE_DIR / template_name).read_text(encoding="utf-8")
    rendered = template.replace("__ASSET_PREFIX__", LAUNCHER_ASSET_PREFIX)
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def write_batch_dashboard(state: LauncherRunState) -> None:
    ensure_launcher_assets()
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    session_payload = build_batch_dashboard_payload(state)
    session_state_path = LAUNCHER_DIR / "session.state.json"
    session_state_path.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    overview_path = build_overview_dashboard_path()
    overview_path.write_text(
        _render_launcher_template(
            "overview.html",
            {
                "__TITLE__": "Interactive Workflow Overview",
                "__SESSION_STATE_URL__": build_launcher_relative_url(session_state_path),
            },
        ),
        encoding="utf-8",
    )

    for category_state in state.categories:
        category_path = build_batch_dashboard_path(category_state.category)
        category_path.write_text(
            _render_launcher_template(
                "category.html",
                {
                    "__TITLE__": f"{category_state.category} Interactive Workflow",
                    "__SESSION_STATE_URL__": build_launcher_relative_url(session_state_path),
                    "__CATEGORY__": category_state.category,
                },
            ),
            encoding="utf-8",
        )


def build_batch_dashboard_payload(state: LauncherRunState) -> dict[str, object]:
    return {
        "status": state.status,
        "runMode": state.run_mode,
        "runModeLabel": _run_mode_label(state.run_mode),
        "note": state.note,
        "startedAt": _format_iso(state.started_at_epoch),
        "completedAt": _format_iso(state.completed_at_epoch),
        "currentCategory": state.current_category,
        "currentProductId": state.current_product_id,
        "categories": [
            {
                "category": category_state.category,
                "status": category_state.status,
                "reviewLimit": category_state.review_limit,
                "startedAt": _format_iso(category_state.started_at_epoch),
                "completedAt": _format_iso(category_state.completed_at_epoch),
                "currentProductId": category_state.current_product_id,
                "detail": category_state.detail,
                "categoryPageUrl": build_launcher_relative_url(build_batch_dashboard_path(category_state.category)),
                "products": [
                    {
                        "index": product.index,
                        "productId": product.product_id,
                        "status": product.status,
                        "reviewLimit": product.review_limit,
                        "startedAt": _format_iso(product.started_at_epoch),
                        "completedAt": _format_iso(product.completed_at_epoch),
                        "detail": product.detail,
                        "exitCode": product.exit_code,
                        "liveProgressUrl": build_product_dashboard_relative_path(category_state.category, product.product_id),
                        "liveProgressStateUrl": build_product_dashboard_state_relative_path(category_state.category, product.product_id),
                        "productPageUrl": build_product_dashboard_relative_path(category_state.category, product.product_id),
                    }
                    for product in category_state.products
                ],
            }
            for category_state in state.categories
        ],
    }


def run_interactive_batch(run_mode_override: str | None = None, continue_previous: bool = False) -> int:
    resume_candidate = find_latest_resumable_batch()
    run_mode = run_mode_override or prompt_run_mode(resume_candidate)

    if run_mode == RUN_MODE_NORMAL:
        categories = discover_categories()
        selected_categories = prompt_categories(categories)
        review_limit = prompt_review_limit()
        selected_items: list[tuple[str, list[str]]] = []
        for category in selected_categories:
            products = discover_products(category)
            selected_products = prompt_products(category, products)
            selected_items.append((category, selected_products))
        state = _build_new_batch_state(selected_items=selected_items, review_limit=review_limit)
    else:
        if resume_candidate is None:
            print("[未找到] 当前没有可继续的未完成批次。请先使用“正常跑”建立一次任务。")
            return 130
        if continue_previous:
            print("[自动] 继续上一次未完成任务。")
        elif not prompt_continue_previous_batch(resume_candidate.payload, run_mode):
            print("[取消] 未继续上一次未完成任务。")
            return 130
        state = restore_batch_state(resume_candidate.payload)

    base_url = ensure_http_server()
    dashboard_url = f"{base_url}{build_overview_entry_relative_url()}"
    state.dashboard_url = dashboard_url
    state.run_mode = run_mode
    if run_mode == RUN_MODE_NORMAL:
        state.note = "等待启动第一个商品"
    else:
        state.status = "running"
        state.completed_at_epoch = None
        state.note = "正在继续上一次未完成任务"
    write_batch_dashboard(state)
    _open_browser(dashboard_url)

    try:
        for category_state in state.categories:
            unfinished_products = [product for product in category_state.products if product.status != "completed"]
            if not unfinished_products:
                category_state.status = "completed"
                category_state.detail = "该品类已完成"
                category_state.completed_at_epoch = category_state.completed_at_epoch or time()
                continue

            category_state.status = "running"
            category_state.started_at_epoch = category_state.started_at_epoch or time()
            for product_state in category_state.products:
                if product_state.status == "completed":
                    continue
                product_state.status = "running"
                product_state.started_at_epoch = product_state.started_at_epoch or time()
                category_state.current_product_id = product_state.product_id
                category_state.detail = f"正在执行 {product_state.product_id}"
                state.current_category = category_state.category
                state.current_product_id = product_state.product_id
                state.note = f"正在执行 {category_state.category} / {product_state.product_id}"
                write_batch_dashboard(state)

                exit_code = run_product_workflow(
                    category=category_state.category,
                    product_id=product_state.product_id,
                    max_reviews=product_state.review_limit,
                    run_mode=run_mode,
                )

                product_state.exit_code = exit_code
                product_state.completed_at_epoch = time()
                if exit_code == 0:
                    product_state.status = "completed"
                    product_state.detail = "执行完成"
                    state.note = f"{category_state.category} / {product_state.product_id} 已完成"
                    category_state.detail = state.note
                    if all(product.status == "completed" for product in category_state.products):
                        category_state.status = "completed"
                        category_state.completed_at_epoch = time()
                        category_state.detail = f"{category_state.category} 品类已完成"
                        category_state.current_product_id = None
                else:
                    product_state.status = "failed"
                    product_state.detail = "执行失败，请查看终端输出"
                    category_state.status = "failed"
                    category_state.detail = f"{product_state.product_id} 执行失败"
                    state.status = "failed"
                    state.note = f"{category_state.category} / {product_state.product_id} 执行失败"
                    state.completed_at_epoch = time()
                    write_batch_dashboard(state)
                    return exit_code
                write_batch_dashboard(state)

        state.status = "completed"
        state.completed_at_epoch = time()
        state.current_category = None
        state.current_product_id = None
        state.note = "所有商品都已完成，本页面会停留在最终完成状态。"
        write_batch_dashboard(state)
        print(f"[完成] 已处理 {_selected_product_total(state)} 个商品。总控页面: {dashboard_url}")
        return 0
    except KeyboardInterrupt:
        state.status = "failed"
        state.completed_at_epoch = time()
        state.note = "工作流已手动中断。"
        write_batch_dashboard(state)
        raise


def _build_new_batch_state(selected_items: list[tuple[str, list[str]]], review_limit: int) -> LauncherRunState:
    return LauncherRunState(
        dashboard_url="",
        categories=[
            CategoryRunState(
                category=category,
                review_limit=review_limit,
                products=[
                    BatchProductState(index=index, product_id=product_id, review_limit=review_limit)
                    for index, product_id in enumerate(selected_products, start=1)
                ],
            )
            for category, selected_products in selected_items
        ],
        started_at_epoch=time(),
        note="等待启动第一个商品",
    )


def restore_batch_state(payload: dict[str, object]) -> LauncherRunState:
    categories_payload_raw = payload.get("categories")
    categories_payload: list[object] | None = categories_payload_raw if isinstance(categories_payload_raw, list) else None
    if categories_payload is None:
        categories_payload = [
            {
                "category": payload.get("category"),
                "reviewLimit": payload.get("reviewLimit"),
                "status": payload.get("status"),
                "startedAt": payload.get("startedAt"),
                "completedAt": payload.get("completedAt"),
                "currentProductId": payload.get("currentProductId"),
                "detail": payload.get("note"),
                "products": payload.get("products") or [],
            }
        ]

    categories: list[CategoryRunState] = []
    for raw_category in categories_payload:
        if not isinstance(raw_category, dict) or not raw_category.get("category"):
            continue
        review_limit = int(raw_category.get("reviewLimit") or 0)
        products_payload_raw = raw_category.get("products")
        products_payload: list[object] = products_payload_raw if isinstance(products_payload_raw, list) else []
        products = [
            BatchProductState(
                index=int(product.get("index") or index),
                product_id=str(product.get("productId") or ""),
                review_limit=int(product.get("reviewLimit") or review_limit),
                status=str(product.get("status") or "pending"),
                started_at_epoch=_parse_iso_epoch(product.get("startedAt")),
                completed_at_epoch=_parse_iso_epoch(product.get("completedAt")),
                detail=str(product.get("detail") or ""),
                exit_code=product.get("exitCode") if isinstance(product.get("exitCode"), int) else None,
            )
            for index, product in enumerate(products_payload, start=1)
            if isinstance(product, dict) and product.get("productId")
        ]
        categories.append(
            CategoryRunState(
                category=str(raw_category.get("category") or ""),
                review_limit=review_limit,
                products=products,
                started_at_epoch=_parse_iso_epoch(raw_category.get("startedAt")),
                completed_at_epoch=_parse_iso_epoch(raw_category.get("completedAt")),
                status=str(raw_category.get("status") or "running"),
                current_product_id=str(raw_category.get("currentProductId")) if raw_category.get("currentProductId") else None,
                detail=str(raw_category.get("detail") or "正在继续上一次未完成任务"),
            )
        )

    return LauncherRunState(
        dashboard_url="",
        categories=categories,
        started_at_epoch=_parse_iso_epoch(payload.get("startedAt")) or time(),
        completed_at_epoch=_parse_iso_epoch(payload.get("completedAt")),
        status=str(payload.get("status") or "running"),
        run_mode=str(payload.get("runMode") or RUN_MODE_NORMAL),
        current_category=str(payload.get("currentCategory")) if payload.get("currentCategory") else None,
        current_product_id=str(payload.get("currentProductId")) if payload.get("currentProductId") else None,
        note=str(payload.get("note") or "正在继续上一次未完成任务"),
    )


def find_latest_resumable_batch(launcher_dir: Path = LAUNCHER_DIR) -> ResumeCandidate | None:
    candidates: list[ResumeCandidate] = []
    if launcher_dir.exists():
        session_state_path = launcher_dir / "session.state.json"
        payload = _read_batch_payload_from_state(session_state_path)
        if payload is not None and _is_resumable_payload(payload):
            return ResumeCandidate(dashboard_path=build_overview_dashboard_path(), payload=payload)
        for state_path in sorted(launcher_dir.glob("*.state.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True):
            if state_path.name == "session.state.json":
                continue
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
    unfinished = [f"{category} / {product_id}" for category, product_id in _unfinished_product_refs(payload)]
    mode_label = "从 aspects 续跑" if run_mode == RUN_MODE_RESUME_ASPECTS else "从 analysis checkpoint 续跑"
    print_func(f"\n已选择运行模式: {mode_label}")
    print_func("检测到最近一次未完成批次：")
    print_func(f"  品类: {', '.join(_payload_categories(payload)) or '--'}")
    print_func(f"  评论数: {_payload_review_limit(payload) or '--'}")
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
    return bool(_unfinished_product_refs(payload))


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


def prompt_categories(categories: list[str], input_func=input, print_func=print) -> list[str]:
    print_func("请选择要处理的品类：")
    for index, category in enumerate(categories, start=1):
        print_func(f"  {index}. {category}")
    while True:
        raw = input_func("请输入品类编号，可用 1-2 或 1,3: ").strip()
        try:
            selected_indexes = parse_index_selection(raw, len(categories))
        except ValueError as exc:
            print_func(f"输入无效: {exc}")
            continue
        return [categories[index - 1] for index in selected_indexes]


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


def _selected_product_total(state: LauncherRunState) -> int:
    return sum(len(category.products) for category in state.categories)


def prompt_run_mode(resume_candidate: ResumeCandidate | None = None, input_func=input, print_func=print) -> str:
    options = available_run_mode_options(resume_candidate)
    default_option = _default_run_mode_option(options)
    print_func("\n请选择运行模式：")
    for index, option in enumerate(options, start=1):
        print_func(f"  {index}. {option.label}")
    if resume_candidate is not None:
        unavailable = unavailable_resume_mode_messages(resume_candidate.payload)
        for message in unavailable:
            print_func(f"  - {message}")
    while True:
        default_label = default_option.label if default_option is not None else "正常跑"
        raw = input_func(f"请输入模式编号，例如 1（直接回车默认 {default_label}）: ").strip()
        if raw == "":
            return default_option.code if default_option is not None else RUN_MODE_NORMAL
        try:
            choice = int(raw)
        except ValueError:
            print_func(f"输入无效，请输入 1 到 {len(options)}。")
            continue
        if 1 <= choice <= len(options):
            return options[choice - 1].code
        print_func(f"输入无效，请输入 1 到 {len(options)}。")


def parse_run_mode_override(value: str | None, resume_candidate: ResumeCandidate | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "1": RUN_MODE_NORMAL,
        "normal": RUN_MODE_NORMAL,
        "2": RUN_MODE_RESUME_ASPECTS,
        "resume-aspects": RUN_MODE_RESUME_ASPECTS,
        "aspects": RUN_MODE_RESUME_ASPECTS,
        "3": RUN_MODE_RESUME_ANALYSIS_CHECKPOINT,
        "resume-analysis-checkpoint": RUN_MODE_RESUME_ANALYSIS_CHECKPOINT,
        "analysis-checkpoint": RUN_MODE_RESUME_ANALYSIS_CHECKPOINT,
    }
    run_mode = aliases.get(normalized)
    if run_mode is None:
        raise ValueError("--mode 只支持 1/2/3、normal、resume-aspects、resume-analysis-checkpoint")
    available = {option.code for option in available_run_mode_options(resume_candidate)}
    if run_mode not in available:
        labels = ", ".join(option.label for option in available_run_mode_options(resume_candidate)) or "无"
        raise ValueError(f"当前不可用的运行模式: {value}。可用模式: {labels}")
    return run_mode


def available_run_mode_options(resume_candidate: ResumeCandidate | None) -> list[ResumeModeOption]:
    options: list[ResumeModeOption] = []
    options.append(ResumeModeOption(code=RUN_MODE_NORMAL, label="正常跑"))
    if resume_candidate is not None:
        payload = resume_candidate.payload
        if _resume_mode_has_aspects(payload):
            options.append(ResumeModeOption(code=RUN_MODE_RESUME_ASPECTS, label="从 aspects 续跑"))
        if _resume_mode_has_analysis_checkpoint(payload):
            options.append(ResumeModeOption(code=RUN_MODE_RESUME_ANALYSIS_CHECKPOINT, label="从 analysis checkpoint 续跑"))
    return options


def _default_run_mode_option(options: list[ResumeModeOption]) -> ResumeModeOption | None:
    for option in options:
        if option.code != RUN_MODE_NORMAL:
            return option
    return options[0] if options else None


def unavailable_resume_mode_messages(payload: dict[str, object]) -> list[str]:
    messages: list[str] = []
    if not _resume_mode_has_aspects(payload):
        messages.append("“从 aspects 续跑”不可用：缺少评论抽取产物。")
    if not _resume_mode_has_analysis_checkpoint(payload):
        messages.append("“从 analysis checkpoint 续跑”不可用：缺少 analysis checkpoint。")
    return messages


def _run_mode_args(run_mode: str) -> list[str]:
    if run_mode == RUN_MODE_RESUME_ASPECTS:
        return ["--skip-normalize", "--skip-index", "--resume-from-aspects"]
    if run_mode == RUN_MODE_RESUME_ANALYSIS_CHECKPOINT:
        return ["--skip-normalize", "--skip-index", "--resume-from-analysis-checkpoint"]
    return []


def _run_mode_label(run_mode: str) -> str:
    if run_mode == RUN_MODE_RESUME_ASPECTS:
        return "从 aspects 续跑"
    if run_mode == RUN_MODE_RESUME_ANALYSIS_CHECKPOINT:
        return "从 analysis checkpoint 续跑"
    return "正常跑"


def _payload_category_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    categories_payload_raw = payload.get("categories")
    if isinstance(categories_payload_raw, list):
        return [item for item in categories_payload_raw if isinstance(item, dict) and item.get("category")]
    category = payload.get("category")
    if not isinstance(category, str) or not category:
        return []
    return [
        {
            "category": category,
            "reviewLimit": payload.get("reviewLimit"),
            "products": payload.get("products") or [],
        }
    ]


def _unfinished_product_refs(payload: dict[str, object]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for category_payload in _payload_category_entries(payload):
        category = str(category_payload.get("category") or "")
        products_payload_raw = category_payload.get("products")
        products_payload: list[object] = products_payload_raw if isinstance(products_payload_raw, list) else []
        for product in products_payload:
            if not isinstance(product, dict) or not product.get("productId"):
                continue
            if str(product.get("status") or "pending") == "completed":
                continue
            refs.append((category, str(product.get("productId"))))
    return refs


def _payload_categories(payload: dict[str, object]) -> list[str]:
    return [str(item.get("category")) for item in _payload_category_entries(payload) if item.get("category")]


def _payload_review_limit(payload: dict[str, object]) -> int | None:
    entries = _payload_category_entries(payload)
    if not entries:
        return None
    raw_value = entries[0].get("reviewLimit")
    return int(raw_value) if isinstance(raw_value, int) else None


def _resume_mode_has_aspects(payload: dict[str, object]) -> bool:
    unfinished = _unfinished_product_refs(payload)
    if not unfinished:
        return False
    return all((ROOT_DIR / "02_outputs" / "2_aspects" / category / f"{product_id}.json").exists() for category, product_id in unfinished)


def _resume_mode_has_analysis_checkpoint(payload: dict[str, object]) -> bool:
    unfinished = _unfinished_product_refs(payload)
    if not unfinished:
        return False
    return all((ROOT_DIR / "02_outputs" / "4_reports" / category / f"{product_id}_analysis_checkpoint.json").exists() for category, product_id in unfinished)


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
    try:
        print(f"[页面] 总控页面已准备好，请手动打开: {url}")
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch interactive VOC workflow.")
    parser.add_argument(
        "--mode",
        help="非交互选择运行模式：1/normal，2/resume-aspects，3/resume-analysis-checkpoint。",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="非交互续跑时自动回答 y，继续上一次未完成任务。",
    )
    args = parser.parse_args()
    try:
        resume_candidate = find_latest_resumable_batch()
        run_mode_override = parse_run_mode_override(args.mode, resume_candidate)
        exit_code = run_interactive_batch(run_mode_override=run_mode_override, continue_previous=args.yes)
    except ValueError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("\n[中断] 交互式批量任务已手动取消。", file=sys.stderr)
        raise SystemExit(130)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
