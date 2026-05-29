"""
Copado CI/CD (Agentia Pro) — Actions REST API client.

Covers: user stories, commit, promote, validate, deploy, job status, environments.

Real mode uses two API styles:
  - Salesforce REST API + SOQL for reading Copado objects (user stories, jobs, environments)
  - Copado Apex REST endpoints for actions (commit, promote, deploy)
"""

from __future__ import annotations

from typing import Optional

from copado_hx.api.base import BaseClient, SalesforceClient
from copado_hx.api import mock_data
from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings


def _get_client() -> SalesforceClient:
    """Get a SalesforceClient configured for the Copado org."""
    settings = get_settings()
    token = get_token("cicd")
    instance_url = settings.copado_sf_instance_url
    if not instance_url:
        raise RuntimeError(
            "Salesforce instance URL not configured. "
            "Run: copado-hx auth login  or set copado_sf_instance_url in .copado-hx.json"
        )
    if not token:
        raise RuntimeError(
            "CI/CD token not found. Run: copado-hx auth login"
        )
    return SalesforceClient(instance_url=instance_url, session_token=token)


def _is_mock() -> bool:
    return get_settings().mock_mode


# ---------------------------------------------------------------------------
# User Stories
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SOQL field mappings for copado__User_Story__c
# ---------------------------------------------------------------------------

_US_FIELDS = (
    "Id, Name, copado__User_Story_Title__c, copado__Status__c, "
    "copado__Environment__c, copado__Org_Credential__c, "
    "copado__Developer__c, copado__Project__c, "
    "LastModifiedDate, CreatedDate"
)


def _normalize_story(record: dict) -> dict:
    """Convert a Salesforce SOQL record into our standard story dict."""
    return {
        "id": record.get("Id", ""),
        "name": record.get("Name", ""),
        "title": record.get("copado__User_Story_Title__c", ""),
        "status": record.get("copado__Status__c", "Unknown"),
        "environment": record.get("copado__Environment__c", ""),
        "developer": record.get("copado__Developer__c", ""),
        "project": record.get("copado__Project__c", ""),
        "last_modified": record.get("LastModifiedDate", ""),
        "created": record.get("CreatedDate", ""),
    }


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
    where_clauses = []
    if status:
        where_clauses.append(f"copado__Status__c = '{status}'")
    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    soql = f"SELECT {_US_FIELDS} FROM copado__User_Story__c{where_sql} ORDER BY LastModifiedDate DESC LIMIT 50"
    records = client.query(soql)
    return [_normalize_story(r) for r in records]


def get_user_story(story_id: str) -> dict:
    """Get detailed information for a single user story."""
    if _is_mock():
        return mock_data.mock_story_detail(story_id)

    client = _get_client()
    soql = f"SELECT {_US_FIELDS} FROM copado__User_Story__c WHERE Name = '{story_id}' LIMIT 1"
    record = client.query_one(soql)
    if not record:
        return {"error": f"User story '{story_id}' not found"}
    return _normalize_story(record)


# ---------------------------------------------------------------------------
# Pipeline Actions
# ---------------------------------------------------------------------------

def commit(message: str, story_id: str) -> dict:
    """Commit metadata changes from a user story."""
    if _is_mock():
        return mock_data.mock_commit(message, story_id)

    client = _get_client()
    # First resolve the story's Salesforce Id from its Name (e.g. US-1234)
    story = client.query_one(
        f"SELECT Id FROM copado__User_Story__c WHERE Name = '{story_id}' LIMIT 1"
    )
    sf_id = story["Id"] if story else story_id
    return client.apexrest("copado/v1/webhook/commitFiles", method="POST", json_body={
        "userStoryId": sf_id,
        "message": message,
    })


def promote(story_id: str, environment: str, validate_only: bool = False) -> dict:
    """Promote a user story to the next environment."""
    if _is_mock():
        return mock_data.mock_promote(story_id, environment, validate_only)

    client = _get_client()
    story = client.query_one(
        f"SELECT Id FROM copado__User_Story__c WHERE Name = '{story_id}' LIMIT 1"
    )
    sf_id = story["Id"] if story else story_id
    action = "validateOnly" if validate_only else "promote"
    return client.apexrest(f"copado/v1/webhook/{action}", method="POST", json_body={
        "userStoryId": sf_id,
        "environment": environment,
    })


def deploy(environment: str) -> dict:
    """Execute a deployment to the target environment."""
    if _is_mock():
        return mock_data.mock_deploy(environment)

    client = _get_client()
    return client.apexrest("copado/v1/webhook/deploy", method="POST", json_body={
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


def list_environments() -> list[dict]:
    """List all pipeline environments."""
    if _is_mock():
        return mock_data.MOCK_ENVIRONMENTS

    client = _get_client()
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
