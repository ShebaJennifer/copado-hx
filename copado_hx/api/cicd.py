"""
Copado CI/CD — API client with isolated read and action paths.

Architecture
────────────
READS  → Salesforce REST + SOQL  (Bearer <SF_ACCESS_TOKEN>)
         Objects: copado__User_Story__c, copado__JobExecution__c, copado__Environment__c,
                  copado__User_Story_Metadata__c

ACTIONS → Copado mcwebhook endpoint
          POST /services/apexrest/copado/mcwebhook
          Body: { "action": "<ActionName>", "key": "<API_KEY>", "payload": { ... } }
          Headers:
            Authorization: Bearer <SF_ACCESS_TOKEN>
            copado-webhook-key: <COPADO_ACTIONS_KEY>

          Action names:
            "Commit"              — commit metadata to feature branch
            "Promotion"           — create promotion record (Git merge)
            "PromotionDeployment" — trigger deployment (dry-run or real)

JOB STATUS → SOQL on copado__JobExecution__c (not a REST endpoint)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from copado_hx.api.base import BaseClient, CopadoAPIError, AuthExpiredError, SalesforceClient
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
# ACTION client — Copado Actions REST API
# ═══════════════════════════════════════════════════════════════════════════

_WEBHOOK_PATH = "/services/apexrest/copado/mcwebhook"


def _post_action(action: str, payload: dict) -> Any:
    """POST to Copado mcwebhook endpoint.

    Body structure:
      { "action": "<ActionName>", "key": "<COPADO_PERSONAL_API_KEY>",
        "payload": { ... } }

    Headers:
      Authorization: Bearer <SF_ACCESS_TOKEN>
      copado-webhook-key: <COPADO_PERSONAL_API_KEY>
    """
    instance_url = _resolve_sf_instance_url()
    sf_token = _resolve_sf_access_token()
    actions_key = _resolve_actions_key()

    url = f"{instance_url.rstrip('/')}{_WEBHOOK_PATH}"
    headers = {
        "Authorization": f"Bearer {sf_token}",
        "Content-Type": "application/json",
        "copado-webhook-key": actions_key,
    }
    body = {
        "action": action,
        "key": actions_key,
        "payload": payload,
    }

    log.debug("POST %s  body=%s", url, body)
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=60)
    except httpx.RequestError as exc:
        raise CopadoAPIError(0, f"Network error calling Copado Actions API: {exc}")

    # ── Troubleshooting diagnostics ──
    if resp.status_code == 401:
        _troubleshoot_401(resp)
    elif resp.status_code == 403:
        _troubleshoot_403(resp)
    elif resp.status_code >= 400:
        try:
            resp_body = resp.json()
            if isinstance(resp_body, list):
                msg = resp_body[0].get("message", str(resp_body))
            else:
                msg = resp_body.get("message") or resp_body.get("error") or str(resp_body)
        except Exception:
            msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        raise CopadoAPIError(resp.status_code, msg)

    if resp.status_code == 204:
        return {}
    try:
        result = resp.json()
        if isinstance(result, str):
            import json as _json
            result = _json.loads(result)
        return result
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
    except AuthExpiredError:
        # Do not fall back to mock data when auth expires - raise the error
        raise
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
    except AuthExpiredError:
        # Do not fall back to mock data when auth expires - raise the error
        raise
    except Exception as exc:
        log.debug("Story read failed (%s) — falling back to mock", exc)
        return mock_data.mock_story_detail(story_id)


def get_job_status(job_id: str) -> dict:
    """Get the status of a job execution by querying copado__JobExecution__c."""
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
    except AuthExpiredError:
        # Do not fall back to mock data when auth expires - raise the error
        raise
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
    except AuthExpiredError:
        # Do not fall back to mock data when auth expires - raise the error
        raise
    except Exception as exc:
        log.debug("Env read failed (%s) — falling back to mock", exc)
        return mock_data.MOCK_ENVIRONMENTS


def list_projects() -> list[dict]:
    """List all Copado projects."""
    if _is_mock():
        return mock_data.MOCK_PROJECTS if hasattr(mock_data, "MOCK_PROJECTS") else []

    try:
        client = _get_read_client()
        soql = "SELECT Id, Name FROM copado__Project__c ORDER BY Name"
        records = client.query(soql)
        return [
            {
                "id": r.get("Id", ""),
                "name": r.get("Name", ""),
            }
            for r in records
        ]
    except AuthExpiredError:
        raise
    except Exception as exc:
        log.debug("Project read failed (%s) — returning empty list", exc)
        return []


def list_releases(project_id: Optional[str] = None) -> list[dict]:
    """List Copado releases, optionally filtered by project."""
    if _is_mock():
        return mock_data.MOCK_RELEASES if hasattr(mock_data, "MOCK_RELEASES") else []

    try:
        client = _get_read_client()
        if project_id:
            soql = (
                f"SELECT Id, Name, copado__Project__c "
                f"FROM copado__Release__c "
                f"WHERE copado__Project__c = '{project_id}' "
                f"ORDER BY Name"
            )
        else:
            soql = "SELECT Id, Name, copado__Project__c FROM copado__Release__c ORDER BY Name"
        records = client.query(soql)
        return [
            {
                "id": r.get("Id", ""),
                "name": r.get("Name", ""),
                "project_id": r.get("copado__Project__c", ""),
            }
            for r in records
        ]
    except AuthExpiredError:
        raise
    except Exception as exc:
        log.debug("Release read failed (%s) — returning empty list", exc)
        return []


def list_credentials() -> list[dict]:
    """List all Copado org credentials."""
    if _is_mock():
        return mock_data.MOCK_CREDENTIALS if hasattr(mock_data, "MOCK_CREDENTIALS") else []

    try:
        client = _get_read_client()
        soql = "SELECT Id, Name FROM copado__Org__c ORDER BY Name"
        records = client.query(soql)
        return [
            {
                "id": r.get("Id", ""),
                "name": r.get("Name", ""),
            }
            for r in records
        ]
    except AuthExpiredError:
        raise
    except Exception as exc:
        log.debug("Credential read failed (%s) — returning empty list", exc)
        return []


# Cache for record type ID
_record_type_id_cache: Optional[str] = None


def get_user_story_record_type_id() -> Optional[str]:
    """Resolve the RecordTypeId for copado__User_Story__c.

    Queries RecordType for the user story object and returns the ID of the
    appropriate record type. Uses selection priority:
    1. DeveloperName matching Copado standard (e.g., User_Story)
    2. Name matching "User Story" (case-insensitive)
    3. First active record type if only one exists
    4. None if no record types exist

    Returns the cached result to avoid repeated queries.
    """
    global _record_type_id_cache
    if _record_type_id_cache is not None:
        return _record_type_id_cache

    if _is_mock():
        # Return a mock record type ID for consistency
        _record_type_id_cache = "0125g000000XXXX"
        return _record_type_id_cache

    try:
        client = _get_read_client()
        soql = (
            "SELECT Id, Name, DeveloperName "
            "FROM RecordType "
            "WHERE SObjectType = 'copado__User_Story__c' AND IsActive = true"
        )
        records = client.query(soql)

        if not records:
            log.debug("No active record types found for copado__User_Story__c")
            _record_type_id_cache = None
            return None

        # Priority 1: DeveloperName matching standard (e.g., User_Story)
        for r in records:
            dev_name = r.get("DeveloperName", "")
            # Common Copado developer names for user story record type
            if dev_name.lower() in ("user_story", "userstory", "copado__user_story"):
                _record_type_id_cache = r.get("Id")
                log.debug("Selected record type by DeveloperName: %s (%s)", dev_name, _record_type_id_cache)
                return _record_type_id_cache

        # Priority 2: Name matching "User Story" (case-insensitive)
        for r in records:
            name = r.get("Name", "")
            if name.lower() == "user story":
                _record_type_id_cache = r.get("Id")
                log.debug("Selected record type by Name: %s (%s)", name, _record_type_id_cache)
                return _record_type_id_cache

        # Priority 3: If only one exists, use it
        if len(records) == 1:
            _record_type_id_cache = records[0].get("Id")
            log.debug("Selected only available record type: %s", _record_type_id_cache)
            return _record_type_id_cache

        # Multiple record types but no match - log and return None
        log.debug("Multiple record types found but no match for User Story")
        _record_type_id_cache = None
        return None

    except AuthExpiredError:
        raise
    except Exception as exc:
        log.debug("Failed to resolve record type: %s", exc)
        _record_type_id_cache = None
        return None


# ═══════════════════════════════════════════════════════════════════════════
# ACTION APIs  — Create Promotion record, then trigger via mcwebhook
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_story_sf_id(story_name: str) -> str:
    """Resolve a human-friendly story name (US-1234) to its 18-char SF Id."""
    client = _get_read_client()
    record = client.query_one(
        f"SELECT Id FROM copado__User_Story__c WHERE Name = '{story_name}' LIMIT 1"
    )
    return record["Id"] if record else story_name


def _resolve_env_id(env_name: str) -> str:
    """Resolve environment name to SF Id."""
    client = _get_read_client()
    record = client.query_one(
        f"SELECT Id FROM copado__Environment__c WHERE Name = '{env_name}' LIMIT 1"
    )
    if not record:
        raise CopadoAPIError(404, f"Environment '{env_name}' not found")
    return record["Id"]


def _get_story_env_info(story_sf_id: str) -> dict:
    """Fetch environment, project, and release for a story."""
    client = _get_read_client()
    record = client.query_one(
        "SELECT copado__Environment__c, copado__Environment__r.Name, "
        "copado__Project__c, copado__Release__c "
        f"FROM copado__User_Story__c WHERE Id = '{story_sf_id}' LIMIT 1"
    )
    return record or {}


def _create_promotion_via_webhook(
    story_sf_id: str,
    project_id: str,
    source_env_id: str,
) -> str:
    """Create a Promotion record via mcwebhook 'Promotion' action.

    POST mcwebhook { action: "Promotion", key, payload: {
      userStoryIds, projectId, sourceEnvironmentId,
      executePromotion: true,   ← runs Git merge (creates promotion branch)
      executeDeployment: false   ← does NOT deploy yet
    }}

    Returns the promotionId from the response.
    """
    result = _post_action("Promotion", {
        "userStoryIds": [story_sf_id],
        "projectId": project_id,
        "sourceEnvironmentId": source_env_id,
        "executePromotion": True,
        "executeDeployment": False,
    })
    promo_id = ""
    if isinstance(result, dict):
        # Response nests the record under "promotion"
        promo = result.get("promotion") or {}
        promo_id = (
            promo.get("Id", "")
            or result.get("promotionId", "")
            or result.get("id", "")
        )
    if not promo_id:
        raise CopadoAPIError(500, f"Promotion action did not return a promotionId: {result}")
    return promo_id


def list_story_metadata(story_sf_id: str) -> list[dict]:
    """Query metadata components linked to a User Story.

    Returns a list of dicts in the Copado CommitChange schema:
      {"a": "Add", "n": "MyClass", "t": "ApexClass"}
    """
    client = _get_read_client()
    records = client.query(
        "SELECT copado__Type__c, Name, copado__Action__c "
        "FROM copado__User_Story_Metadata__c "
        f"WHERE copado__User_Story__c = '{story_sf_id}'"
    )
    return [
        {
            "t": r.get("copado__Type__c", ""),
            "n": r.get("Name", ""),
            "a": r.get("copado__Action__c", "Add"),
        }
        for r in records
    ]


# Metadata types queryable via Tooling API and their entity/field mappings
_TOOLING_TYPES: dict[str, tuple[str, str]] = {
    "ApexClass":                  ("ApexClass",      "Name"),
    "ApexTrigger":                ("ApexTrigger",    "Name"),
    "LightningComponentBundle":   ("LightningComponentBundle", "DeveloperName"),
    "AuraDefinitionBundle":       ("AuraDefinitionBundle",     "DeveloperName"),
    "Flow":                       ("FlowDefinition", "DeveloperName"),
    "CustomObject":               ("CustomObject",   "DeveloperName"),
    "CustomLabel":                ("ExternalString", "Name"),
    "ApexPage":                   ("ApexPage",       "Name"),
    "ApexComponent":              ("ApexComponent",  "Name"),
    "StaticResource":             ("StaticResource", "Name"),
    "PermissionSet":              ("PermissionSet",  "Name"),
}


def list_org_metadata(metadata_type: str) -> list[str]:
    """Query the org for component names of a given metadata type via Tooling API.

    Returns a sorted list of component names (excluding managed-package items).
    """
    mapping = _TOOLING_TYPES.get(metadata_type)
    if not mapping:
        return []
    entity, name_field = mapping
    client = _get_read_client()
    try:
        # ExternalString (CustomLabel) often from managed packages - don't filter by NamespacePrefix
        # Add date filter to show only recently changed components (last 7 days)
        if entity == "ExternalString":
            records = client.tooling_query(
                f"SELECT {name_field} FROM {entity} "
                f"WHERE LastModifiedDate = LAST_N_DAYS:7 "
                f"ORDER BY {name_field} LIMIT 200"
            )
        else:
            records = client.tooling_query(
                f"SELECT {name_field} FROM {entity} "
                f"WHERE NamespacePrefix = null "
                f"ORDER BY {name_field} LIMIT 200"
            )
        return [r.get(name_field, "") for r in records if r.get(name_field)]
    except Exception as exc:
        log.debug("Tooling query for %s failed: %s", metadata_type, exc)
        return []


def commit(message: str, story_id: str, changes: Optional[list[dict]] = None) -> dict:
    """Commit metadata changes via mcwebhook action 'Commit'.

    Args:
        message: Commit message.
        story_id: User story name (e.g. US-0000024) or SF Id.
        changes: Optional list of CommitChange dicts. If omitted, auto-detected
                 from copado__User_Story_Metadata__c.

    Returns:
        dict with jobExecutionId for polling, commitId, and component count.
    """
    if _is_mock():
        return mock_data.mock_commit(message, story_id)

    sf_id = _resolve_story_sf_id(story_id)

    # Auto-detect components if none provided
    if not changes:
        changes = list_story_metadata(sf_id)
    if not changes:
        raise CopadoAPIError(
            400,
            "No metadata components found for this User Story.\n"
            "  → Select components in the Copado UI first, or provide --changes <file.json>."
        )

    # Enrich changes with module/category fields for Copado v26.25 + SalesforceDx v8.19
    enriched_changes = [
        {
            "a": c.get("a", "Add"),
            "n": c.get("n"),
            "t": c.get("t"),
            "m": "force-app/main/default",
            "c": "SFDX",
        }
        for c in changes
    ]

    result = _post_action("Commit", {
        "userStoryId": sf_id,
        "changes": enriched_changes,
        "message": message,
    })

    # Extract real IDs from response
    job_exec = result.get("jobExecution", {}) if isinstance(result, dict) else {}
    us_commit = result.get("userStoryCommit", {}) if isinstance(result, dict) else {}
    return {
        "status": "Commit Triggered",
        "jobExecutionId": job_exec.get("Id", "") or _extract_job_id(result),
        "commitId": us_commit.get("Id", ""),
        "message": message,
        "userStory": story_id,
        "componentsCount": len(changes),
    }


def _extract_job_id(result: Any) -> str:
    """Extract jobExecutionId from a PromotionDeployment response.

    The mcwebhook may nest the ID in various ways:
      - result["jobExecutionId"]
      - result["jobExecution"]["Id"]
    """
    if not isinstance(result, dict):
        return ""
    # Direct key
    jid = result.get("jobExecutionId", "")
    if jid:
        return jid
    # Nested under jobExecution
    je = result.get("jobExecution") or {}
    if isinstance(je, dict):
        jid = je.get("Id", "") or je.get("id", "")
    return jid or ""


def _find_job_for_promotion(promo_id: str) -> str:
    """Fallback: find the latest JobExecution for a Promotion via SOQL."""
    try:
        client = _get_read_client()
        record = client.query_one(
            "SELECT Id FROM copado__JobExecution__c "
            f"WHERE copado__Promotion__c = '{promo_id}' "
            "ORDER BY CreatedDate DESC LIMIT 1"
        )
        return record["Id"] if record else ""
    except Exception:
        return ""


def validate(story_id: str) -> dict:
    """Validate changes — check-only deployment (no actual changes to target org).

    Flow:
      1. Resolve story → get projectId + sourceEnvironmentId
      2. POST mcwebhook action:"Promotion" with executePromotion:true
         → creates Promotion record and runs Git merge
      3. POST mcwebhook action:"PromotionDeployment" with deploymentDryRun:true
         → runs check-only deploy against target org
      4. Returns jobExecutionId for polling
    """
    if _is_mock():
        return mock_data.mock_validate(story_id)

    sf_id = _resolve_story_sf_id(story_id)
    info = _get_story_env_info(sf_id)
    project_id = info.get("copado__Project__c", "")
    source_env_id = info.get("copado__Environment__c", "")
    if not source_env_id:
        raise CopadoAPIError(400, "Story has no source environment set.")

    promo_id = _create_promotion_via_webhook(sf_id, project_id, source_env_id)

    result = _post_action("PromotionDeployment", {
        "promotionId": promo_id,
        "deploymentDryRun": True,
    })
    job_id = _extract_job_id(result) or _find_job_for_promotion(promo_id)
    return {
        "status": result.get("status", "Validation Triggered"),
        "jobExecutionId": job_id,
        "promotionId": promo_id,
        "userStory": story_id,
    }


def promote(story_id: str, environment: str) -> dict:
    """Promote a user story — Merge & Deploy to target environment.

    Flow:
      1. POST mcwebhook action:"Promotion" → creates Promotion record
      2. POST mcwebhook action:"PromotionDeployment" with deploymentDryRun:false
         → merges feature branch + deploys to target org
    """
    if _is_mock():
        return mock_data.mock_promote(story_id, environment, validate_only=False)

    sf_id = _resolve_story_sf_id(story_id)
    info = _get_story_env_info(sf_id)
    project_id = info.get("copado__Project__c", "")
    source_env_id = info.get("copado__Environment__c", "")
    if not source_env_id:
        raise CopadoAPIError(400, "Story has no source environment set.")

    promo_id = _create_promotion_via_webhook(sf_id, project_id, source_env_id)

    result = _post_action("PromotionDeployment", {
        "promotionId": promo_id,
        "deploymentDryRun": False,
    })
    job_id = _extract_job_id(result) or _find_job_for_promotion(promo_id)
    return {
        "status": result.get("status", "Merge & Deploy Triggered"),
        "promotionId": promo_id,
        "jobExecutionId": job_id,
        "userStory": story_id,
        "destination": environment,
    }


def deploy(promotion_id: str) -> dict:
    """Deploy an existing Promotion via mcwebhook (Merge & Deploy).

    Triggers PromotionDeployment on an already-created Promotion record.
    """
    if _is_mock():
        return mock_data.mock_deploy(promotion_id)

    result = _post_action("PromotionDeployment", {
        "promotionId": promotion_id,
        "deploymentDryRun": False,
    })
    job_id = _extract_job_id(result) or _find_job_for_promotion(promotion_id)
    return {
        "status": result.get("status", "Deployment Triggered"),
        "jobExecutionId": job_id,
        "promotionId": promotion_id,
    }


def create_user_story(
    title: str,
    project_id: str = "",
    release_id: str = "",
    credential_id: str = "",
    environment_id: str = "",
    status: str = "Draft",
) -> dict:
    """Create a new user story via Salesforce REST API.

    Creates a copado__User_Story__c record with the given fields.
    If release_id is provided but no project_id, derives project_id from the release.
    """
    if _is_mock():
        return mock_data.mock_create_user_story(title)

    # Handle release-without-project edge case: derive project from release
    if release_id and not project_id:
        try:
            client = _get_read_client()
            release = client.query_one(
                f"SELECT copado__Project__c FROM copado__Release__c WHERE Id = '{release_id}' LIMIT 1"
            )
            if release and release.get("copado__Project__c"):
                project_id = release["copado__Project__c"]
                log.debug("Derived project_id %s from release %s", project_id, release_id)
        except Exception as exc:
            log.debug("Failed to derive project from release: %s", exc)
            # Continue without project - let Salesforce validation handle it

    instance_url = _resolve_sf_instance_url()
    token = _resolve_sf_access_token()

    # Resolve record type ID
    record_type_id = get_user_story_record_type_id()

    story_data: dict[str, str] = {
        "copado__User_Story_Title__c": title,
        "copado__Status__c": status,
    }
    if project_id:
        story_data["copado__Project__c"] = project_id
    if release_id:
        story_data["copado__Release__c"] = release_id
    if credential_id:
        story_data["copado__Org_Credential__c"] = credential_id
    if environment_id:
        story_data["copado__Environment__c"] = environment_id
    if record_type_id:
        story_data["RecordTypeId"] = record_type_id

    resp = httpx.post(
        f"{instance_url}/services/data/v62.0/sobjects/copado__User_Story__c",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=story_data,
        timeout=30,
    )
    if resp.status_code != 201:
        raise CopadoAPIError(resp.status_code, resp.text[:500])

    record_id = resp.json()["id"]

    # Fetch back the created record with related fields to get resolved names
    try:
        client = _get_read_client()
        created = client.query_one(
            f"SELECT Id, Name, copado__User_Story_Title__c, copado__Status__c, "
            f"copado__Project__c, copado__Project__r.Name, "
            f"copado__Release__c, copado__Release__r.Name, "
            f"copado__Environment__c, copado__Environment__r.Name, "
            f"copado__Org_Credential__c, copado__Org_Credential__r.Name, "
            f"RecordTypeId, RecordType.Name "
            f"FROM copado__User_Story__c WHERE Id = '{record_id}' LIMIT 1"
        )
        if created:
            return {
                "id": record_id,
                "name": created.get("Name", record_id),
                "title": created.get("copado__User_Story_Title__c", title),
                "status": created.get("copado__Status__c", status),
                "project_id": created.get("copado__Project__c", ""),
                "project": (created.get("copado__Project__r") or {}).get("Name", ""),
                "release_id": created.get("copado__Release__c", ""),
                "release": (created.get("copado__Release__r") or {}).get("Name", ""),
                "environment_id": created.get("copado__Environment__c", ""),
                "environment": (created.get("copado__Environment__r") or {}).get("Name", ""),
                "credential_id": created.get("copado__Org_Credential__c", ""),
                "credential": (created.get("copado__Org_Credential__r") or {}).get("Name", ""),
                "record_type_id": created.get("RecordTypeId", ""),
                "record_type": (created.get("RecordType") or {}).get("Name", ""),
            }
        else:
            # Fallback if read-back fails
            return {
                "id": record_id,
                "name": record_id,
                "title": title,
                "status": status,
                "project_id": project_id,
                "project": "",
                "release_id": release_id,
                "release": "",
                "environment_id": environment_id,
                "environment": "",
                "credential_id": credential_id,
                "credential": "",
                "record_type_id": record_type_id or "",
                "record_type": "",
            }
    except Exception as exc:
        log.debug("Read-back after create failed: %s", exc)
        # Return what we have even if read-back fails
        return {
            "id": record_id,
            "name": record_id,
            "title": title,
            "status": status,
            "project_id": project_id,
            "project": "",
            "release_id": release_id,
            "release": "",
            "environment_id": environment_id,
            "environment": "",
            "credential_id": credential_id,
            "credential": "",
            "record_type_id": record_type_id or "",
            "record_type": "",
        }
