from __future__ import annotations

import html
import json
import os
from pathlib import Path
import select
import sys
import termios
import threading
import tty
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time import monotonic, time
from typing import Iterator, Literal

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


TerminalMode = Literal["events", "live"]


@dataclass
class ProgressStepState:
    key: str
    label: str
    status: str = "pending"
    completed: float = 0.0
    total: float | None = None
    detail: str = ""
    started_at: float | None = None
    started_at_epoch: float | None = None
    completed_at_epoch: float | None = None


@dataclass
class ProgressModuleState:
    key: str
    label: str
    status: str = "pending"
    steps: list[ProgressStepState] = field(default_factory=list)
    detail: str = ""
    started_at: float | None = None
    started_at_epoch: float | None = None
    completed_at_epoch: float | None = None


class NoopWorkflowProgressReporter:
    def activate_module(self, *args, **kwargs) -> None:
        return None

    def complete_module(self, *args, **kwargs) -> None:
        return None

    def skip_module(self, *args, **kwargs) -> None:
        return None

    def activate_step(self, *args, **kwargs) -> None:
        return None

    def start_count_step(self, *args, **kwargs) -> None:
        return None

    def advance_step(self, *args, **kwargs) -> None:
        return None

    def complete_step(self, *args, **kwargs) -> None:
        return None

    def note(self, *args, **kwargs) -> None:
        return None

    def refresh(self) -> None:
        return None


