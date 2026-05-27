"""
Realistic mock data for all Copado API surfaces.

Used when mock_mode is True (i.e., before hackathon credentials are available).
Also serves as a live-demo fallback if APIs are slow.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rand_id(prefix: str = "") -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{suffix}"


# ---------------------------------------------------------------------------
# CI/CD Mock Data
# ---------------------------------------------------------------------------

MOCK_USER_STORIES = [
    {
        "id": "a1B5g00000US1234",
        "name": "US-1234",
        "title": "Add Lead Scoring Logic",
        "status": "In Progress",
        "pipeline": "Main Pipeline",
        "environment": "DEV",
        "developer": "sheba.jennifer",
        "last_modified": "2026-05-26T10:30:00Z",
    },
    {
        "id": "a1B5g00000US1235",
        "name": "US-1235",
        "title": "Fix Account Trigger Bulk Issue",
        "status": "Ready for Testing",
        "pipeline": "Main Pipeline",
        "environment": "UAT",
        "developer": "sheba.jennifer",
        "last_modified": "2026-05-25T14:15:00Z",
    },
    {
        "id": "a1B5g00000US1236",
        "name": "US-1236",
        "title": "Opportunity Split Automation",
        "status": "Approved",
        "pipeline": "Main Pipeline",
        "environment": "DEV",
        "developer": "team.member",
        "last_modified": "2026-05-24T09:00:00Z",
    },
]


def mock_story_detail(story_id: str) -> dict:
    for s in MOCK_USER_STORIES:
        if s["name"] == story_id or s["id"] == story_id:
            return {
                **s,
                "metadata_scope": [
                    {"name": "LeadScoring.cls", "type": "ApexClass"},
                    {"name": "LeadScoring.cls-meta.xml", "type": "ApexClass"},
                    {"name": "Lead.object", "type": "CustomObject"},
                ],
                "feature_branch": f"feature/{s['name']}",
            }
    return {"error": f"User story {story_id} not found"}


def mock_commit(message: str, story_id: str) -> dict:
    return {
        "commitId": _rand_id("cmt-"),
        "status": "Completed Successfully",
        "userStory": story_id,
        "message": message,
        "filesCommitted": ["LeadScoring.cls", "LeadScoring.cls-meta.xml", "Lead.object"],
        "timestamp": _ts(),
    }


def mock_promote(story_id: str, env: str, validate_only: bool = False) -> dict:
    return {
        "promotionId": _rand_id("prm-"),
        "status": "In Progress",
        "userStory": story_id,
        "targetEnvironment": env,
        "validateOnly": validate_only,
        "jobExecutionId": _rand_id("job-"),
        "timestamp": _ts(),
    }


def mock_deploy(env: str) -> dict:
    return {
        "deploymentId": _rand_id("dep-"),
        "status": "In Progress",
        "targetEnvironment": env,
        "jobExecutionId": _rand_id("job-"),
        "timestamp": _ts(),
    }


def mock_job_status(job_id: str, force_done: bool = False) -> dict:
    status = "Completed Successfully" if force_done else random.choice(
        ["In Progress", "In Progress", "Completed Successfully"]
    )
    return {
        "jobExecutionId": job_id,
        "status": status,
        "startTime": "2026-05-27T10:00:00Z",
        "endTime": _ts() if "Completed" in status else None,
        "logs": "Deployment validated successfully. 3 components transferred." if "Completed" in status else "Running...",
    }


MOCK_ENVIRONMENTS = [
    {"id": "env-dev-001", "name": "DEV", "type": "Development", "org_id": "00D5g000007XXXX"},
    {"id": "env-sit-001", "name": "SIT", "type": "Integration", "org_id": "00D5g000007YYYY"},
    {"id": "env-uat-001", "name": "UAT", "type": "Staging", "org_id": "00D5g000007ZZZZ"},
    {"id": "env-prod-001", "name": "PROD", "type": "Production", "org_id": "00D5g000007WWWW"},
]


# ---------------------------------------------------------------------------
# CRT Mock Data
# ---------------------------------------------------------------------------

MOCK_TEST_JOBS = [
    {"jobId": "job-smoke-001", "name": "Smoke Test Suite", "project": "Phoenix QA", "testCount": 15},
    {"jobId": "job-regression-001", "name": "Full Regression Suite", "project": "Phoenix QA", "testCount": 87},
    {"jobId": "job-lead-scoring-001", "name": "Lead Scoring Tests", "project": "Phoenix QA", "testCount": 8},
]


def mock_test_run(job_id: str) -> dict:
    return {
        "executionId": _rand_id("exec-"),
        "status": "Running",
        "projectId": "proj-phoenix-001",
        "jobId": job_id,
        "startTime": _ts(),
    }


def mock_test_status(execution_id: str, force_done: bool = False) -> dict:
    status = "Succeeded" if force_done else random.choice(["Running", "Running", "Succeeded"])
    return {
        "executionId": execution_id,
        "status": status,
        "duration": "2m 34s" if status == "Succeeded" else "running...",
    }


def mock_test_results(execution_id: str) -> dict:
    return {
        "executionId": execution_id,
        "testResult": "Succeeded",
        "totalTests": 15,
        "passed": 14,
        "failed": 1,
        "skipped": 0,
        "duration": "2m 34s",
        "failures": [
            {
                "testName": "TestLeadScoring_BulkInsert",
                "error": "Expected 200 records but got 150. Batch size limit exceeded.",
                "class": "LeadScoringTest",
            }
        ],
        "passRate": "93%",
    }


# ---------------------------------------------------------------------------
# AI Platform Mock Data
# ---------------------------------------------------------------------------

MOCK_AI_RESPONSES = {
    "plan": "Based on analysis of US-1234, the Lead Scoring feature impacts 3 metadata components: "
    "LeadScoring.cls, Lead.object (custom fields), and LeadScoring_Flow. "
    "No conflicts detected with other in-progress user stories. "
    "Recommended sprint allocation: 5 story points.",
    "build": "For US-1234 (Lead Scoring), you should commit the following metadata:\n"
    "1. **LeadScoring.cls** — Main Apex class with scoring logic\n"
    "2. **LeadScoring.cls-meta.xml** — Class metadata\n"
    "3. **Lead.object** — Custom field: Score__c (Number)\n\n"
    "The code follows Apex best practices with bulkified trigger patterns.",
    "test": "Generated CRT QWord test script for LeadScoring:\n\n"
    "```\n"
    "*** Test Cases ***\n"
    "Verify Lead Score Calculation\n"
    "    OpenApp    Sales\n"
    "    ClickText  Leads\n"
    "    ClickText  New\n"
    "    TypeText   Last Name    Test Lead\n"
    "    TypeText   Company      Test Corp\n"
    "    ClickText  Save\n"
    "    VerifyField    Lead Score    75\n"
    "```",
    "release": "**Release Notes for US-1234 — Lead Scoring Logic**\n\n"
    "**What changed:** Added automated lead scoring based on engagement metrics.\n\n"
    "**Components deployed:**\n"
    "- LeadScoring.cls (new)\n"
    "- Lead.object (modified — added Score__c field)\n\n"
    "**Impact:** All new leads will receive an automatic score (0-100) based on "
    "email opens, page visits, and form submissions.\n\n"
    "**Rollback plan:** Deactivate the LeadScoring trigger and remove Score__c field.",
    "operate": "**Change Management Plan — Lead Scoring (US-1234)**\n\n"
    "**Training required:** Sales team needs 30-min walkthrough on new Score column.\n\n"
    "**Documentation:** Update Sales Playbook section 4.2 with scoring criteria.\n\n"
    "**Monitoring:** Set up a report to track score distribution for first 2 weeks.\n\n"
    "**Rollback trigger:** If >10% of leads show score = 0 after 48 hours, investigate.",
}


def mock_ai_dialogue(agent: str) -> dict:
    return {
        "dialogueId": _rand_id("dlg-"),
        "agent": agent,
        "status": "active",
        "timestamp": _ts(),
    }


MOCK_TRIAGE_RESPONSE = (
    "**Root Cause Analysis**\n\n"
    "The test `TestLeadScoring_BulkInsert` failed because it expects 200 records "
    "but the batch size was reduced to 150 in the latest commit.\n\n"
    "**Root Cause:** The `LeadScoring.cls` trigger now enforces a batch limit of 150 "
    "records per transaction (changed from 200). The test data setup still inserts 200 records.\n\n"
    "**Recommended Fix:**\n"
    "1. Update the test to use 150 records instead of 200, OR\n"
    "2. Revert the batch size limit in `LeadScoring.cls` back to 200\n\n"
    "**Risk Assessment:** Low — this is an isolated test data mismatch, not a logic error.\n\n"
    "**Confidence:** Safe to deploy after fixing the test assertion."
)


def mock_ai_message(agent: str, prompt: str) -> dict:
    # Context-aware: if the prompt mentions failures/errors, return triage analysis
    prompt_lower = prompt.lower()
    if any(kw in prompt_lower for kw in ["fail", "error", "analyze", "triage", "diagnos"]):
        response_text = MOCK_TRIAGE_RESPONSE
    else:
        response_text = MOCK_AI_RESPONSES.get(agent, f"[{agent} agent] Response to: {prompt}")
    return {
        "messageId": _rand_id("msg-"),
        "agent": agent,
        "role": "assistant",
        "content": response_text,
        "timestamp": _ts(),
    }
