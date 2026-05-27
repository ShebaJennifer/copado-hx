"""
Output formatting helpers.

Every command in copado-hx supports two output modes:
  1. Human-readable (Rich tables, panels, colours) — default
  2. Machine-readable JSON (--json flag) — for AI agents and CI/CD pipelines

This module provides helpers so command authors never worry about formatting.
"""

from __future__ import annotations

import json as _json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def print_json(data: Any) -> None:
    """Pretty-print data as JSON to stdout."""
    console.print_json(_json.dumps(data, default=str, indent=2))


# ---------------------------------------------------------------------------
# Rich helpers
# ---------------------------------------------------------------------------

def print_success(message: str) -> None:
    console.print(f"[bold green]\u2705 {message}[/bold green]")


def print_error(message: str) -> None:
    err_console.print(f"[bold red]\u274c {message}[/bold red]")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]\u26a0\ufe0f  {message}[/bold yellow]")


def print_info(message: str) -> None:
    console.print(f"[bold cyan]\u2139\ufe0f  {message}[/bold cyan]")


def print_panel(title: str, content: str, style: str = "blue") -> None:
    """Display a Rich panel — great for summaries and status."""
    console.print(Panel(content, title=title, border_style=style, expand=False))


def make_table(title: str, columns: list[str], rows: list[list[str]]) -> Table:
    """Build a Rich table and return it (caller prints via console.print)."""
    table = Table(title=title, box=box.ROUNDED, show_lines=True)
    for col in columns:
        table.add_column(col, style="cyan", overflow="fold")
    for row in rows:
        table.add_row(*row)
    return table


def smart_output(data: Any, *, json_mode: bool, title: str = "", columns: list[str] | None = None) -> None:
    """
    Universal output dispatcher.

    If json_mode is True  -> print JSON.
    If json_mode is False -> print a Rich table (when data is a list of dicts)
                             or a Rich panel (when data is a single dict).
    """
    if json_mode:
        print_json(data)
        return

    if isinstance(data, list) and data and isinstance(data[0], dict):
        cols = columns or list(data[0].keys())
        rows = [[str(item.get(c, "")) for c in cols] for item in data]
        console.print(make_table(title or "Results", cols, rows))
    elif isinstance(data, dict):
        lines = "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in data.items())
        print_panel(title or "Details", lines)
    else:
        console.print(data)
