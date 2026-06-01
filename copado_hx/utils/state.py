"""
Lightweight session state for copado-hx workflow engine.

Tracks the *last action* and *last result* so that `copado-hx next` can
recommend context-aware follow-up commands.  State is persisted to
.copado-hx-state.json in the project root (gitignored).

This is intentionally simple — a flat JSON dict, not a database.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_STATE_FILE = ".copado-hx-state.json"


def _state_path() -> Path:
    return Path.cwd() / _STATE_FILE


def load_state() -> dict:
    """Load session state from disk.  Returns empty dict if missing."""
    p = _state_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    """Persist session state to disk."""
    _state_path().write_text(
        json.dumps(state, indent=2, default=str),
        encoding="utf-8",
    )


def record_action(action: str, **extras: Any) -> None:
    """Record that an action just happened (e.g. 'commit', 'promote')."""
    state = load_state()
    state["last_action"] = action
    state["last_action_time"] = datetime.now(timezone.utc).isoformat()
    state.update(extras)
    save_state(state)


def get_last_action() -> Optional[str]:
    return load_state().get("last_action")


def get_state_value(key: str, default: Any = None) -> Any:
    return load_state().get(key, default)
