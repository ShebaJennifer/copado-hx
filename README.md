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
  Commit successful
  status: Committed  |  environment: Dev1-SFP

$ copado-hx promote --us US-0000024 --env INT-SFP
  Promotion triggered
  source: Dev1-SFP  |  destination: INT-SFP

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
| Switch tabs, find pipeline, click promote, wait | `copado-hx promote --env INT-SFP` |
| Open CRT, find suite, click run, wait, download results | `copado-hx test run --job <id> --watch` |
| Switch to AI chat, ask question, copy response | `copado-hx ai ask --agent build "Review my Apex"` |

**Zero context-switching. Full DevOps lifecycle. Any AI agent can drive it.**

---

## Architecture

```
+-------------------------------------------------------------+
|                      copado-hx CLI                          |
|  auth | story | commit | promote | deploy | test | ai | env |
+-------------------------------------------------------------+
|               Dual API Strategy                             |
|   SOQL Reads (stories, envs)  |  REST DML (promote, deploy)|
+-------------------------------------------------------------+
|               Salesforce REST API v62.0                     |
|    Browser OAuth (Authorization Code Grant)                 |
+-------------------------------------------------------------+
|                    Copado Platform                           |
|  User Stories  | Promotions | Environments | Job Executions |
|  CRT Testing   | AI Agents  | Pipelines    | Org Credentials|
+-------------------------------------------------------------+
```

### Key Design Decisions

- **Browser OAuth** — Authorization code flow works on all orgs (no security token needed)
- **Direct REST API** — Creates Copado records directly via Salesforce REST, bypassing webhook limitations
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
```

### CI/CD Pipeline Operations
```bash
copado-hx commit --us US-0000024 -m "feat: lead scoring"   # Commit
copado-hx promote --us US-0000024 --env INT-SFP            # Promote
copado-hx promote --us US-0000024 --env INT-SFP --validate # Validate only
copado-hx deploy --env INT-SFP --yes                       # Deploy
copado-hx status                                           # Pipeline overview
```

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

### Direct REST API Integration

Instead of relying on webhook endpoints, `copado-hx` creates Copado records (Promotions, Promoted User Stories) directly via the Salesforce REST API — making it compatible with any Copado edition and configuration.

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

# 4. Promote to integration
copado-hx promote --us US-0000024 --env INT-SFP

# 5. Run tests
copado-hx test run --job 120649 --watch

# 6. Check confidence score
copado-hx test results --execution <id>

# 7. Deploy to UAT
copado-hx promote --us US-0000024 --env UAT-SFP

# 8. Deploy to production (with safety confirmation)
copado-hx deploy --env Production-SFP
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
| **Commit** | REST DML | Updates user story record via `PATCH` |
| **Promote** | REST DML | Creates `copado__Promotion__c` + `copado__Promoted_User_Story__c` |
| **Deploy** | REST DML | Updates promotion status to trigger deployment |
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
│   │   ├── pipeline.py      # commit / promote / deploy / status
│   │   ├── env.py           # env list
│   │   ├── test.py          # test list / run / status / results
│   │   └── ai.py            # ai ask / chat / triage
│   ├── api/
│   │   ├── base.py          # Shared HTTP client + SalesforceClient
│   │   ├── cicd.py          # Copado CI/CD — SOQL reads + REST DML actions
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
