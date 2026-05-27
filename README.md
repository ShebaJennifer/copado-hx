# copado-hx — The Headless Developer CLI for Copado DevOps

> **Manage your entire Salesforce release lifecycle from the terminal. No browser tab required.**

`copado-hx` is an open-source, unified command-line interface that wraps the entire Copado API surface — **CI/CD**, **Robotic Testing (CRT)**, and **AI Agents** — into a single, ergonomic developer tool.

Built for the **CopadoCON Bangalore 2026 Hackathon** (Track A + Track B).

---

## Why copado-hx?

| Before (Browser-based) | After (copado-hx) |
|---|---|
| Open Copado UI → navigate to user story → click commit | `copado-hx commit -m "feat: lead scoring"` |
| Switch tabs → find pipeline → click promote → wait | `copado-hx promote --env UAT --validate --watch` |
| Open CRT → find suite → click run → wait → download results | `copado-hx test run --suite <id> --watch` |
| Switch to AI chat → ask question → copy response | `copado-hx ai ask --agent build "Review my Apex code"` |

**Zero context-switching. Full DevOps lifecycle. Any AI agent can drive it.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      copado-hx CLI                          │
│  auth │ story │ commit │ promote │ deploy │ test │ ai       │
├─────────────────────────────────────────────────────────────┤
│                    API Client Layer                          │
│         CI/CD Client │ CRT Client │ AI Platform Client      │
├─────────────────────────────────────────────────────────────┤
│                    Copado API Surface                        │
│    Agentia Pro    │  Agentia Testing  │  Agentia AI Hub     │
│   (CI/CD REST)    │   (CRT Open API)  │  (Dialogue API)    │
└─────────────────────────────────────────────────────────────┘
         │                    │                   │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │ Commit  │         │ Run     │         │ 5 AI    │
    │ Promote │         │ Status  │         │ Agents  │
    │ Deploy  │         │ Results │         │ plan    │
    │ Status  │         │         │         │ build   │
    └─────────┘         └─────────┘         │ test    │
                                            │ release │
                                            │ operate │
                                            └─────────┘
```

### Key Design Decisions

- **Python + Typer** — Fastest CLI framework to build, beautiful help text out of the box
- **Rich** — Professional terminal output (tables, panels, spinners, colors)
- **Mock Mode** — Built-in sample data for demos and offline development
- **Modular API Layer** — Each Copado API surface has its own client; commands never call HTTP directly
- **Secure Auth** — Tokens stored in OS keychain via `keyring` (never in plaintext files)
- **Dual Output** — Human-readable by default, `--json` for machine/agent consumption

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/copado-hx.git
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
# Interactive — prompts for all three API tokens
copado-hx auth login

# Or token-based for CI environments
copado-hx auth login --token <your-token> --type cicd
copado-hx auth login --token <your-pak> --type crt
copado-hx auth login --token <your-key> --type ai

# Verify
copado-hx auth status
```

### Configure

Copy the example config and edit:
```bash
cp .copado-hx.json.example .copado-hx.json
```

Edit `.copado-hx.json` with your Copado instance URLs and project IDs. Set `"mock_mode": false` when using real API credentials.

---

## Usage Examples

### User Story Management
```bash
copado-hx story list                                    # List my stories
copado-hx story list --status "In Progress"             # Filter by status
copado-hx story set --id US-1234                        # Set working context
copado-hx story show                                    # Show current story details
```

### CI/CD Pipeline Operations
```bash
copado-hx commit -m "feat: lead scoring logic"          # Commit metadata
copado-hx promote --env UAT --validate --watch          # Validate in UAT
copado-hx deploy --env PROD                             # Deploy (with confirmation)
copado-hx status --watch                                # Live pipeline status
```

### Robotic Testing (CRT)
```bash
copado-hx test list                                     # List test suites
copado-hx test run --suite <suite-id> --watch           # Run and poll
copado-hx test status --execution <id> --watch          # Check status
copado-hx test results --execution <id>                 # View results + confidence score
```

### AI Agents
```bash
copado-hx ai ask --agent build "Generate Apex for lead scoring"
copado-hx ai ask --agent test "Generate CRT test script for LeadScoring"
copado-hx ai ask --agent release "Generate release notes for US-1234"
copado-hx ai chat --agent build                         # Interactive session
copado-hx ai triage --execution <id>                    # AI failure analysis
```

---

## The Full Demo Flow

A developer completes the entire release lifecycle without opening a browser:

```bash
copado-hx auth login                                          # Authenticate
copado-hx story set --id US-1234                              # Set context
copado-hx ai ask --agent build "What should I commit?"        # AI-guided scope
copado-hx commit -m "feat: lead scoring"                      # Commit
copado-hx promote --env UAT --validate --watch                # Promote + validate
copado-hx test run --suite <id> --watch                       # Run CRT tests
copado-hx test results --execution <id>                       # Results + Confidence Score
copado-hx deploy --env PROD                                   # Deploy (human approval)
copado-hx ai ask --agent release "Generate release notes"     # Release notes
```

---

## Innovation Features

### Deployment Confidence Score
After test execution, `copado-hx test results` displays an automated **Deployment Confidence Score** (0–100) that combines:
- CRT test pass rate
- Failure severity analysis
- Coverage metrics

This gives release engineers a single go/no-go number before deploying.

### AI-Powered Test Failure Triage
`copado-hx ai triage` automatically pipes CRT test failures to the Copado Release Agent for root cause analysis and fix suggestions — turning test failures into actionable insights in seconds.

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

## Copado API Surfaces Used

| API Surface | Endpoints Used |
|---|---|
| **CI/CD (Agentia Pro)** | `/actions/commit`, `/actions/promote`, `/actions/validate`, `/actions/deploy`, `/user-stories`, `/environments`, `/job-executions` |
| **CRT (Agentia Testing)** | `/pace/v4/projects/.../jobs`, `/pace/v4/.../builds`, `/pace/v4/.../results` |
| **AI Platform (Agentia AI)** | `/dialogues`, `/dialogues/.../messages`, `/organizations/.../workspaces` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| CLI Framework | Python + Typer |
| Terminal UI | Rich (tables, panels, spinners, Markdown) |
| HTTP Client | httpx |
| Auth Storage | keyring (OS keychain) |
| Data Validation | Pydantic |
| Configuration | dotenv + JSON config |

---

## Project Structure

```
copado-hx/
├── copado_hx/
│   ├── main.py              # CLI entry point — all commands wired here
│   ├── auth/
│   │   └── store.py         # Secure token storage (OS keychain)
│   ├── commands/
│   │   ├── auth.py          # auth login / status / logout
│   │   ├── story.py         # story list / show / set / create
│   │   ├── pipeline.py      # commit / promote / deploy / status
│   │   ├── test.py          # test list / run / status / results
│   │   └── ai.py            # ai ask / chat / triage
│   ├── api/
│   │   ├── base.py          # Shared HTTP client with error handling
│   │   ├── cicd.py          # Copado CI/CD API client
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

*"Developers can do everything from the CLI." — The Copado Creed* 🚀
