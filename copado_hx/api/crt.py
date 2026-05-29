"""
Copado Robotic Testing (CRT / Agentia Testing) — Open API client.

Covers: list test jobs, trigger test runs, poll execution status, retrieve results.

Key concept: In CRT, both "suites" and individual tests are addressed by a jobId.
The --suite flag in the CLI is a convenience alias for --job.
"""

from __future__ import annotations

from typing import Optional

from copado_hx.api.base import BaseClient
from copado_hx.api import mock_data
from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings


def _get_client() -> BaseClient:
    settings = get_settings()
    token = get_token("crt")
    if not token:
        raise RuntimeError("CRT token not found. Run: copado-hx auth login")
    return BaseClient(
        base_url=settings.copado_crt_base_url,
        headers={
            "Authorization": f"PAK {token}",
            "Content-Type": "application/json",
        },
    )


def _project_id() -> str:
    return get_settings().crt_project_id


def _org_id() -> str:
    return get_settings().crt_org_id


def _is_mock() -> bool:
    return get_settings().mock_mode


# ---------------------------------------------------------------------------
# Test Jobs
# ---------------------------------------------------------------------------

def list_test_jobs(project_id: Optional[str] = None) -> list[dict]:
    """List available test jobs/suites in the CRT project."""
    if _is_mock():
        return mock_data.MOCK_TEST_JOBS

    client = _get_client()
    pid = project_id or _project_id()
    oid = _org_id()
    params = {"orgId": oid} if oid else None
    return client.get(f"/pace/v4/projects/{pid}/jobs", params=params)


# ---------------------------------------------------------------------------
# Test Execution
# ---------------------------------------------------------------------------

def run_test(job_id: str, project_id: Optional[str] = None) -> dict:
    """Trigger a test job execution (a 'build' in CRT terms)."""
    if _is_mock():
        return mock_data.mock_test_run(job_id)

    client = _get_client()
    pid = project_id or _project_id()
    oid = _org_id()
    url = f"/pace/v4/projects/{pid}/jobs/{job_id}/builds"
    if oid:
        url += f"?orgId={oid}"
    return client.post(url)


def get_test_status(
    execution_id: str,
    job_id: str = "",
    project_id: Optional[str] = None,
) -> dict:
    """Poll the status of a running test execution."""
    if _is_mock():
        return mock_data.mock_test_status(execution_id)

    client = _get_client()
    pid = project_id or _project_id()
    oid = _org_id()
    params = {"orgId": oid} if oid else None
    return client.get(f"/pace/v4/projects/{pid}/jobs/{job_id}/builds/{execution_id}", params=params)


def get_test_results(
    execution_id: str,
    job_id: str = "",
    project_id: Optional[str] = None,
) -> dict:
    """Retrieve test results for a completed execution."""
    if _is_mock():
        return mock_data.mock_test_results(execution_id)

    client = _get_client()
    pid = project_id or _project_id()
    oid = _org_id()
    params = {"orgId": oid} if oid else None
    return client.get(
        f"/pace/v4/projects/{pid}/jobs/{job_id}/builds/{execution_id}/results",
        params=params,
    )
