"""
Async-job polling utility.

Many Copado operations (commit, promote, deploy, test run) are asynchronous:
you trigger them, get back a job/execution ID, and poll until done.

This module provides a reusable poller with:
  - configurable interval and timeout
  - a Rich spinner for human-friendly output
  - Ctrl+C exits the polling view (job keeps running on the server)
"""

from __future__ import annotations

import time
from typing import Callable, Any, Optional

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

console = Console()

# Statuses that mean "still going"
IN_PROGRESS_STATUSES = {"In Progress", "Queued", "Running", "Pending", "InProgress",
                        "executing", "running", "queued", "pending"}

# Statuses that mean "done successfully"
SUCCESS_STATUSES = {"Completed Successfully", "Succeeded", "Success", "Completed", "Successful"}

# Statuses that mean "done but failed"
FAILURE_STATUSES = {"Failed", "Completed with Errors", "Error", "Cancelled", "failed"}


def poll_until_done(
    fetch_fn: Callable[[], dict],
    status_key: str = "status",
    interval: int = 10,
    timeout: int = 600,
    watch: bool = False,
    label: str = "Waiting for completion",
) -> dict:
    """
    Poll ``fetch_fn()`` until the returned dict's ``status_key`` field
    leaves the IN_PROGRESS set.

    Parameters
    ----------
    fetch_fn : callable returning a dict with at least a ``status_key`` field.
    status_key : which key to check in the returned dict.
    interval : seconds between polls.
    timeout : maximum seconds to wait (0 = unlimited).
    watch : if True, display a live spinner in the terminal.
    label : text shown next to the spinner.

    Returns
    -------
    The final dict returned by fetch_fn (with a terminal status).
    """
    start = time.time()
    last_result: Optional[dict] = None

    def _do_poll() -> dict:
        nonlocal last_result
        elapsed = 0
        while True:
            result = fetch_fn()
            last_result = result
            status = str(result.get(status_key, "Unknown"))

            if status not in IN_PROGRESS_STATUSES:
                return result

            elapsed = time.time() - start
            if timeout and elapsed >= timeout:
                result["_poll_timeout"] = True
                return result

            time.sleep(interval)

    try:
        if watch:
            spinner = Spinner("dots", text=Text(f" {label}...", style="bold cyan"))
            with Live(spinner, console=console, refresh_per_second=4):
                return _do_poll()
        else:
            return _do_poll()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exited polling view — job is still running on the server.[/yellow]")
        return last_result or {"status": "Cancelled", "_poll_interrupted": True}
