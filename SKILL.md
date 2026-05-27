# SKILL.md — copado-hx Agent Instruction File

> This file teaches any AI coding agent (Cursor, Claude, OpenAI, Agentforce, or any MCP-compatible system) how to use `copado-hx` as a native skill within a Salesforce DevOps workflow.

---

## Identity

You have access to `copado-hx`, a CLI that gives you full control over the Copado DevOps platform for Salesforce. Through this skill you can manage user stories, trigger CI/CD pipeline actions (commit, promote, validate, deploy), execute Copado Robotic Testing (CRT) test suites, and converse with Copado's 5 specialist AI agents (Plan, Build, Test, Release, Operate) — all without opening a browser.

`copado-hx` covers three Copado API surfaces:
- **CI/CD (Agentia Pro)** — User stories, commits, promotions, deployments, pipeline status
- **CRT (Agentia Testing)** — Test job execution, status polling, results retrieval
- **AI Platform (Agentia AI Context Hub)** — 5 specialist agents for the full DevOps lifecycle

---

## Prerequisites

Before executing any `copado-hx` command:

1. Run `copado-hx auth status` to verify an authenticated session exists.
2. If **not authenticated**, instruct the user to run `copado-hx auth login` and **pause** until authentication is confirmed.
3. A working user story context **must** be set with `copado-hx story set --id <US-ID>` before any commit, promote, or deploy operation.
4. **Never infer or fabricate** pipeline IDs, environment names, user story IDs, or job IDs. Always retrieve them from `copado-hx story list`, `copado-hx test list`, or `copado-hx status`.

---

## Commands Reference

### `copado-hx auth login`
**Purpose:** Authenticate with Copado APIs.
**When to use:** Before any other command, if `auth status` shows "Not configured".
**Syntax:** `copado-hx auth login` (interactive) or `copado-hx auth login --token <token> --type <cicd|crt|ai>`
**Output:** Auth status summary showing which APIs are connected.

### `copado-hx auth status`
**Purpose:** Check authentication state.
**Syntax:** `copado-hx auth status --json`
**Output:** JSON with authentication status for each API surface.

### `copado-hx story list`
**Purpose:** List user stories assigned to the current user.
**When to use:** To discover available user stories before setting context.
**Syntax:** `copado-hx story list [--pipeline <id>] [--status "In Progress"] --json`
**Output:** JSON array of user story objects with `id`, `name`, `title`, `status`, `environment`.

### `copado-hx story set`
**Purpose:** Set the active user story context (like `git checkout` for Copado).
**When to use:** Before any commit, promote, or deploy operation.
**Syntax:** `copado-hx story set --id <US-ID>`
**Output:** Confirmation and story details.
**Do not skip:** This command is required before pipeline operations.

### `copado-hx story show`
**Purpose:** Show details and metadata scope for a user story.
**Syntax:** `copado-hx story show [--id <US-ID>] --json`
**Output:** JSON with story details including `metadata_scope[]`.

### `copado-hx commit`
**Purpose:** Commit metadata changes from the current user story to Git and update the Copado user story record.
**When to use:** After the developer has made local code/config changes and wants to push them to the feature branch.
**Syntax:** `copado-hx commit --message <msg> [--us <US-ID>] --json`
**Output:** JSON with `{ commitId, status, filesCommitted[] }`
**Do not use if:** No user story context is set. Run `copado-hx story set` first.

### `copado-hx promote`
**Purpose:** Promote a user story to the next environment in the pipeline.
**Syntax:** `copado-hx promote --env <ENV> [--us <US-ID>] [--validate] [--watch] --json`
**Flags:**
- `--validate` : Run a validation-only deployment (no actual deploy)
- `--env <name>` : Target environment (e.g., UAT, SIT, PROD)
- `--watch` : Poll until the promotion job completes
**Output:** JSON with `{ promotionId, status, jobExecutionId }`
**Poll for completion:** Use `copado-hx status --job <jobExecutionId> --watch`

