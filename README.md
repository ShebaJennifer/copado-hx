# copado-hx — The Headless Developer CLI for Copado DevOps

> **Manage your entire Salesforce release lifecycle from the terminal. No browser tab required.**

`copado-hx` is an open-source, unified command-line interface that wraps the entire Copado API surface — **CI/CD**, **Robotic Testing (CRT)**, and **AI Agents** — into a single, ergonomic developer tool.

Built for the **CopadoCON Bangalore 2026 Hackathon** (Track A + Track B).

---

## Live Demo — Real Copado Org

Every command below runs against a **live Copado trial org** — no mocks, no fakes.

```
$ copado-hx auth status
  Salesforce CI/CD:       Connected
  Copado Actions API:     Connected
  CRT (Robotic Testing):  Connected

$ copado-hx story list
                              User Stories
  name       | title                             | status      | environment
  US-0000024 | My first Source Format User Story  | In Progress | Dev1-SFP

$ copado-hx commit --us US-0000024 -m "feat: lead scoring"
  Auto-detected 3 components: 2 ApexClass, 1 Flow
  Commit triggered — Job: a1Xhk000002bcDE

$ copado-hx promote --validate --us US-0000024
  Validation triggered — Job: a1Xhk000001abCD

$ copado-hx merge-deploy --us US-0000024 --env INT-SFP
  Step 1/2: Promoting (Git merge)... ✓
  Step 2/2: Deploying... ✓
  Merge and Deploy completed successfully!

$ copado-hx env list
  name           | platform | type
  Dev1-SFP       | SFDX     | Sandbox
  INT-SFP        | SFDX     | Sandbox
  UAT-SFP        | SFDX     | Sandbox
  Production-SFP | SFDX     | Sandbox
```

> **Run `copado-hx demo` to see this full flow live in your terminal.**

---

## Why copado-hx?

| Before (Browser-based) | After (copado-hx) |
|---|---|
| Open Copado UI, navigate to user story, click commit | `copado-hx commit -m "feat: lead scoring"` |
| Switch tabs, validate, promote, deploy — 3 separate steps | `copado-hx merge-deploy --env INT-SFP` |
| Open CRT, find suite, click run, wait, download results | `copado-hx test run --job <id> --watch` |
| Switch to AI chat, ask question, copy response | `copado-hx ai ask --agent build "Review my Apex"` |

**Zero context-switching. Full DevOps lifecycle. Any AI agent can drive it.**

---

## Architecture

```
+-------------------------------------------------------------+
|                      copado-hx CLI                          |
| auth | story | commit | promote | deploy | merge-deploy |   |
| test | ai | env | guide (interactive workflow)               |
+-------------------------------------------------------------+
|               Dual API Strategy                             |
|   SOQL Reads (stories, envs)  |  mcwebhook Actions (CI/CD) |
+-------------------------------------------------------------+
|   Salesforce REST API v62.0   | Copado mcwebhook endpoint  |
|    Browser OAuth (Authorization Code Grant)                 |
+-------------------------------------------------------------+
|                    Copado Platform                           |
|  User Stories  | Promotions | Environments | Job Executions |
|  CRT Testing   | AI Agents  | Pipelines    | Org Credentials|
+-------------------------------------------------------------+
```

### Key Design Decisions

- **Browser OAuth** — Authorization code flow works on all orgs (no security token needed)
- **Copado mcwebhook** — Uses the Copado mcwebhook endpoint with action names (Commit, Promotion, PromotionDeployment) and real `jobExecutionId` polling
- **SOQL-powered reads** — Real-time data with relationship queries (environment names resolved, not raw IDs)
- **Python + Typer** — Fastest CLI framework to build, beautiful help text out of the box
- **Rich** — Professional terminal output (tables, panels, spinners, colors)
- **Secure Auth** — Tokens stored in OS keychain via `keyring` (never in plaintext files)
- **Dual Output** — Human-readable by default, `--json` for machine/agent consumption
- **Mock Mode** — Built-in sample data for demos and offline development

---

## Quick Start

### Prerequisites

- Python 3.10+
- A Copado-enabled Salesforce org
- A Connected App / External Client App with OAuth enabled

### Installation

```bash
# Clone the repository
git clone https://github.com/ShebaJennifer-CRT/copado-hx.git
cd copado-hx

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install copado-hx
pip install -e .
```

### Authenticate

```bash
# Interactive login — opens browser for Salesforce OAuth
copado-hx auth login

# Verify all connections
copado-hx auth status
```

The browser-based OAuth flow:
1. Opens your browser to the Salesforce login page
2. You log in and approve access
3. Copy the redirect URL from the browser and paste it back
4. Token is securely stored in your OS keychain

### Run the Demo

