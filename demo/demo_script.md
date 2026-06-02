# copado-hx Demo Script

> 5-minute recorded demo + 10-minute live demo guide

---

## Opening Statement (30 seconds)

"Every Salesforce developer I know has 15 browser tabs open — Copado, the org, test results, AI chat. Today, we're closing all of them. This is **copado-hx** — the headless developer CLI for Copado DevOps."

---

## Act 1 — Authentication & Context (1 minute)

```bash
# Show the CLI
copado-hx --help

# Authenticate (tokens already stored for demo)
copado-hx auth status

# List user stories
copado-hx story list

# Set working context — like 'git checkout' for Copado
copado-hx story set --id US-1234

# Show story details and metadata scope
copado-hx story show
```

**Talking point:** "One command to see all my stories. One command to set context. No browser, no clicking, no waiting for page loads."

---

## Act 2 — AI-Guided Development (1.5 minutes)

```bash
# Ask the Build Agent what metadata to commit
copado-hx ai ask --agent build "What metadata should I commit for US-1234?"

# Commit — auto-detects components from the User Story, or pick interactively
copado-hx commit --us US-0000024 -m "feat: lead scoring logic"

# Validate before deploying
copado-hx promote --validate --us US-1234 --watch

# Merge and deploy to UAT (promote + deploy in one step)
copado-hx merge-deploy --us US-1234 --env UAT
```

**Talking point:** "The AI agent tells me exactly what to commit. The commit command auto-detects metadata components from the User Story — or if none exist yet, launches an interactive picker that queries the org's metadata via Tooling API. I commit, validate, then merge-and-deploy — all from the terminal. Every action goes through the Copado mcwebhook and polls until complete."

---

## Act 3 — QA Intelligence (1.5 minutes) — THE DIFFERENTIATOR

```bash
# List available test suites
copado-hx test list

# Run the smoke test suite
copado-hx test run --suite job-smoke-001 --watch

# Get results with Deployment Confidence Score
copado-hx test results --execution <exec-id>
```

**Talking point:** "Look at that — not just pass/fail, but a **Deployment Confidence Score**. 91 out of 100. It tells me the risk level is Low and it's Safe to Deploy. This is QA intelligence built right into the CLI."

```bash
# AI-powered failure triage — automatically diagnoses why tests failed
copado-hx ai triage --execution <exec-id>
```

**Talking point:** "One test failed. Instead of manually debugging, I ask the Release Agent to triage. It identifies the root cause — a batch size mismatch — and recommends two specific fixes. This turns a 30-minute investigation into a 10-second command."

---

## Act 4 — Deploy to Production (30 seconds)

```bash
# Merge and deploy to PROD — note the safety confirmation prompt
copado-hx merge-deploy --us US-1234 --env PROD
```

**Talking point:** "Merge-and-deploy runs promote (Git merge) then deploy, each step polling the Copado mcwebhook until completion. copado-hx stops and shows clear errors if any step fails. No accidental deploys."

```bash
# Generate release notes
copado-hx ai ask --agent release "Generate release notes for US-1234"
```

---

## Act 5 — The Agent Demo (Track B) (1 minute)

**Option A: Cursor Demo**
Open Cursor → Show SKILL.md in .cursor/rules/ → Type:

> "My lead scoring feature is ready. Run the tests and if they pass, promote to UAT."

Show the agent reading SKILL.md, executing commands, pausing for approval.

**Option B: JSON Output for Agents**
```bash
# Every command supports --json for machine consumption
copado-hx story list --json
copado-hx test results --execution <exec-id> --json
```

**Talking point:** "Every command outputs JSON for AI agents. Combined with SKILL.md — the agent instruction file — any AI system can drive copado-hx autonomously. The agent knows what commands to run, in what order, and when to stop and ask for human approval."

---

## Closing Statement (30 seconds)

"User story to production. Zero browser tabs. AI-guided commits, automated testing with confidence scores, intelligent failure triage, and agent-ready workflows. This is **copado-hx** — the Copado Headless Developer Experience."

---

## Demo Tips

- **Pre-authenticate** before demo starts (run `copado-hx auth login` beforehand)
- **Pre-set** the story context (`copado-hx story set --id US-1234`)
- **Use mock mode** if APIs are slow — set `"mock_mode": true` in `.copado-hx.json`
- **Record a backup video** in case live demo has issues
- **Keep terminal font large** (16pt+) so judges can read
- **Use a dark terminal theme** — the Rich colors look best on dark backgrounds
- **Practice the full flow 3 times** before the live demo

---

## Key Metrics for Judges

| Metric | Value |
|---|---|
| Copado API surfaces covered | All 3 (CI/CD, CRT, AI) |
| CLI commands | 18+ |
| AI agents integrated | All 5 (plan, build, test, release, operate) |
| Output formats | Human + JSON |
| Innovation features | Deployment Confidence Score, AI Triage |
| Track coverage | A (CLI) + B (SKILL.md) |
| Lines of code | ~2,000+ |
| Setup time | < 2 minutes |
