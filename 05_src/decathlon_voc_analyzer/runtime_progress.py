from __future__ import annotations

import os
import select
import sys
import termios
import threading
import tty
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from time import monotonic
from typing import Iterator

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class ProgressStepState:
    key: str
    label: str
    status: str = "pending"
    completed: float = 0.0
    total: float | None = None
    detail: str = ""
    started_at: float | None = None


@dataclass
class ProgressModuleState:
    key: str
    label: str
    status: str = "pending"
    steps: list[ProgressStepState] = field(default_factory=list)
    detail: str = ""


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
    def __init__(self, modules: list[tuple[str, str, list[tuple[str, str]]]], enabled: bool = True) -> None:
        self.enabled = enabled
        self.started_at = monotonic()
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
        self._stdin_fd: int | None = None
        self._stdin_termios: list[int] | None = None
        self._input_drain_stop = threading.Event()
        self._input_drain_thread: threading.Thread | None = None

    def __enter__(self) -> "WorkflowProgressReporter":
        if self.enabled:
            self._prepare_terminal()
            self._configure_terminal_input()
            self._live = Live(
                self.render(),
                console=self._console,
                screen=True,
                auto_refresh=True,
                refresh_per_second=4,
                transient=False,
                vertical_overflow="crop",
            )
            self._live.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._live is not None:
            self.refresh()
            self._live.stop()
            self._live = None
        self._restore_terminal_input()

    def activate_module(self, module_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        module.status = "in_progress"
        if detail:
            module.detail = detail
        self._active_module_key = module_key
        self._active_step_key = None
        self.refresh()

    def complete_module(self, module_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        module.status = "done"
        if detail:
            module.detail = detail
        self._active_module_key = None
        self._active_step_key = None
        self.refresh()

    def skip_module(self, module_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        module.status = "skipped"
        if detail:
            module.detail = detail
        self.refresh()

    def activate_step(self, module_key: str, step_key: str, detail: str | None = None) -> None:
        module = self._module_lookup[module_key]
        step = self._step_lookup[f"{module_key}:{step_key}"]
        module.status = "in_progress"
        step.status = "in_progress"
        step.started_at = monotonic()
        if detail:
            step.detail = detail
        self._active_module_key = module_key
        self._active_step_key = step_key
        self.refresh()

    def advance_step(self, module_key: str, step_key: str, amount: float = 1.0, detail: str | None = None) -> None:
        step = self._step_lookup[f"{module_key}:{step_key}"]
        step.completed += amount
        if detail:
            step.detail = detail
        self.refresh()

    def complete_step(self, module_key: str, step_key: str, detail: str | None = None) -> None:
        step = self._step_lookup[f"{module_key}:{step_key}"]
        if step.total is not None:
            step.completed = step.total
        else:
            step.completed = max(step.completed, 1.0)
        step.status = "done"
        if detail:
            step.detail = detail
        self._active_step_key = None
        self.refresh()

    def note(self, text: str) -> None:
        self._note = text
        self.refresh()

    def start_count_step(self, module_key: str, step_key: str, total: int, detail: str | None = None) -> None:
        step = self._step_lookup[f"{module_key}:{step_key}"]
        step.total = float(max(total, 0))
        step.completed = 0.0
        self.activate_step(module_key, step_key, detail=detail)

    def _prepare_terminal(self) -> None:
        # Clear the primary buffer and scrollback before switching to the
        # alternate screen so mouse-wheel scrolling doesn't reveal the shell
        # prompt and the original command line underneath the progress UI.
        terminal = self._console.file
        terminal.write("\x1b[3J\x1b[2J\x1b[H")
        terminal.flush()

    def _configure_terminal_input(self) -> None:
        if not sys.stdin.isatty():
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

    def render(self):
        header = self._render_header()
        modules = self._render_modules_table()
        bars = self._render_bars()
        return Panel(Group(header, modules, bars), title="Workflow Progress", border_style="cyan")

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(self.render(), refresh=True)

    def _render_header(self):
        elapsed = monotonic() - self.started_at
        active_module = self._module_lookup.get(self._active_module_key) if self._active_module_key else None
        active_step = None
        if active_module is not None and self._active_step_key is not None:
            active_step = self._step_lookup.get(f"{active_module.key}:{self._active_step_key}")

        header = Text()
        header.append(f"Elapsed {elapsed:6.1f}s", style="bold cyan")
        if active_module is not None:
            header.append("  ")
            header.append(f"Module: {active_module.label}", style="bold yellow")
        if active_step is not None:
            header.append("  ")
            header.append(f"Step: {active_step.label}", style="yellow")
            header.append("  ")
            header.append(f"Step Elapsed: {self._step_elapsed(active_step):5.1f}s", style="bold magenta")
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
        bars.add_row(self._bar_text("Overall", self._overall_fraction(), "cyan"), self._current_step_bar())
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
        return {
            "done": "done",
            "in_progress": "running",
            "skipped": "skipped",
        }.get(module.status, "pending")

    def _step_status_label(self, step: ProgressStepState) -> str:
        return {
            "done": "done",
            "in_progress": "running",
            "skipped": "skipped",
        }.get(step.status, "pending")

    def _module_progress_text(self, module: ProgressModuleState) -> Text:
        return self._bar_text(module.label, self._module_fraction(module), self._module_style(module))

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
        return self._bar_text(
            f"Current {step.label}",
            self._step_fraction(step),
            "yellow",
            meta=self._step_meta_text(step),
        )

    def _count_text(self, step: ProgressStepState) -> str | None:
        if step.total is None:
            return None
        completed = int(min(step.completed, step.total))
        total = int(step.total)
        return f"{completed}/{total}"

    def _step_elapsed(self, step: ProgressStepState) -> float:
        if step.started_at is None:
            return 0.0
        return max(0.0, monotonic() - step.started_at)

    def _step_meta_text(self, step: ProgressStepState) -> str | None:
        parts: list[str] = []
        count_text = self._count_text(step)
        if count_text is not None:
            parts.append(count_text)
        if step.status == "in_progress" and step.started_at is not None:
            parts.append(f"{self._step_elapsed(step):.1f}s")
        return " | ".join(parts) if parts else None

    def _overall_fraction(self) -> float:
        if not self.modules:
            return 1.0
        total = 0.0
        for module in self.modules:
            total += self._module_fraction(module)
        return min(1.0, total / float(len(self.modules)))

    def _module_fraction(self, module: ProgressModuleState) -> float:
        if module.status == "done":
            return 1.0
        if module.status == "skipped":
            return 1.0
        if not module.steps:
            return 1.0 if module.status == "done" else 0.0
        completed = 0.0
        for step in module.steps:
            completed += self._step_fraction(step)
        return min(1.0, completed / float(len(module.steps)))

    def _step_fraction(self, step: ProgressStepState) -> float:
        if step.status == "done":
            return 1.0
        if step.total is None:
            return 0.0 if step.status != "done" else 1.0
        if step.total <= 0:
            return 1.0
        return min(1.0, max(0.0, step.completed / step.total))

    def _bar_text(self, label: str, fraction: float, style: str, meta: str | None = None) -> Text:
        width = 22
        filled = int(round(width * fraction))
        filled = max(0, min(width, filled))
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