```bash
# One command — full lifecycle demo with real data
copado-hx demo
```

---

## Command Reference

### Authentication
```bash
copado-hx auth login                    # Browser OAuth login
copado-hx auth status                   # Show all connection statuses
copado-hx auth logout                   # Clear stored tokens
```

### User Story Management
```bash
copado-hx story list                    # List user stories (real SOQL)
copado-hx story list --status "Draft"   # Filter by status
copado-hx story show --id US-0000024    # Detailed view
copado-hx story set --id US-0000024     # Set working context
copado-hx story create                  # Interactive mode with auto-discovery pickers
copado-hx story create --title "Feature X" --project <id> --release <id> --env <id>  # Scripting mode
```

**Story Create Dual Mode:**
- **Interactive mode** (default when flags missing): Launches numbered pickers for auto-discovery of projects, releases, credentials, and environments from Salesforce. No need to memorize IDs.
- **Scripting mode** (when flags provided): Create without prompts for automation and AI agents.
- **Project is effectively required** for pipeline usability (strongly prompted in interactive mode, optional in scripting mode).
- **Release is scoped to project** to ensure consistency.

### CI/CD Pipeline Operations
```bash
copado-hx commit --us US-0000024 -m "feat: lead scoring"   # Commit (auto-detects components)
copado-hx commit --us US-0000024 -m "msg" --changes f.json # Commit with explicit component list
copado-hx commit --us US-0000024 -m "msg" --watch          # Commit and poll until done
copado-hx promote --validate --us US-0000024               # Validate only (dry-run)
copado-hx promote --us US-0000024 --env INT-SFP            # Promote (Git merge)
copado-hx deploy --promotion <id> --yes                    # Deploy a promotion
copado-hx merge-deploy --us US-0000024 --env INT-SFP       # Promote + deploy in one step
copado-hx status                                           # Pipeline overview
```

**Commit Smart Detection:**
- **Auto-detect** (default): Queries `copado__User_Story_Metadata__c` for components already linked to the story.
- **Interactive picker** (fallback): If no metadata exists, launches an interactive component selector — queries your org's metadata types via Tooling API and lets you pick components from numbered lists.
- **`--changes file.json`** (override): Provide an explicit JSON array of `{"a": "Add", "t": "ApexClass", "n": "MyClass"}` entries for scripted/CI use.

### Environment Management
```bash
copado-hx env list                      # List all pipeline environments
```

### Robotic Testing (CRT)
```bash
copado-hx test list                     # List test jobs
copado-hx test run --job <id> --watch   # Run and poll
copado-hx test status --execution <id>  # Check status
copado-hx test results --execution <id> # Results + Confidence Score
```

### AI Agents
```bash
copado-hx ai ask --agent build "Generate Apex for lead scoring"
copado-hx ai ask --agent test "Generate CRT test script for LeadScoring"
copado-hx ai ask --agent release "Generate release notes for US-1234"
copado-hx ai chat --agent build         # Interactive session
```

---

## Innovation Features

### Deployment Confidence Score

After test execution, `copado-hx test results` displays an automated **Deployment Confidence Score** (0-100):

```
  Deployment Confidence Score
  Score: ==================== 85/100
  CRT Tests: 17/20 passed (85%)
  Risk Level: Low
  Recommendation: SAFE TO DEPLOY
```

Combines CRT test pass rate + failure severity + coverage metrics into a single go/no-go number.

### AI-Powered Test Failure Triage

`copado-hx ai triage` pipes CRT test failures to Copado AI agents for root cause analysis and fix suggestions — turning test failures into actionable insights in seconds.

### Browser-Based OAuth

Implements the OAuth 2.0 Authorization Code flow with a paste-URL approach — works on any Salesforce org regardless of IP restrictions, security token requirements, or SOAP API settings.

### Copado mcwebhook Integration

`copado-hx` uses the Copado mcwebhook endpoint (`POST /services/apexrest/copado/mcwebhook`) with action names `Commit`, `Promotion`, and `PromotionDeployment`. Each action returns a `jobExecutionId` which is polled via SOQL until completion. The commit payload includes a `changes[]` array of metadata components auto-detected from `copado__User_Story_Metadata__c` or selected interactively.

### Smart Polling & UX

- **Ctrl+C exits the polling view** without cancelling the server-side job — run other commands while it continues.
- **Compact test output** — `test status` and `test results` show clean summary panels instead of raw JSON dumps.
- **AI-powered failure triage** — truncated error messages with actionable summaries.

---

## The Full Demo Flow

A developer completes the entire release lifecycle without opening a browser:

