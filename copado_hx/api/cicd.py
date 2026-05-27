"""
Copado CI/CD (Agentia Pro) — Actions REST API client.

Covers: user stories, commit, promote, validate, deploy, job status, environments.
"""

from __future__ import annotations

from typing import Optional

from copado_hx.api.base import BaseClient
from copado_hx.api import mock_data
from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings


def _get_client() -> BaseClient:
    settings = get_settings()
    token = get_token("cicd")
    return BaseClient(
        base_url=settings.copado_cicd_base_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )


def _is_mock() -> bool:
    return get_settings().mock_mode


# ---------------------------------------------------------------------------
# User Stories
# ---------------------------------------------------------------------------

def list_user_stories(
    pipeline: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    """List user stories, optionally filtered by pipeline and status."""
    if _is_mock():
        stories = mock_data.MOCK_USER_STORIES
        if status:
            stories = [s for s in stories if s["status"].lower() == status.lower()]
        return stories

    client = _get_client()
    params = {}
    if pipeline:
        params["pipeline"] = pipeline
    if status:
        params["status"] = status
    return client.get("/user-stories", params=params)


def get_user_story(story_id: str) -> dict:
    """Get detailed information for a single user story."""
    if _is_mock():
        return mock_data.mock_story_detail(story_id)

    client = _get_client()
    return client.get(f"/user-stories/{story_id}")


# ---------------------------------------------------------------------------
# Pipeline Actions
# ---------------------------------------------------------------------------

def commit(message: str, story_id: str) -> dict:
    """Commit metadata changes from a user story."""
    if _is_mock():
        return mock_data.mock_commit(message, story_id)

    client = _get_client()
    return client.post("/actions/commit", {
        "userStoryId": story_id,
        "message": message,
    })


def promote(story_id: str, environment: str, validate_only: bool = False) -> dict:
    """Promote a user story to the next environment."""
    if _is_mock():
        return mock_data.mock_promote(story_id, environment, validate_only)

    client = _get_client()
    endpoint = "/actions/validate" if validate_only else "/actions/promote"
    return client.post(endpoint, {
        "userStoryId": story_id,
        "environment": environment,
    })


def deploy(environment: str) -> dict:
    """Execute a deployment to the target environment."""
    if _is_mock():
        return mock_data.mock_deploy(environment)

    client = _get_client()
    return client.post("/actions/deploy", {
        "environment": environment,
    })


# ---------------------------------------------------------------------------
# Status / Polling
# ---------------------------------------------------------------------------

def get_job_status(job_id: str) -> dict:
    """Get the status of a job execution (commit, promote, deploy)."""
    if _is_mock():
        return mock_data.mock_job_status(job_id)

    client = _get_client()
    return client.get(f"/job-executions/{job_id}")


def list_environments() -> list[dict]:
    """List all pipeline environments."""
    if _is_mock():
        return mock_data.MOCK_ENVIRONMENTS

    client = _get_client()
    return client.get("/environments")
