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
            "X-Authorization": token,
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
    response = client.get(f"/pace/v4/projects/{pid}/jobs", params=params)
    
    # Normalize CRT response to expected format
    if isinstance(response, dict) and "data" in response:
        jobs = response["data"]
        # Map CRT fields to CLI expected fields
        normalized = []
        for job in jobs:
            normalized.append({
                "jobId": str(job.get("id", "")),
                "name": job.get("name", ""),
                "testCount": len(job.get("tests", [])) if "tests" in job else "N/A"
            })
        return normalized
    
    return response


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
    response = client.post(url)
    
    # Normalize CRT response to extract execution ID
    if isinstance(response, dict) and "data" in response:
        data = response["data"]
        # Add executionId field for CLI compatibility
        if "id" in data:
            data["executionId"] = str(data["id"])
        return response
    
    return response


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

    # Results are included in the status response - no separate results endpoint
    response = get_test_status(execution_id, job_id, project_id)
    
    # Normalize CRT response to CLI expected format
    if isinstance(response, dict) and "data" in response:
        data = response["data"]
        failures = []
        total = passed = failed = skipped = 0

        # Strategy 1: xunitReport (real CRT responses)
        xunit = data.get("xunitReport")
        if isinstance(xunit, dict):
            testsuite = xunit.get("testsuite", {})
            testcases = testsuite.get("testcase", [])
            if isinstance(testcases, dict):
                testcases = [testcases]
            total = len(testcases)
            for tc in testcases:
                tc_failures = tc.get("failure", [])
                if isinstance(tc_failures, dict):
                    tc_failures = [tc_failures]
                if tc_failures:
                    failed += 1
                    error_msgs = "; ".join(f.get("message", "Test failed") for f in tc_failures)
                    failures.append({
                        "testName": tc.get("name", "Unknown"),
                        "class": tc.get("classname", "Test"),
                        "error": error_msgs,
                    })
                else:
                    passed += 1

        # Strategy 2: jsonObjReport (alternative CRT format)
        if total == 0:
            json_report = data.get("jsonObjReport")
            if isinstance(json_report, dict) and "statistics" in json_report:
                stats = json_report["statistics"]
                total_stats = stats.get("total", [])
                if isinstance(total_stats, list) and total_stats:
                    main_stats = total_stats[0]
                    passed = int(main_stats.get("pass", 0))
                    failed = int(main_stats.get("fail", 0))
                    skipped = int(main_stats.get("skip", 0))
                    total = passed + failed + skipped

                suites = json_report.get("suites", [])
                for suite in suites:
                    for test in suite.get("tests", []):
                        if test.get("status") == "failed":
                            failures.append({
                                "testName": test.get("name", "Unknown"),
                                "class": suite.get("name", "Test"),
                                "error": test.get("failure", {}).get("message", "Test failed"),
                            })

        # Strategy 3: top-level status fallback
        if total == 0 and data.get("status") == "failed":
            total = 1
            failed = 1
            failures.append({
                "testName": "Build Execution",
                "class": str(data.get("jobId", "")),
                "error": f"Build {execution_id} failed (status: {data.get('status')})",
            })

        return {
            "totalTests": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "passRate": f"{(passed/total*100):.1f}%" if total > 0 else "0%",
            "duration": data.get("duration", "N/A"),
            "testResult": "Failed" if failed > 0 else "Succeeded",
            "failures": failures,
        }

    return response