```bash
# 1. Authenticate (browser OAuth — 15 seconds)
copado-hx auth login

# 2. See what's in progress
copado-hx story list

# 3. Commit changes
copado-hx commit --us US-0000024 -m "feat: lead scoring"

# 4. Validate before deploying
copado-hx promote --validate --us US-0000024 --watch

# 5. Merge and deploy to integration (promote + deploy in one step)
copado-hx merge-deploy --us US-0000024 --env INT-SFP

# 6. Run tests
copado-hx test run --job 120649 --watch

# 7. Check confidence score
copado-hx test results --execution <id>

# 8. Merge and deploy to UAT
copado-hx merge-deploy --us US-0000024 --env UAT-SFP
```

---

## Track B — SKILL.md (Agentic Orchestrator)

The repository includes a complete `SKILL.md` at the root — a machine-readable instruction file that teaches any AI coding agent (Cursor, Claude, OpenAI, Agentforce) how to use `copado-hx` autonomously.

SKILL.md includes:
- **Identity** — What the skill does and which systems it connects to
- **Prerequisites** — What must be true before any command runs
- **Commands Reference** — Structured description of every command
- **Workflow Playbooks** — Step-by-step recipes for common DevOps scenarios
- **Guardrails** — Safety rules (e.g., never deploy to PROD without human approval)
- **Output Parsing Guide** — How to interpret CLI output for decision-making
- **Agent Persona Routing** — Which Copado AI agent to invoke based on developer intent

### Using with Cursor
Place `SKILL.md` in `.cursor/rules/` or reference it in your system prompt. The AI agent can then execute full Copado DevOps workflows from natural language instructions.

---

## Copado API Integration

| Operation | Method | Detail |
|---|---|---|
| **Story List** | SOQL Query | `SELECT ... FROM copado__User_Story__c` with relationship fields |
| **Story Detail** | SOQL Query | Environment name resolved via `copado__Environment__r.Name` |
| **Environment List** | SOQL Query | `SELECT ... FROM copado__Environment__c` |
| **Commit** | mcwebhook | action: `Commit` — auto-detect or interactive component selection |
| **Validate** | mcwebhook | action: `Promotion` → `PromotionDeployment` (dryRun: true) |
| **Promote** | mcwebhook | action: `Promotion` → `PromotionDeployment` (dryRun: false) |
| **Deploy** | mcwebhook | action: `PromotionDeployment` on existing promotion |
| **Job Status** | SOQL | `SELECT ... FROM copado__JobExecution__c` — poll until done |
| **Create Story** | Salesforce REST | `POST /sobjects/copado__User_Story__c` |
| **CRT Tests** | CRT Open API | `/pace/v4/projects/.../jobs`, `/builds`, `/results` |
| **AI Agents** | Dialogue API | `/dialogues`, `/messages` |
| **Auth** | OAuth 2.0 | Authorization Code flow (browser-based) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| CLI Framework | Python + Typer |
| Terminal UI | Rich (tables, panels, spinners, Markdown) |
| HTTP Client | httpx |
| Auth Storage | keyring (OS keychain) |
| Auth Flow | OAuth 2.0 Authorization Code (browser-based) |
| Data Validation | Pydantic |
| Configuration | dotenv + JSON config |

---

## Project Structure

```
copado-hx/
├── copado_hx/
│   ├── main.py              # CLI entry point — all commands wired here
│   ├── auth/
│   │   ├── store.py         # Secure token storage (OS keychain)
│   │   └── sf_oauth.py      # Browser OAuth + password flow
│   ├── commands/
│   │   ├── auth.py          # auth login / status / logout
│   │   ├── story.py         # story list / show / set / create
│   │   ├── pipeline.py      # commit / promote / validate / deploy / merge-deploy / status
│   │   ├── env.py           # env list
│   │   ├── test.py          # test list / run / status / results
│   │   └── ai.py            # ai ask / chat / triage
│   ├── api/
│   │   ├── base.py          # Shared HTTP client + SalesforceClient
│   │   ├── cicd.py          # Copado CI/CD — SOQL reads + mcwebhook actions
│   │   ├── crt.py           # CRT Open API client
│   │   ├── ai_platform.py   # Copado AI Dialogue API client
│   │   └── mock_data.py     # Realistic mock responses for all APIs
│   └── utils/
│       ├── config.py        # .copado-hx.json configuration management
│       ├── output.py        # Rich formatting + --json output support
│       └── polling.py       # Async job status polling with spinner
├── SKILL.md                 # Track B — Agent instruction file
├── .copado-hx.json.example  # Example configuration
├── pyproject.toml           # Python packaging and dependencies
├── LICENSE                  # MIT License
└── README.md                # This file
```

---

## License

MIT — see [LICENSE](LICENSE).

---

## Team

Built at **CopadoCON Bangalore 2026 Hackathon**.

---

*"The entire Copado DevOps lifecycle — from commit to deploy — in one CLI. No browser required."*
