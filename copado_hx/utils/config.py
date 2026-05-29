"""
Configuration management for copado-hx.

Reads .copado-hx.json from the project root (or home dir) and provides
a single Settings object used by every module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


_CONFIG_FILENAME = ".copado-hx.json"


class Settings(BaseModel):
    """Global settings loaded from .copado-hx.json."""

    # Copado API base URLs
    copado_sf_instance_url: str = Field(default="", description="Salesforce org URL (e.g. https://myorg.my.salesforce.com)")
    copado_cicd_base_url: str = Field(default="", description="Base URL for Copado CI/CD REST API (auto-derived from SF instance URL if blank)")
    copado_crt_base_url: str = Field(default="https://eu-robotic.copado.com", description="Base URL for CRT Open API")
    copado_ai_base_url: str = Field(
        default="https://copadogpt-api.robotic.copado.com",
        description="Base URL for Copado AI Platform API",
    )

    # Default IDs — so you don't have to pass them every time
    default_pipeline: str = ""
    default_environment: str = ""
    crt_project_id: str = ""
    crt_org_id: str = ""
    ai_org_id: str = ""
    ai_workspace_id: str = ""

    # Active user story context (set by `story set`)
    current_story_id: str = ""

    # Mock mode — when True, API clients return sample data instead of real calls
    mock_mode: bool = True


def _find_config_file() -> Optional[Path]:
    """Walk up from CWD looking for .copado-hx.json, then check home dir."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    home_candidate = Path.home() / _CONFIG_FILENAME
    if home_candidate.is_file():
        return home_candidate
    return None


def load_settings() -> Settings:
    """Load settings from the config file, falling back to defaults."""
    config_path = _find_config_file()
    if config_path is None:
        return Settings()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return Settings(**data)
    except Exception:
        return Settings()


def save_settings(settings: Settings) -> Path:
    """Persist settings to .copado-hx.json in the current directory."""
    config_path = Path.cwd() / _CONFIG_FILENAME
    config_path.write_text(
        json.dumps(settings.model_dump(), indent=2),
        encoding="utf-8",
    )
    return config_path


# Singleton — loaded once, reused everywhere
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the cached Settings instance (loads on first call)."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def update_settings(**kwargs) -> Settings:
    """Update specific fields and persist."""
    global _settings
    s = get_settings()
    updated = s.model_copy(update=kwargs)
    save_settings(updated)
    _settings = updated
    return updated
