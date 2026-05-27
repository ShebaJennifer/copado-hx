"""
Copado AI Platform (Agentia AI Context Hub) — Dialogue API client.

Covers: start dialogue, send message, retrieve history.

The 5 specialist agents:
  plan   — Sprint planning, user story refinement, conflict detection
  build  — Code generation, metadata analysis, coverage improvement
  test   — CRT QWord script generation, automation advice
  release — Deployment coordination, error analysis, release notes
  operate — Post-release docs, change management, training materials

Note: The Orchestrate Agent is OUT OF SCOPE for this hackathon.
"""

from __future__ import annotations

from typing import Optional

from copado_hx.api.base import BaseClient
from copado_hx.api import mock_data
from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings

VALID_AGENTS = {"plan", "build", "test", "release", "operate"}


def _get_client() -> BaseClient:
    settings = get_settings()
    token = get_token("ai")
    return BaseClient(
        base_url=settings.copado_ai_base_url,
        headers={
            "X-Authorization": token,
            "Content-Type": "application/json",
        },
    )


def _is_mock() -> bool:
    return get_settings().mock_mode


def validate_agent(agent: str) -> str:
    """Ensure the agent name is valid, return normalized name."""
    agent_lower = agent.lower()
    if agent_lower not in VALID_AGENTS:
        raise ValueError(
            f"Invalid agent '{agent}'. Valid agents: {', '.join(sorted(VALID_AGENTS))}"
        )
    return agent_lower


# ---------------------------------------------------------------------------
# Dialogues
# ---------------------------------------------------------------------------

def start_dialogue(agent: str) -> dict:
    """Start a new dialogue session with a specific agent."""
    agent = validate_agent(agent)
    if _is_mock():
        return mock_data.mock_ai_dialogue(agent)

    client = _get_client()
    return client.post("/dialogues", {"agent": agent})


def send_message(dialogue_id: str, message: str, agent: str = "") -> dict:
    """Send a message in an existing dialogue and get the agent's response."""
    if _is_mock():
        return mock_data.mock_ai_message(agent or "build", message)

    client = _get_client()
    return client.post(f"/dialogues/{dialogue_id}/messages", {
        "content": message,
    })


def get_dialogue_history(dialogue_id: str) -> dict:
    """Retrieve the full message history for a dialogue."""
    if _is_mock():
        return {
            "dialogueId": dialogue_id,
            "messages": [
                mock_data.mock_ai_message("build", "sample prompt"),
            ],
        }

    client = _get_client()
    return client.get(f"/dialogues/{dialogue_id}")


def list_workspaces(org_id: Optional[str] = None) -> list[dict]:
    """List available AI workspaces."""
    if _is_mock():
        return [
            {"id": "ws-001", "name": "Phoenix QA Workspace", "orgId": "org-001"},
        ]

    client = _get_client()
    oid = org_id or get_settings().ai_org_id
    return client.get(f"/organizations/{oid}/workspaces")
