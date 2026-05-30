"""
Copado CI/CD — API client with isolated read and action paths.

Architecture
────────────
READS  → Salesforce REST + SOQL  (Bearer <SF_ACCESS_TOKEN>)
         Objects: copado__User_Story__c, copado__JobExecution__c, copado__Environment__c

ACTIONS → POST /services/apexrest/copado/mcwebhook
          Headers:
            Authorization: Bearer <SF_ACCESS_TOKEN>
            copado-webhook-key: <COPADO_ACTIONS_KEY>
          Body varies by action (commit, promote, deploy).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from copado_hx.api.base import BaseClient, CopadoAPIError, SalesforceClient
from copado_hx.api import mock_data
from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings
from copado_hx.utils.output import print_warning

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — credential resolution
# ═══════════════════════════════════════════════════════════════════════════

def _is_mock() -> bool:
    return get_settings().mock_mode


def _resolve_sf_access_token() -> str:
    """Return the best available Salesforce access token.

    Priority:
      1. Dedicated sf_access_token (Session ID / OAuth token stored in keyring)
      2. Legacy cicd token (backward compat)
      3. OAuth password flow (auto-fetch if creds are available)
    """
    token = get_token("sf_access_token")
    if token:
        return token
    token = get_token("cicd")
    if token:
        return token

    # Attempt OAuth auto-refresh (browser or password flow)
    token = _oauth_auto_refresh()
    if token:
        return token

    raise RuntimeError(
        "No Salesforce access token found.\n"
        "Run: copado-hx auth login  to configure OAuth credentials."
    )


def _oauth_auto_refresh() -> Optional[str]:
    """Try to obtain a fresh SF access token automatically.

    Tries browser flow first, then password flow.
    Returns the token on success, None if required config is missing.
    """
    from copado_hx.auth.sf_oauth import browser_login, password_grant, SFOAuthError
    from copado_hx.auth.store import store_token

    settings = get_settings()
    client_id = settings.sf_client_id
    if not client_id:
        return None

    client_secret = get_token("sf_client_secret") or ""
    login_url = settings.sf_instance_url or "https://login.salesforce.com"

    # Try browser flow (interactive)
    log.debug("Attempting browser OAuth flow @ %s", login_url)
    try:
        result = browser_login(
            login_url=login_url,
            client_id=client_id,
            client_secret=client_secret,
        )
        store_token("sf_access_token", result.access_token)
        from copado_hx.utils.config import update_settings
        update_settings(sf_instance_url=result.instance_url, copado_sf_instance_url=result.instance_url)
        log.debug("Browser OAuth success — instance_url=%s", result.instance_url)
        return result.access_token
    except SFOAuthError:
        log.debug("Browser OAuth failed, trying password flow")

    # Try password flow (headless)
    username = settings.sf_username
    password = get_token("sf_password")
    if not all([username, password]):
        return None

    security_token = get_token("sf_security_token") or ""
    try:
        result = password_grant(
            login_url=login_url,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            security_token=security_token,
        )
        store_token("sf_access_token", result.access_token)
        from copado_hx.utils.config import update_settings
        update_settings(sf_instance_url=result.instance_url, copado_sf_instance_url=result.instance_url)
        log.debug("Password OAuth success — instance_url=%s", result.instance_url)
        return result.access_token
    except SFOAuthError:
        return None


def _resolve_sf_instance_url() -> str:
    settings = get_settings()
    url = settings.sf_instance_url or settings.copado_sf_instance_url
    if not url:
        raise RuntimeError(
            "Salesforce instance URL not configured.\n"
            "Run: copado-hx auth login  or set sf_instance_url in .copado-hx.json"
        )
    return url


def _resolve_actions_key() -> str:
    """Return the Copado Actions API Key (for mcwebhook)."""
    key = get_token("copado_actions_key")
    if not key:
        raise RuntimeError(
            "Copado Actions API Key not found.\n"
            "Run: copado-hx auth login  and provide the key from the Copado Actions API tab."
        )
    return key


# ═══════════════════════════════════════════════════════════════════════════
# READ client — Salesforce REST + SOQL
# ═══════════════════════════════════════════════════════════════════════════

def _get_read_client() -> SalesforceClient:
    """SalesforceClient for SOQL queries (reads only)."""
    return SalesforceClient(
        instance_url=_resolve_sf_instance_url(),
        session_token=_resolve_sf_access_token(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# ACTION client — mcwebhook
# ═══════════════════════════════════════════════════════════════════════════

def _post_mcwebhook(payload: dict) -> Any:
    """POST to /services/apexrest/copado/mcwebhook with dual-header auth.

    Headers:
      Authorization: Bearer <SF_ACCESS_TOKEN>
      copado-webhook-key: <COPADO_ACTIONS_KEY>
    """
    instance_url = _resolve_sf_instance_url()
    sf_token = _resolve_sf_access_token()
    actions_key = _resolve_actions_key()

    url = f"{instance_url.rstrip('/')}/services/apexrest/copado/mcwebhook"
    headers = {
        "Authorization": f"Bearer {sf_token}",
        "copado-webhook-key": actions_key,
        "Content-Type": "application/json",
    }

    log.debug("POST %s  payload=%s", url, payload)
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=60)
    except httpx.RequestError as exc:
        raise CopadoAPIError(0, f"Network error calling mcwebhook: {exc}")

    # ── Troubleshooting diagnostics ──
    if resp.status_code == 401:
        _troubleshoot_401(resp)
    elif resp.status_code == 403:
        _troubleshoot_403(resp)
    elif resp.status_code >= 400:
        try:
            body = resp.json()
            msg = body.get("message") or body.get("error") or str(body)
        except Exception:
            msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        raise CopadoAPIError(resp.status_code, msg)

    if resp.status_code == 204:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


# ═══════════════════════════════════════════════════════════════════════════
# Troubleshooting helpers
# ═══════════════════════════════════════════════════════════════════════════

def _troubleshoot_401(resp: httpx.Response) -> None:
    """Diagnose 401 Unauthorized from mcwebhook."""
    try:
        body = resp.json()
    except Exception:
        body = {}
    msg = str(body)

    if "INVALID_SESSION_ID" in msg or "Session expired" in msg:
        raise CopadoAPIError(401, (
            "Salesforce session expired or invalid.\n"
            "  → Re-run: copado-hx auth login  and paste a fresh SF Access Token / Session ID.\n"
            "  → Or configure OAuth password flow with sf_client_id / sf_client_secret."
        ))
    raise CopadoAPIError(401, f"Unauthorized: {msg}")


def _troubleshoot_403(resp: httpx.Response) -> None:
    """Diagnose 403 Forbidden from mcwebhook."""
    try:
        body = resp.json()
    except Exception:
        body = {}
    msg = str(body)

    hints = []
    if "copado-webhook-key" in msg.lower() or "webhook" in msg.lower():
        hints.append("The Copado Actions API Key appears invalid or missing.")
        hints.append("  → Generate a new key from Copado Actions API in App Launcher.")
    else:
        hints.append("403 Forbidden — possible causes:")
        hints.append("  1. Copado Actions API Key is wrong → regenerate in App Launcher")
        hints.append("  2. Pipeline is not source-format → check pipeline settings")
        hints.append("  3. User lacks Copado_User permission set")
    raise CopadoAPIError(403, "\n".join(hints))


def _troubleshoot_pipeline(pipeline_id: str) -> None:
    """Validate that the pipeline exists and is source-format."""
    try:
        client = _get_read_client()
        soql = (
            "SELECT Id, Name, copado__Platform__c "
            f"FROM copado__Pipeline__c WHERE Id = '{pipeline_id}' LIMIT 1"
        )
        record = client.query_one(soql)
        if not record:
            print_warning(f"Pipeline {pipeline_id} not found via SOQL. Check the 18-char Id.")
            return
        platform = record.get("copado__Platform__c", "")
        if platform and "source" not in platform.lower():
            print_warning(
                f"Pipeline '{record.get('Name', '')}' platform is '{platform}'.\n"
                "  mcwebhook actions require a source-format pipeline.\n"
                "  → In Copado Setup, ensure the pipeline Platform = 'Salesforce' with 'Source Format' enabled."
            )
    except Exception as exc:
        log.debug("Pipeline validation skipped: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# SOQL field mappings
# ═══════════════════════════════════════════════════════════════════════════

_US_FIELDS = (
    "Id, Name, copado__User_Story_Title__c, copado__Status__c, "
    "copado__Environment__c, copado__Environment__r.Name, copado__Org_Credential__c, "
    "copado__Developer__c, copado__Project__c, "
    "LastModifiedDate, CreatedDate"
)


def _normalize_story(record: dict) -> dict:
    """Convert a Salesforce SOQL record into our standard story dict."""
    # Resolve environment name from relationship field
    env_rel = record.get("copado__Environment__r") or {}
    env_name = env_rel.get("Name", "") if isinstance(env_rel, dict) else ""
    return {
        "id": record.get("Id", ""),
        "name": record.get("Name", ""),
        "title": record.get("copado__User_Story_Title__c", ""),
        "status": record.get("copado__Status__c", "Unknown"),
        "environment": env_name or record.get("copado__Environment__c", ""),
        "developer": record.get("copado__Developer__c", ""),
        "project": record.get("copado__Project__c", ""),
        "last_modified": record.get("LastModifiedDate", ""),
        "created": record.get("CreatedDate", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
# READ APIs  (SOQL)
# ═══════════════════════════════════════════════════════════════════════════

def list_user_stories(
    pipeline: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    """List user stories via SOQL. Falls back to mock if creds are missing."""
    if _is_mock():
        stories = mock_data.MOCK_USER_STORIES
        if status:
            stories = [s for s in stories if s["status"].lower() == status.lower()]
        return stories

    try:
        client = _get_read_client()
        where_clauses = []
        if status:
            where_clauses.append(f"copado__Status__c = '{status}'")
        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        soql = f"SELECT {_US_FIELDS} FROM copado__User_Story__c{where_sql} ORDER BY LastModifiedDate DESC LIMIT 50"
        records = client.query(soql)
        return [_normalize_story(r) for r in records]
    except Exception as exc:
        log.debug("SOQL read failed (%s) — falling back to mock data", exc)
        stories = mock_data.MOCK_USER_STORIES
        if status:
            stories = [s for s in stories if s["status"].lower() == status.lower()]
        return stories


def get_user_story(story_id: str) -> dict:
    """Get detailed information for a single user story."""
    if _is_mock():
        return mock_data.mock_story_detail(story_id)

    try:
        client = _get_read_client()
        soql = f"SELECT {_US_FIELDS} FROM copado__User_Story__c WHERE Name = '{story_id}' LIMIT 1"
        record = client.query_one(soql)
        if not record:
            return {"error": f"User story '{story_id}' not found"}
        return _normalize_story(record)
    except Exception as exc:
        log.debug("Story read failed (%s) — falling back to mock", exc)
        return mock_data.mock_story_detail(story_id)


def get_job_status(job_id: str) -> dict:
    """Get the status of a job execution (commit, promote, deploy)."""
    if _is_mock():
        return mock_data.mock_job_status(job_id)

    try:
        client = _get_read_client()
        soql = (
            "SELECT Id, Name, copado__Status__c, copado__ErrorMessage__c, "
            "CreatedDate, LastModifiedDate "
            f"FROM copado__JobExecution__c WHERE Id = '{job_id}' LIMIT 1"
        )
        record = client.query_one(soql)
        if not record:
            return {"jobId": job_id, "status": "Not Found"}
        return {
            "jobId": record.get("Id", ""),
            "name": record.get("Name", ""),
            "status": record.get("copado__Status__c", "Unknown"),
            "error": record.get("copado__ErrorMessage__c", ""),
            "lastModified": record.get("LastModifiedDate", ""),
        }
    except Exception as exc:
        log.debug("Job status read failed (%s) — falling back to mock", exc)
        return mock_data.mock_job_status(job_id)


def list_environments() -> list[dict]:
    """List all pipeline environments."""
    if _is_mock():
        return mock_data.MOCK_ENVIRONMENTS

    try:
        client = _get_read_client()
        soql = (
            "SELECT Id, Name, copado__Platform__c, copado__Type__c "
            "FROM copado__Environment__c ORDER BY Name"
        )
        records = client.query(soql)
        return [
            {
                "id": r.get("Id", ""),
                "name": r.get("Name", ""),
                "platform": r.get("copado__Platform__c", ""),
                "type": r.get("copado__Type__c", ""),
            }
            for r in records
        ]
    except Exception as exc:
        log.debug("Env read failed (%s) — falling back to mock", exc)
        return mock_data.MOCK_ENVIRONMENTS


# ═══════════════════════════════════════════════════════════════════════════
# ACTION APIs  (mcwebhook)
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_story_sf_id(story_name: str) -> str:
    """Resolve a human-friendly story name (US-1234) to its 18-char SF Id."""
    client = _get_read_client()
    record = client.query_one(
        f"SELECT Id FROM copado__User_Story__c WHERE Name = '{story_name}' LIMIT 1"
    )
    return record["Id"] if record else story_name


def commit(message: str, story_id: str) -> dict:
    """Commit metadata changes from a user story via mcwebhook."""
    if _is_mock():
        return mock_data.mock_commit(message, story_id)

    settings = get_settings()
    if settings.copado_actions_pipeline_id:
        _troubleshoot_pipeline(settings.copado_actions_pipeline_id)

    sf_id = _resolve_story_sf_id(story_id)
    return _post_mcwebhook({
        "action": "commitFiles",
        "userStoryId": sf_id,
        "message": message,
    })


def promote(story_id: str, environment: str, validate_only: bool = False) -> dict:
    """Promote a user story to the next environment via mcwebhook."""
    if _is_mock():
        return mock_data.mock_promote(story_id, environment, validate_only)

    settings = get_settings()
    if settings.copado_actions_pipeline_id:
        _troubleshoot_pipeline(settings.copado_actions_pipeline_id)

    sf_id = _resolve_story_sf_id(story_id)
    action = "validateOnly" if validate_only else "promote"
    return _post_mcwebhook({
        "action": action,
        "userStoryId": sf_id,
        "environment": environment,
    })


def deploy(environment: str) -> dict:
    """Execute a deployment to the target environment via mcwebhook."""
    if _is_mock():
        return mock_data.mock_deploy(environment)

    return _post_mcwebhook({
        "action": "deploy",
        "environment": environment,
    })