### `copado-hx deploy`
**Purpose:** Execute a deployment to the target environment.
**Syntax:** `copado-hx deploy --env <ENV> [--watch] [--yes] --json`
**Flags:**
- `--yes` : Skip the human confirmation prompt (use ONLY for non-production environments)
**Output:** JSON with `{ deploymentId, status, jobExecutionId }`
**CRITICAL:** Never use `--yes` flag for PROD deployments. Always let the human confirm.

### `copado-hx status`
**Purpose:** Show pipeline status including promotions, deployments, quality gates.
**Syntax:** `copado-hx status [--job <jobExecutionId>] [--watch] --json`
**Output:** JSON with current pipeline state or specific job status.

### `copado-hx test list`
**Purpose:** List available CRT test suites and jobs.
**Syntax:** `copado-hx test list --json`
**Output:** JSON array of test jobs with `jobId`, `name`, `testCount`.

### `copado-hx test run`
**Purpose:** Trigger a CRT test suite or job execution.
**Syntax:** `copado-hx test run --suite <suite-id> [--watch] --json`
**Note:** `--suite` is a convenience alias for `--job`. In the CRT API, both suites and individual tests are addressed by a `jobId`.
**Output:** JSON with `{ executionId, status, projectId, jobId }`
**Poll for results:** Use `copado-hx test status --execution <id> --watch`

### `copado-hx test status`
**Purpose:** Poll the status of a running test execution.
**Syntax:** `copado-hx test status --execution <exec-id> [--watch] --json`
**Output:** JSON with `{ executionId, status, duration }`
**Terminal statuses:** `Succeeded`, `Failed`

### `copado-hx test results`
**Purpose:** Retrieve detailed test results for a completed execution.
**Syntax:** `copado-hx test results --execution <exec-id> --json`
**Output:** JSON with `{ totalTests, passed, failed, skipped, passRate, failures[], testResult }`

### `copado-hx ai ask`
**Purpose:** Send a prompt to one of the 5 Copado AI specialist agents.
**Syntax:** `copado-hx ai ask --agent <plan|build|test|release|operate> "<prompt>" [--us <US-ID>] --json`
**Output:** JSON with `{ content, agent, messageId }`

### `copado-hx ai chat`
**Purpose:** Open an interactive multi-turn chat session with an AI agent.
**Syntax:** `copado-hx ai chat --agent <id> [--us <US-ID>]`
**Output:** Interactive REPL — not suitable for automated agent use. Prefer `ai ask` for automation.

### `copado-hx ai triage`
**Purpose:** AI-powered test failure analysis. Fetches test results and asks the Release Agent to diagnose failures.
**Syntax:** `copado-hx ai triage --execution <exec-id> --json`
**Output:** JSON with `{ failures[], ai_analysis }`
**When to use:** After `test results` shows failures, to get automated root cause analysis.

---

## Workflow Playbooks

### Playbook: Full Story Delivery (Commit → UAT → Test → PROD)

Use this when the developer says: "ship my user story", "promote to prod", "deploy US-1234 end to end", or similar.

**Steps:**
1. Verify auth: `copado-hx auth status --json`
2. Set context: `copado-hx story set --id <us-id>`
3. Ask Build Agent for commit guidance: `copado-hx ai ask --agent build "What metadata should I commit for <us-id>?" --json`
4. Commit: `copado-hx commit --message "<generated message>" --json`
5. Promote + validate to UAT: `copado-hx promote --env UAT --validate --watch --json`
6. Run CRT smoke tests: `copado-hx test run --suite <smoke-suite-id> --watch --json`
   *(Retrieve suite ID from `copado-hx test list --json` first)*
7. Check test results: `copado-hx test results --execution <id> --json`
8. **STOP. Ask the human:** "Tests passed/failed. Here are the results: [summary]. Shall I proceed to deploy to PROD?"
9. Only on **explicit human approval**: `copado-hx deploy --env PROD --watch --json`
10. Generate release notes: `copado-hx ai ask --agent release "Generate release notes for <us-id>" --json`

