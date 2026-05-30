"""
Copado AI Platform (Agentia AI Context Hub) — Dialogue API client.

Covers: start dialogue, send message, retrieve history.

The 6 specialist agents:
  plan      — Sprint planning, user story refinement, conflict detection
  build     — Code generation, metadata analysis, coverage improvement
  test      — CRT QWord script generation, automation advice
  release   — Deployment coordination, error analysis, release notes
  operate   — Post-release docs, change management, training materials
  knowledge — General Copado knowledge base queries

API shape (discovered from OpenAPI spec at copadogpt-api.robotic.copado.com):
  POST /organizations/{org_id}/dialogues                          — create dialogue
  POST /organizations/{org_id}/dialogues/{id}/messages            — send message (streaming NDJSON)
  GET  /organizations/{org_id}/dialogues                          — list dialogues
  GET  /organizations/{org_id}/dialogues/{id}                     — get dialogue detail
  GET  /organizations/{org_id}/workspaces                         — list workspaces
  GET  /prompts                                                   — list prompt templates
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

import httpx

from copado_hx.api import mock_data
from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings

VALID_AGENTS = {"plan", "build", "test", "release", "operate", "knowledge"}


def _base_url() -> str:
    return get_settings().copado_ai_base_url.rstrip("/")


def _org_id() -> str:
    return get_settings().ai_org_id


def _headers() -> dict:
    token = get_token("ai")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


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
    """Start a new dialogue session.

    POST /organizations/{org_id}/dialogues  { "name": "copado-hx ..." }
    Returns: { "id": "...", "name": "...", "assistant_id": "knowledge", ... }
    """
    agent = validate_agent(agent)
    if _is_mock():
        return mock_data.mock_ai_dialogue(agent)

    url = f"{_base_url()}/organizations/{_org_id()}/dialogues"
    r = httpx.post(url, headers=_headers(), json={"name": f"copado-hx {agent}"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return {"dialogueId": data.get("id", ""), **data}


def send_message(dialogue_id: str, message: str, agent: str = "") -> dict:
    """Send a message and collect the streamed response.

    POST /organizations/{org_id}/dialogues/{id}/messages
      { "request_id": "<uuid>", "prompt": "<message>" }

    Response is streamed NDJSON with token chunks.  We reassemble the full
    text and return {"content": "...", "dialogueId": "..."}.
    """
    if _is_mock():
        return mock_data.mock_ai_message(agent or "build", message)

    url = f"{_base_url()}/organizations/{_org_id()}/dialogues/{dialogue_id}/messages"
    req_id = str(uuid.uuid4())
    payload = {"request_id": req_id, "prompt": message}

    with httpx.stream("POST", url, headers=_headers(), json=payload, timeout=90) as resp:
        resp.raise_for_status()
        tokens: list[str] = []
        for line in resp.iter_lines():
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("type") == "token":
                tokens.append(chunk.get("content", ""))
        content = "".join(tokens)

    return {"content": content, "dialogueId": dialogue_id, "requestId": req_id}


def get_dialogue_history(dialogue_id: str) -> dict:
    """Retrieve the full message history for a dialogue."""
    if _is_mock():
        return {
            "dialogueId": dialogue_id,
            "messages": [
                mock_data.mock_ai_message("build", "sample prompt"),
            ],
        }

    url = f"{_base_url()}/organizations/{_org_id()}/dialogues/{dialogue_id}"
    r = httpx.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def list_dialogues() -> list[dict]:
    """List recent dialogues."""
    if _is_mock():
        return []

    url = f"{_base_url()}/organizations/{_org_id()}/dialogues"
    r = httpx.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def list_prompts(agent: Optional[str] = None) -> list[dict]:
    """List available prompt templates, optionally filtered by agent."""
    if _is_mock():
        return []

    url = f"{_base_url()}/prompts"
    r = httpx.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    prompts = r.json()
    if agent:
        prompts = [p for p in prompts if p.get("agent") == agent]
    return prompts


def list_workspaces(org_id: Optional[str] = None) -> list[dict]:
    """List available AI workspaces."""
    if _is_mock():
        return [
            {"id": "ws-001", "name": "Phoenix QA Workspace", "orgId": "org-001"},
        ]

    oid = org_id or _org_id()
    url = f"{_base_url()}/organizations/{oid}/workspaces"
    r = httpx.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()
