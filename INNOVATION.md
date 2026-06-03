# Innovation Statement — copado-hx

---

copado-hx redefines how developers interact with Copado by introducing a guided, headless DevOps experience.

Unlike traditional UI-driven workflows, it combines:
- Workflow orchestration through CLI
- AI-assisted decision-making
- Non-blocking execution
- Intelligent recommendations


At its core, copado-hx is not just a CLI — it is a guided DevOps engine.

The following innovations demonstrate how copado-hx transforms Copado into a developer-first DevOps platform.


## 1. SKILL.md — Agentic Orchestrator (Track B)

A machine-readable instruction file that teaches any AI coding agent (Cursor, Claude, Agentforce) how to use `copado-hx` autonomously. Includes:
- **Workflow playbooks** — Step-by-step recipes for commit-to-deploy
- **Safety guardrails** — Never deploy to PROD without human approval
- **Agent persona routing** — Which Copado AI agent to invoke based on intent
- **Output parsing guide** — How to interpret CLI output for decision-making

**Why it's innovative:** Transforms a CLI tool into an AI-native DevOps platform. Any AI agent with SKILL.md can manage the entire Salesforce release lifecycle autonomously.

---

## 2. AI-Powered Failure Triage

`copado-hx ai triage` automatically pipes CRT test failure details to Copado's specialist AI agents. Instead of developers manually reading test logs (~10 minutes), the AI returns root cause analysis, suggested fixes, and risk assessment in ~10 seconds.

**Why it's innovative:** Closes the loop between testing and fixing — the AI doesn't just report failures, it tells you *why* they failed and *how* to fix them.

---
## 3. Deployment Confidence Score

After CRT test execution, `copado-hx test results` computes an automated **Deployment Confidence Score** (0-100) that synthesizes test pass rate, failure severity, and coverage into a single go/no-go number.

```
  Deployment Confidence Score
  Score: ==================== 85/100
  CRT Tests: 17/20 passed (85%)
  Risk Level: Low
  Recommendation: SAFE TO DEPLOY
```

**Why it's innovative:** Converts subjective deployment decisions into a quantifiable, data-driven confidence score.

---
## 4. Smart Commit with Interactive Metadata Discovery

The commit command implements a three-tier fallback:
1. **Auto-detect** — Queries `copado__User_Story_Metadata__c` for linked components
2. **Interactive picker** — Falls back to querying the org's metadata via Tooling API, presenting numbered lists for selection with add/remove capability
3. **Explicit file** — `--changes file.json` for scripted/CI use

**Why it's innovative:** Solves the "first commit" problem where no metadata records exist yet. The interactive picker queries real org metadata — not a static list — making it a genuine discovery tool.

---