class WorkflowProgressReporter:
    def __init__(
        self,
        modules: list[tuple[str, str, list[tuple[str, str]]]],
        enabled: bool = True,
        dashboard_path: Path | None = None,
        dashboard_title: str | None = None,
        terminal_mode: TerminalMode = "events",
        restore_state: bool = False,
    ) -> None:
        self.enabled = enabled
        self.dashboard_path = dashboard_path
        self.dashboard_title = dashboard_title or "Workflow Progress"
        self.terminal_mode = terminal_mode
        self.restore_state = restore_state
        self._use_alt_screen = terminal_mode == "live"
        self._vertical_overflow = "visible"
        self.started_at = monotonic()
        self.started_at_epoch = time()
        self.modules: list[ProgressModuleState] = [
            ProgressModuleState(
                key=module_key,
                label=module_label,
                steps=[ProgressStepState(key=step_key, label=step_label) for step_key, step_label in step_plan],
            )
            for module_key, module_label, step_plan in modules
        ]
        self._module_lookup = {module.key: module for module in self.modules}
        self._step_lookup = {f"{module.key}:{step.key}": step for module in self.modules for step in module.steps}
        self._active_module_key: str | None = None
        self._active_step_key: str | None = None
        self._note = ""
        self._live: Live | None = None
        self._console = Console(stderr=True, force_terminal=True, color_system="standard", width=120)
        self._log_console = Console(stderr=True, force_terminal=False, color_system=None)
        self._stdin_fd: int | None = None
        self._stdin_termios: list[int] | None = None
        self._input_drain_stop = threading.Event()
        self._input_drain_thread: threading.Thread | None = None
        if self.restore_state:
            self._restore_progress_state()

    def __enter__(self) -> "WorkflowProgressReporter":
        if self.enabled and self.terminal_mode == "live":
            self._prepare_terminal()
            self._configure_terminal_input()
            self._live = Live(
                self.render(),
                console=self._console,
                screen=self._use_alt_screen,
                auto_refresh=True,
                refresh_per_second=4,
                transient=False,
                vertical_overflow=self._vertical_overflow,
            )
            self._live.start()
        self._write_dashboard_snapshot()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._live is not None:
            self.refresh()
            self._live.stop()
            self._live = None
        self._write_dashboard_snapshot()
        self._restore_terminal_input()

    def activate_module(self, module_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        module.status = "in_progress"
        if module.started_at is None:
            module.started_at = monotonic()
        if module.started_at_epoch is None:
            module.started_at_epoch = time()
        module.completed_at_epoch = None
        if detail:
            module.detail = detail
        self._active_module_key = module_key
        self._active_step_key = None
        self._emit_event("module_start", module=module)
        self.refresh()

    def complete_module(self, module_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        self._ensure_module_started(module)
        module.status = "done"
        if module.completed_at_epoch is None:
            module.completed_at_epoch = time()
        if detail:
            module.detail = detail
        self._emit_event("module_done", module=module)
        self._active_module_key = None
        self._active_step_key = None
        self.refresh()

    def skip_module(self, module_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        self._ensure_module_started(module)
        module.status = "skipped"
        if module.completed_at_epoch is None:
            module.completed_at_epoch = time()
        if detail:
            module.detail = detail
        self._emit_event("module_skipped", module=module)
        self.refresh()

    def activate_step(self, module_key: str, step_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        step = self._step_lookup[f"{module_key}:{step_key}"]
        module.status = "in_progress"
        self._ensure_module_started(module)
        step.status = "in_progress"
        if step.started_at is None:
            step.started_at = monotonic()
        if step.started_at_epoch is None:
            step.started_at_epoch = time()
        step.completed_at_epoch = None
        if detail:
            step.detail = detail
        self._active_module_key = module_key
        self._active_step_key = step_key
        self._emit_event("step_start", module=module, step=step)
        self.refresh()

    def advance_step(self, module_key: str, step_key: str, amount: float = 1.0, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        step = self._step_lookup[f"{module_key}:{step_key}"]
        step.completed += amount
        if detail:
            step.detail = detail
        self._emit_event("step_progress", module=module, step=step)
        self.refresh()

    def complete_step(self, module_key: str, step_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        step = self._step_lookup[f"{module_key}:{step_key}"]
        self._ensure_module_started(module)
        self._ensure_step_started(step)
        if step.total is not None:
            step.completed = step.total
        else:
            step.completed = max(step.completed, 1.0)
        step.status = "done"
        if step.completed_at_epoch is None:
            step.completed_at_epoch = time()
        if detail:
            step.detail = detail
        self._emit_event("step_done", module=module, step=step)
        self._active_step_key = None
        self.refresh()

    def note(self, text: str) -> None:
        self._note = text
        self._emit_event("note", detail=text)
        self.refresh()

    def start_count_step(self, module_key: str, step_key: str, total: int, detail: str | None = None) -> None:
        step = self._step_lookup[f"{module_key}:{step_key}"]
        step.total = float(max(total, 0))
        step.completed = 0.0
        self.activate_step(module_key, step_key, detail=detail)

    def render(self):
        header = self._render_header()
        modules = self._render_modules_table()
        bars = self._render_bars()
        return Panel(Group(header, modules, bars), title="Workflow Progress", border_style="cyan")

    def refresh(self) -> None:
        self._write_dashboard_snapshot()
        if self._live is not None:
            self._live.update(self.render(), refresh=True)

    def _emit_event(
        self,
        event_type: str,
        module: ProgressModuleState | None = None,
        step: ProgressStepState | None = None,
        detail: str | None = None,
    ) -> None:
        if not self.enabled or self.terminal_mode != "events":
            return
        parts = [f"[{datetime.now().strftime('%H:%M:%S')}]", event_type]
        if module is not None:
            parts.append(f"module={module.label}")
            module_eta = self._estimate_remaining_seconds(self._module_fraction(module), self._module_elapsed(module))
            if module_eta is not None:
                parts.append(f"stage_eta={self._format_duration(module_eta)}")
                parts.append(f"stage_finish={self._format_eta_clock(module_eta)}")
        if step is not None:
            parts.append(f"step={step.label}")
            count = self._count_text(step)
            if count is not None:
                parts.append(f"count={count}")
            step_eta = self._estimate_remaining_seconds(self._step_fraction(step), self._step_elapsed(step))
            if step_eta is not None:
                parts.append(f"step_eta={self._format_duration(step_eta)}")
                parts.append(f"step_finish={self._format_eta_clock(step_eta)}")
            if step.detail:
                parts.append(f"detail={step.detail}")
        if detail:
            parts.append(f"detail={detail}")
        overall_eta = self._estimate_remaining_seconds(self._overall_fraction(), monotonic() - self.started_at)
        if overall_eta is not None:
            parts.append(f"overall_eta={self._format_duration(overall_eta)}")
            parts.append(f"overall_finish={self._format_eta_clock(overall_eta)}")
        self._log_console.print(" ".join(parts), highlight=False)

    def _write_dashboard_snapshot(self) -> None:
        if self.dashboard_path is None:
            return
        self.dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_progress_state()
        self.dashboard_path.write_text(self._render_dashboard_html(), encoding="utf-8")

    def _progress_state_path(self) -> Path | None:
        if self.dashboard_path is None:
            return None
        return self.dashboard_path.with_suffix(".state.json")

    def _write_progress_state(self) -> None:
        state_path = self._progress_state_path()
        if state_path is None:
            return
        payload = {
            "workflow": {
                "started_at_epoch": self.started_at_epoch,
                "started_at": self._iso_from_epoch(self.started_at_epoch),
                "note": self._note,
                "active_module_key": self._active_module_key,
                "active_step_key": self._active_step_key,
                "updated_at": self._iso_from_epoch(time()),
            },
            "modules": [
                {
                    "key": module.key,
                    "status": module.status,
                    "detail": module.detail,
                    "started_at_epoch": module.started_at_epoch,
                    "started_at": self._iso_from_epoch(module.started_at_epoch),
                    "completed_at_epoch": module.completed_at_epoch,
                    "completed_at": self._iso_from_epoch(module.completed_at_epoch),
                    "steps": [
                        {
                            "key": step.key,
                            "status": step.status,
                            "completed": step.completed,
                            "total": step.total,
                            "detail": step.detail,
                            "started_at_epoch": step.started_at_epoch,
                            "started_at": self._iso_from_epoch(step.started_at_epoch),
                            "completed_at_epoch": step.completed_at_epoch,
                            "completed_at": self._iso_from_epoch(step.completed_at_epoch),
                        }
                        for step in module.steps
                    ],
                }
                for module in self.modules
            ],
        }
        state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _restore_progress_state(self) -> None:
        state_path = self._progress_state_path()
        if state_path is None or not state_path.exists():
            return
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        workflow = payload.get("workflow") or {}
        started_at_epoch = self._as_float(workflow.get("started_at_epoch"))
        if started_at_epoch is not None:
            self.started_at_epoch = started_at_epoch
            self.started_at = self._monotonic_from_epoch(started_at_epoch)
        note = workflow.get("note")
        if isinstance(note, str):
            self._note = note
        active_module_key = workflow.get("active_module_key")
        if isinstance(active_module_key, str) and active_module_key in self._module_lookup:
            self._active_module_key = active_module_key
        active_step_key = workflow.get("active_step_key")
        if isinstance(active_step_key, str):
            self._active_step_key = active_step_key

        module_payloads = payload.get("modules")
        if not isinstance(module_payloads, list):
            return
        for module_payload in module_payloads:
            if not isinstance(module_payload, dict):
                continue
            module_key = module_payload.get("key")
            if not isinstance(module_key, str) or module_key not in self._module_lookup:
                continue
            module = self._module_lookup[module_key]
            status = module_payload.get("status")
            if isinstance(status, str):
                module.status = status
            detail = module_payload.get("detail")
            if isinstance(detail, str):
                module.detail = detail
            module.started_at_epoch = self._as_float(module_payload.get("started_at_epoch"))
            module.completed_at_epoch = self._as_float(module_payload.get("completed_at_epoch"))
            if module.started_at_epoch is not None:
                module.started_at = self._monotonic_from_epoch(module.started_at_epoch)

            step_payloads = module_payload.get("steps")
            if not isinstance(step_payloads, list):
                continue
            for step_payload in step_payloads:
                if not isinstance(step_payload, dict):
                    continue
                step_key = step_payload.get("key")
                step_lookup_key = f"{module_key}:{step_key}"
                if not isinstance(step_key, str) or step_lookup_key not in self._step_lookup:
                    continue
                step = self._step_lookup[step_lookup_key]
                status = step_payload.get("status")
                if isinstance(status, str):
                    step.status = status
                detail = step_payload.get("detail")
                if isinstance(detail, str):
                    step.detail = detail
                completed = self._as_float(step_payload.get("completed"))
                if completed is not None:
                    step.completed = completed
                total = self._as_float(step_payload.get("total"))
                step.total = total
                step.started_at_epoch = self._as_float(step_payload.get("started_at_epoch"))
                step.completed_at_epoch = self._as_float(step_payload.get("completed_at_epoch"))
                if step.started_at_epoch is not None:
                    step.started_at = self._monotonic_from_epoch(step.started_at_epoch)

    def _render_dashboard_html(self) -> str:
        payload_json = json.dumps(self._dashboard_payload(), ensure_ascii=False)
        title = html.escape(self.dashboard_title)
        template = r"""<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="refresh" content="2" />
    <title>__TITLE__</title>
    <style>
        :root {
            --bg: #f5f5f7;
            --panel: rgba(255,255,255,0.78);
            --panel-strong: rgba(255,255,255,0.92);
            --ink: #1d1d1f;
            --muted: #6e6e73;
            --line: rgba(60,60,67,0.12);
            --blue: #0071e3;
            --green: #248a3d;
            --orange: #b26b00;
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
        .wrap { max-width: 1380px; margin: 0 auto; padding: 28px; }
        .status-banner {
            margin-bottom: 14px;
            padding: 14px 18px;
            border-radius: 18px;
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.78);
            backdrop-filter: blur(16px) saturate(135%);
            box-shadow: var(--shadow);
        }
        .status-banner.complete {
            border-color: rgba(36,138,61,0.24);
            background: linear-gradient(180deg, rgba(36,138,61,0.10), rgba(255,255,255,0.92));
        }
        .status-banner.running {
            border-color: rgba(0,113,227,0.18);
            background: linear-gradient(180deg, rgba(0,113,227,0.08), rgba(255,255,255,0.92));
        }
        .status-banner .eyebrow {
            color: var(--muted);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .status-banner .headline {
            margin-top: 4px;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.03em;
        }
        .status-banner .caption {
            margin-top: 6px;
            color: var(--muted);
            font-size: 13px;
        }
        .hero {
            position: sticky;
            top: 0;
            z-index: 3;
            padding: 20px 22px 18px;
            border-radius: 28px;
            border: 1px solid var(--line);
            background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.72));
            backdrop-filter: blur(18px) saturate(140%);
            box-shadow: var(--shadow);
        }
        h1 { margin: 0 0 10px; font-size: 30px; font-weight: 700; letter-spacing: -0.03em; }
        .note { color: var(--muted); margin-bottom: 14px; }
        .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
        .card {
            min-height: 104px;
            padding: 14px 16px;
            border-radius: 20px;
            border: 1px solid var(--line);
            background: var(--panel-strong);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
        }
        .label { color: var(--muted); font-size: 12px; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase; }
        .value { margin-top: 6px; font-size: 24px; font-weight: 700; letter-spacing: -0.03em; }
        .sub { margin-top: 8px; color: var(--muted); font-size: 13px; }
        .grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr); gap: 18px; margin-top: 18px; align-items: start; }
        .panel {
            padding: 20px;
            border-radius: 24px;
            border: 1px solid var(--line);
            background: var(--panel);
            backdrop-filter: blur(14px) saturate(135%);
            box-shadow: var(--shadow);
        }
        .panel h2 { margin: 0 0 14px; font-size: 20px; letter-spacing: -0.02em; }
        .list { display: grid; gap: 14px; }
        .module { border-radius: 18px; border: 1px solid var(--line); background: rgba(255,255,255,0.75); padding: 16px; }
        .row { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; flex-wrap: wrap; }
        .debug-panel summary {
            cursor: pointer;
            list-style: none;
            font-size: 16px;
            font-weight: 600;
            color: var(--ink);
        }
        .debug-panel summary::-webkit-details-marker { display: none; }
        .debug-panel .debug-note { margin: 8px 0 12px; color: var(--muted); font-size: 13px; }
        .status { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
        .status.done { color: var(--green); }
        .status.running { color: var(--blue); }
        .status.pending { color: var(--muted); }
        .status.skipped { color: var(--orange); }
        .bar { width: 100%; height: 10px; background: rgba(60,60,67,0.08); border-radius: 999px; overflow: hidden; margin: 12px 0 8px; }
        .fill { height: 100%; background: linear-gradient(90deg, #0a84ff 0%, #5ac8fa 100%); }
        .detail { color: var(--muted); font-size: 13px; }
        .steps { display: grid; gap: 10px; margin-top: 12px; }
        .step { padding: 12px 14px; border-radius: 16px; background: rgba(250,250,252,0.95); border: 1px solid rgba(60,60,67,0.08); }
        .step.active { background: linear-gradient(180deg, rgba(0,113,227,0.08), rgba(255,255,255,0.98)); border-color: rgba(0,113,227,0.18); }
        pre { margin: 0; white-space: pre-wrap; word-break: break-word; font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; color: #2c2c2e; }
        @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } .hero { position: static; } }
    </style>
</head>
<body>
    <div class="wrap">
        <section class="status-banner {{workflowStatusClass}}">
            <div class="eyebrow">Workflow Status</div>
            <div class="headline">{{workflowHeadline}}</div>
            <div class="caption">{{workflowCaption}}</div>
        </section>
        <section class="hero">
            <h1>__TITLE__</h1>
            <div class="note">{{note}}</div>
            <div class="meta">
                <div class="card"><div class="label">Overall</div><div class="value">{{overallPercent}}</div><div class="sub">ETA {{overallEta}} · Finish {{overallFinish}}</div></div>
                <div class="card"><div class="label">Active Stage</div><div class="value">{{activeModule}}</div><div class="sub">ETA {{moduleEta}} · Finish {{moduleFinish}}</div></div>
                <div class="card"><div class="label">Active Step</div><div class="value">{{activeStep}}</div><div class="sub">ETA {{stepEta}} · Finish {{stepFinish}}</div></div>
                <div class="card"><div class="label">Elapsed</div><div class="value">{{elapsed}}</div><div class="sub">Auto refresh every 2s</div></div>
            </div>
        </section>
        <section class="grid">
            <div class="panel">
                <h2>Workflow</h2>
                <div class="list" id="modules"></div>
            </div>
            <div class="panel debug-panel">
                <details>
                    <summary>技术快照</summary>
                    <div class="debug-note">这是给调试和排障看的原始状态，不是主要的人类阅读界面。</div>
                    <pre id="raw"></pre>
                </details>
            </div>
        </section>
    </div>
    <script>
        const payload = __PAYLOAD__;
        const fill = (template, values) => template.replace(/\{\{(.*?)\}\}/g, (_, key) => values[key.trim()] ?? '--');
        const fmtPercent = value => `${(value * 100).toFixed(1)}%`;
        const statusClass = status => status === 'in_progress' ? 'running' : status;
        const rootValues = {
            overallPercent: fmtPercent(payload.overallFraction),
            overallEta: payload.overallEta ?? '--',
            overallFinish: payload.overallFinish ?? '--',
            activeModule: payload.activeModule ?? '--',
            moduleEta: payload.activeModuleEta ?? '--',
            moduleFinish: payload.activeModuleFinish ?? '--',
            activeStep: payload.activeStep ?? '--',
            stepEta: payload.activeStepEta ?? '--',
            stepFinish: payload.activeStepFinish ?? '--',
            elapsed: payload.elapsed,
            note: payload.note || 'Workflow is running',
            workflowStatusClass: payload.workflowStatus === 'completed' ? 'complete' : 'running',
            workflowHeadline: payload.workflowHeadline,
            workflowCaption: payload.workflowCaption,
        };
        document.body.innerHTML = fill(document.body.innerHTML, rootValues);

        const modulesEl = document.getElementById('modules');
        for (const module of payload.modules) {
            const moduleEl = document.createElement('div');
            moduleEl.className = 'module';
            const stepsHtml = module.steps.map(step => `
                <div class="step ${step.isActive ? 'active' : ''}">
                    <div class="row"><strong>${step.label}</strong><span class="status ${statusClass(step.status)}">${step.statusLabel}</span></div>
                    <div class="bar"><div class="fill" style="width:${fmtPercent(step.fraction)}"></div></div>
                    <div class="detail">${step.detail || ''}</div>
                    <div class="detail">${step.meta || ''}</div>
                </div>
            `).join('');
            moduleEl.innerHTML = `
                <div class="row"><strong>${module.label}</strong><span class="status ${statusClass(module.status)}">${module.statusLabel}</span></div>
                <div class="bar"><div class="fill" style="width:${fmtPercent(module.fraction)}"></div></div>
                <div class="detail">${module.detail || ''}</div>
                <div class="detail">${module.meta || ''}</div>
                <div class="steps">${stepsHtml}</div>
            `;
            modulesEl.appendChild(moduleEl);
        }
        document.getElementById('raw').textContent = JSON.stringify(payload, null, 2);
    </script>
</body>
</html>
        """
        return template.replace("__TITLE__", title).replace("__PAYLOAD__", payload_json)

    def _dashboard_payload(self) -> dict[str, object]:
        elapsed = monotonic() - self.started_at
        overall_eta_seconds = self._estimate_remaining_seconds(self._overall_fraction(), elapsed)
        active_module = self._module_lookup.get(self._active_module_key) if self._active_module_key else None
        active_step = self._step_lookup.get(f"{active_module.key}:{self._active_step_key}") if active_module is not None and self._active_step_key is not None else None
        active_module_eta = self._module_eta_seconds(active_module)
        active_step_eta = self._step_eta_seconds(active_step)
        workflow_status = self._workflow_status()
        workflow_completed_at = self._workflow_completed_at_epoch()
        return {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "workflowStartedAt": self._iso_from_epoch(self.started_at_epoch),
            "workflowCompletedAt": self._iso_from_epoch(workflow_completed_at),
            "workflowStatus": workflow_status,
            "workflowHeadline": self._workflow_headline(workflow_status),
            "workflowCaption": self._workflow_caption(workflow_status, workflow_completed_at),
            "elapsed": f"{elapsed:.1f}s",
            "overallFraction": self._overall_fraction(),
            "overallEta": self._format_duration(overall_eta_seconds) if overall_eta_seconds is not None else None,
            "overallFinish": self._format_eta_clock(overall_eta_seconds) if overall_eta_seconds is not None else None,
            "activeModule": active_module.label if active_module is not None else None,
            "activeModuleEta": self._format_duration(active_module_eta) if active_module_eta is not None else None,
            "activeModuleFinish": self._format_eta_clock(active_module_eta) if active_module_eta is not None else None,
            "activeStep": active_step.label if active_step is not None else None,
            "activeStepEta": self._format_duration(active_step_eta) if active_step_eta is not None else None,
            "activeStepFinish": self._format_eta_clock(active_step_eta) if active_step_eta is not None else None,
            "note": self._note,
            "modules": [
                {
                    "key": module.key,
                    "label": module.label,
                    "status": module.status,
                    "statusLabel": self._module_status_label(module),
                    "fraction": self._module_fraction(module),
                    "detail": module.detail,
                    "startedAt": self._iso_from_epoch(module.started_at_epoch),
                    "completedAt": self._iso_from_epoch(module.completed_at_epoch),
                    "meta": self._module_meta_text(module),
                    "isActive": module.key == self._active_module_key,
                    "steps": [
                        {
                            "key": step.key,
                            "label": step.label,
                            "status": step.status,
                            "statusLabel": self._step_status_label(step),
                            "fraction": self._step_fraction(step),
                            "detail": step.detail,
                            "startedAt": self._iso_from_epoch(step.started_at_epoch),
                            "completedAt": self._iso_from_epoch(step.completed_at_epoch),
                            "meta": self._step_meta_text(step),
                            "isActive": module.key == self._active_module_key and step.key == self._active_step_key,
                        }
                        for step in module.steps
                    ],
                }
                for module in self.modules
            ],
        }

    def _prepare_terminal(self) -> None:
        if not self._use_alt_screen:
            return
        terminal = self._console.file
        terminal.write("\x1b[3J\x1b[2J\x1b[H")
        terminal.flush()

    def _configure_terminal_input(self) -> None:
        if not sys.stdin.isatty() or self.terminal_mode != "live":
            return
        try:
            fd = sys.stdin.fileno()
            settings = termios.tcgetattr(fd)
        except (OSError, termios.error, ValueError):
            return

        self._stdin_fd = fd
        self._stdin_termios = settings
        updated = termios.tcgetattr(fd)
        updated[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, updated)
        tty.setcbreak(fd)

        self._input_drain_stop.clear()
        self._input_drain_thread = threading.Thread(target=self._drain_terminal_input, name="workflow-progress-input", daemon=True)
        self._input_drain_thread.start()

    def _restore_terminal_input(self) -> None:
        self._input_drain_stop.set()
        if self._input_drain_thread is not None:
            self._input_drain_thread.join(timeout=0.5)
            self._input_drain_thread = None
        if self._stdin_fd is None or self._stdin_termios is None:
            return
        try:
            termios.tcsetattr(self._stdin_fd, termios.TCSADRAIN, self._stdin_termios)
        except (OSError, termios.error):
            pass
        finally:
            self._stdin_fd = None
            self._stdin_termios = None

    def _drain_terminal_input(self) -> None:
        if self._stdin_fd is None:
            return
        while not self._input_drain_stop.is_set():
            try:
                ready, _, _ = select.select([self._stdin_fd], [], [], 0.1)
            except (OSError, ValueError):
                return
            if not ready:
                continue
            try:
                os.read(self._stdin_fd, 1024)
            except OSError:
                return

    def _render_header(self):
        elapsed = monotonic() - self.started_at
        overall_fraction = self._overall_fraction()
        overall_eta = self._estimate_remaining_seconds(overall_fraction, elapsed)
        active_module = self._module_lookup.get(self._active_module_key) if self._active_module_key else None
        active_step = self._step_lookup.get(f"{active_module.key}:{self._active_step_key}") if active_module is not None and self._active_step_key is not None else None

        header = Text()
        header.append(f"Elapsed {elapsed:6.1f}s", style="bold cyan")
        if overall_eta is not None:
            header.append("  ")
            header.append(f"ETA {self._format_duration(overall_eta)}", style="bold green")
            header.append("  ")
            header.append(f"Finish ~{self._format_eta_clock(overall_eta)}", style="green")
        if active_module is not None:
            header.append("  ")
            header.append(f"Module: {active_module.label}", style="bold yellow")
            module_eta = self._module_eta_seconds(active_module)
            if module_eta is not None:
                header.append("  ")
                header.append(f"Stage ETA {self._format_duration(module_eta)}", style="yellow")
                header.append("  ")
                header.append(f"Stage Finish ~{self._format_eta_clock(module_eta)}", style="yellow")
        if active_step is not None:
            header.append("  ")
            header.append(f"Step: {active_step.label}", style="yellow")
            header.append("  ")
            header.append(f"Step Elapsed: {self._step_elapsed(active_step):5.1f}s", style="bold magenta")
            step_eta = self._step_eta_seconds(active_step)
            if step_eta is not None:
                header.append("  ")
                header.append(f"Step ETA {self._format_duration(step_eta)}", style="magenta")
                header.append("  ")
                header.append(f"Step Finish ~{self._format_eta_clock(step_eta)}", style="magenta")
        if self._note:
            header.append("\n")
            header.append(self._note, style="white")
        return header

    def _render_modules_table(self):
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(ratio=2)
        table.add_column(ratio=1)
        table.add_column(ratio=3)

        for module in self.modules:
            style = self._module_style(module)
            table.add_row(self._module_label(module), Text(self._module_status_label(module), style=style), self._module_progress_text(module))
            for step in module.steps:
                table.add_row(self._step_label(module, step), Text(self._step_status_label(step), style=self._step_style(module, step)), self._step_progress_text(module, step))
        return table

    def _render_bars(self):
        bars = Table.grid(expand=True, padding=(0, 1))
        bars.add_column(ratio=1)
        bars.add_column(ratio=1)
        bars.add_row(
            self._bar_text("Overall", self._overall_fraction(), "cyan", meta=self._overall_meta_text()),
            self._current_step_bar(),
        )
        return bars

    def _module_label(self, module: ProgressModuleState) -> Text:
        label = Text("▶ " if module.key == self._active_module_key else "• ")
        label.append(module.label, style=self._module_style(module))
        if module.detail:
            label.append(f"\n    {module.detail}", style="dim")
        return label

    def _step_label(self, module: ProgressModuleState, step: ProgressStepState) -> Text:
        label = Text("    ↳ ")
        label.append(step.label, style=self._step_style(module, step))
        if step.detail:
            label.append(f"\n        {step.detail}", style="dim")
        return label

    def _module_style(self, module: ProgressModuleState) -> str:
        if module.status == "done":
            return "green"
        if module.status == "skipped":
            return "dim"
        if module.key == self._active_module_key:
            return "bold yellow"
        return "white"

    def _step_style(self, module: ProgressModuleState, step: ProgressStepState) -> str:
        if step.status == "done":
            return "green"
        if step.status == "skipped":
            return "dim"
        if module.key == self._active_module_key and step.key == self._active_step_key:
            return "bold yellow"
        return "white"

    def _module_status_label(self, module: ProgressModuleState) -> str:
        return {"done": "done", "in_progress": "running", "skipped": "skipped"}.get(module.status, "pending")

    def _step_status_label(self, step: ProgressStepState) -> str:
        return {"done": "done", "in_progress": "running", "skipped": "skipped"}.get(step.status, "pending")

    def _module_progress_text(self, module: ProgressModuleState) -> Text:
        return self._bar_text(module.label, self._module_fraction(module), self._module_style(module), meta=self._module_meta_text(module))

    def _step_progress_text(self, module: ProgressModuleState, step: ProgressStepState) -> Text:
        fraction = self._step_fraction(step)
        label = step.label if step.total is not None else (step.detail or step.label)
        count_text = self._count_text(step)
        return self._bar_text(label, fraction, self._step_style(module, step), meta=count_text)

    def _current_step_bar(self) -> Text:
        if self._active_module_key is None or self._active_step_key is None:
            return Text("Current step: idle", style="dim")
        step = self._step_lookup.get(f"{self._active_module_key}:{self._active_step_key}")
        if step is None:
            return Text("Current step: idle", style="dim")
        return self._bar_text(f"Current {step.label}", self._step_fraction(step), "yellow", meta=self._step_meta_text(step))

    def _count_text(self, step: ProgressStepState) -> str | None:
        if step.total is None:
            return None
        return f"{int(min(step.completed, step.total))}/{int(step.total)}"

    def _step_elapsed(self, step: ProgressStepState) -> float:
        if step.started_at is None:
            return 0.0
        return max(0.0, monotonic() - step.started_at)

    def _module_elapsed(self, module: ProgressModuleState) -> float:
        if module.started_at is None:
            return 0.0
        return max(0.0, monotonic() - module.started_at)

    def _step_eta_seconds(self, step: ProgressStepState | None) -> float | None:
        if step is None:
            return None
        return self._estimate_remaining_seconds(self._step_fraction(step), self._step_elapsed(step))

    def _module_eta_seconds(self, module: ProgressModuleState | None) -> float | None:
        if module is None:
            return None
        return self._estimate_remaining_seconds(self._module_fraction(module), self._module_elapsed(module))

    def _step_meta_text(self, step: ProgressStepState) -> str | None:
        parts: list[str] = []
        started_at = self._format_timestamp_clock(step.started_at_epoch)
        if started_at is not None:
            parts.append(f"Start {started_at}")
        count_text = self._count_text(step)
        if count_text is not None:
            parts.append(count_text)
        if step.status == "in_progress" and step.started_at is not None:
            elapsed = self._step_elapsed(step)
            parts.append(f"{elapsed:.1f}s")
            eta = self._step_eta_seconds(step)
            if eta is not None:
                parts.append(f"ETA {self._format_duration(eta)}")
                parts.append(f"~{self._format_eta_clock(eta)}")
        return " | ".join(parts) if parts else None

    def _module_meta_text(self, module: ProgressModuleState) -> str | None:
        parts: list[str] = []
        started_at = self._format_timestamp_clock(module.started_at_epoch)
        if started_at is not None:
            parts.append(f"Start {started_at}")
        if module.status != "in_progress" or module.started_at is None:
            completed_at = self._format_timestamp_clock(module.completed_at_epoch)
            if completed_at is not None:
                parts.append(f"End {completed_at}")
            return " | ".join(parts) if parts else None
        elapsed = self._module_elapsed(module)
        parts.append(f"{elapsed:.1f}s")
        eta = self._module_eta_seconds(module)
        if eta is not None:
            parts.append(f"ETA {self._format_duration(eta)}")
            parts.append(f"~{self._format_eta_clock(eta)}")
        return " | ".join(parts)

    def _overall_meta_text(self) -> str | None:
        elapsed = monotonic() - self.started_at
        eta = self._estimate_remaining_seconds(self._overall_fraction(), elapsed)
        parts: list[str] = []
        started_at = self._format_timestamp_clock(self.started_at_epoch)
        if started_at is not None:
            parts.append(f"Start {started_at}")
        if eta is not None:
            parts.append(f"ETA {self._format_duration(eta)}")
            parts.append(f"~{self._format_eta_clock(eta)}")
        return " | ".join(parts) if parts else None

    def _overall_fraction(self) -> float:
        if not self.modules:
            return 1.0
        return min(1.0, sum(self._module_fraction(module) for module in self.modules) / float(len(self.modules)))

    def _workflow_status(self) -> str:
        if self.modules and all(module.status in {"done", "skipped"} for module in self.modules):
            return "completed"
        return "running"

    def _workflow_completed_at_epoch(self) -> float | None:
        completed_epochs = [
            module.completed_at_epoch
            for module in self.modules
            if module.completed_at_epoch is not None and module.status in {"done", "skipped"}
        ]
        if not completed_epochs:
            return None
        return max(completed_epochs)

    def _workflow_headline(self, workflow_status: str) -> str:
        if workflow_status == "completed":
            return "已完成所有流程"
        return "工作流运行中"

    def _workflow_caption(self, workflow_status: str, completed_at_epoch: float | None) -> str:
        started_at = self._format_timestamp_clock(self.started_at_epoch)
        if workflow_status == "completed":
            finished_at = self._format_timestamp_clock(completed_at_epoch)
            if started_at is not None and finished_at is not None:
                return f"本页面会停留在最终完成状态。开始于 {started_at}，完成于 {finished_at}。"
            return "本页面会停留在最终完成状态。"
        if started_at is not None:
            return f"页面会持续刷新直到完成。当前这次运行开始于 {started_at}。"
        return "页面会持续刷新直到完成。"

    def _module_fraction(self, module: ProgressModuleState) -> float:
        if module.status in {"done", "skipped"}:
            return 1.0
        if not module.steps:
            return 0.0
        return min(1.0, sum(self._step_fraction(step) for step in module.steps) / float(len(module.steps)))

    def _step_fraction(self, step: ProgressStepState) -> float:
        if step.status == "done":
            return 1.0
        if step.total is None:
            return 0.0
        if step.total <= 0:
            return 1.0
        return min(1.0, max(0.0, step.completed / step.total))

    def _estimate_remaining_seconds(self, fraction: float, elapsed: float) -> float | None:
        if fraction <= 0.0 or fraction >= 1.0 or elapsed <= 0.0:
            return None
        return max(0.0, elapsed * (1.0 - fraction) / fraction)

    def _format_duration(self, seconds: float | None) -> str:
        if seconds is None:
            return "--"
        total_seconds = max(0, int(round(seconds)))
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _format_eta_clock(self, seconds: float | None) -> str:
        if seconds is None:
            return "--"
        return (datetime.now() + timedelta(seconds=max(0.0, seconds))).strftime("%H:%M:%S")

    def _format_timestamp_clock(self, epoch_seconds: float | None) -> str | None:
        if epoch_seconds is None:
            return None
        return datetime.fromtimestamp(epoch_seconds).strftime("%H:%M:%S")

    def _iso_from_epoch(self, epoch_seconds: float | None) -> str | None:
        if epoch_seconds is None:
            return None
        return datetime.fromtimestamp(epoch_seconds).isoformat(timespec="seconds")

    def _monotonic_from_epoch(self, epoch_seconds: float) -> float:
        elapsed = max(0.0, time() - epoch_seconds)
        return monotonic() - elapsed

    def _as_float(self, value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _ensure_module_started(self, module: ProgressModuleState) -> None:
        if module.started_at is None:
            module.started_at = monotonic()
        if module.started_at_epoch is None:
            module.started_at_epoch = time()

    def _ensure_step_started(self, step: ProgressStepState) -> None:
        if step.started_at is None:
            step.started_at = monotonic()
        if step.started_at_epoch is None:
            step.started_at_epoch = time()

    def _bar_text(self, label: str, fraction: float, style: str, meta: str | None = None) -> Text:
        width = 22
        filled = max(0, min(width, int(round(width * fraction))))
        bar = "█" * filled + "░" * (width - filled)
        text = Text()
        text.append(f"{label:<18} ", style=style)
        text.append(f"[{bar}] ", style=style)
        text.append(f"{fraction * 100:5.1f}%", style=style)
        if meta:
            text.append(f"  {meta}", style="dim")
        return text


_WORKFLOW_PROGRESS: ContextVar[WorkflowProgressReporter | NoopWorkflowProgressReporter | None] = ContextVar(
    "WORKFLOW_PROGRESS",
    default=None,
)


def get_workflow_progress() -> WorkflowProgressReporter | NoopWorkflowProgressReporter:
    reporter = _WORKFLOW_PROGRESS.get()
    if reporter is None:
        return NoopWorkflowProgressReporter()
    return reporter


@contextmanager
def use_workflow_progress(reporter: WorkflowProgressReporter) -> Iterator[WorkflowProgressReporter]:
    token: Token[WorkflowProgressReporter | NoopWorkflowProgressReporter | None] = _WORKFLOW_PROGRESS.set(reporter)
    try:
        yield reporter
    finally:
        _WORKFLOW_PROGRESS.reset(token)