### Playbook: Investigate a Failed Deployment

Use this when the developer says: "why did my deployment fail?", "fix my pipeline error".

**Steps:**
1. `copado-hx status --json` → retrieve the failed job execution ID
2. `copado-hx ai ask --agent release "Analyze the job execution error for <jobExecutionId>" --json`
3. Present the root cause and suggested fix to the developer.
4. If a code fix is needed: `copado-hx ai ask --agent build "Fix the issue: <error summary>" --json`

### Playbook: Generate and Run a Test

Use this when the developer says: "write a test for my class", "test this feature".

**Steps:**
1. `copado-hx ai ask --agent test "Generate a CRT QWord test script for <class/feature>" --json`
2. Present the generated script to the developer for review.
3. **STOP. Ask the human:** "Here is the generated test script. Shall I trigger this test suite?"
4. On approval: `copado-hx test run --suite <id> --watch --json`
   *(Retrieve suite ID from `copado-hx test list --json` first)*
5. `copado-hx test results --execution <id> --json`
6. If failures exist: `copado-hx ai triage --execution <id> --json`

### Playbook: AI-Powered Test Triage

Use this when test results show failures.

**Steps:**
1. `copado-hx test results --execution <id> --json` → check for failures
2. If failures > 0: `copado-hx ai triage --execution <id> --json`
3. Present the AI analysis to the developer with the recommended fix.

---

## Guardrails — What Agents Must Never Do

🚫 **Never deploy to a PROD or production environment without explicit human confirmation.** Always pause and ask: "I'm about to deploy to PROD. Please confirm."

🚫 **Never fabricate or guess IDs** (user story IDs, pipeline IDs, environment names, suite IDs). Always retrieve them from the CLI first using `story list`, `test list`, or `status`.

🚫 **Never run `copado-hx deploy` immediately after `copado-hx promote`** without checking test results and receiving human approval.

🚫 **Never store or log API tokens** in any output, file, or message.

🚫 **Never chain more than 3 destructive actions** (commit, promote, deploy) without a human checkpoint between each stage.

⚠️ **Always surface test failures to the human** before proceeding to the next pipeline stage. Do not auto-retry failed tests.

⚠️ **Always use `--json` flag** when parsing command output programmatically.

---

## Output Parsing Guide

All `copado-hx` commands support `--json` for structured output. **Always use `--json` when parsing output programmatically.**

| Field | Meaning | Agent Action |
|---|---|---|
| `status: "Completed Successfully"` | Action succeeded | Proceed to next step |
| `status: "Completed with Errors"` | Partial failure | Stop, surface errors to human |
| `status: "In Progress"` | Still running | Poll again with `--watch` flag |
| `status: "Failed"` | Hard failure | Stop, invoke Release Agent for analysis |
| `testResult: "Succeeded"` | All tests passed | Safe to proceed to next stage |
| `testResult: "Failed"` | Tests failed | Stop, run `ai triage`, surface failures |

---

## Agent Persona Routing

When the developer's request maps to a DevOps lifecycle stage, route to the appropriate Copado AI agent using `copado-hx ai ask --agent <id>`:

| Developer Says | Route to Agent |
|---|---|
| "Write a user story", "plan this feature", "check for conflicts" | `plan` |
| "Write the code", "generate Apex", "review my class", "fix this bug" | `build` |
| "Write a test", "generate test script", "improve coverage" | `test` |
| "Deploy this", "promote to UAT", "why did it fail?", "release notes" | `release` |
| "Write docs", "create training material", "change management plan" | `operate` |

---

## Error Recovery

If any command fails:
1. Check `copado-hx auth status --json` — authentication may have expired.
2. Read the error message — copado-hx surfaces Copado API error details, not raw HTTP errors.
3. For deployment/promotion failures: `copado-hx ai ask --agent release "Analyze error: <error message>"`
4. For test failures: `copado-hx ai triage --execution <id>`
5. Never retry a failed deployment automatically — always ask the human first.
