"""
Contextual suggestion engine for copado-hx.

After every major command, we print a compact "Suggested next steps" block.
The `recommend()` function inspects auth state, current story, and last action
to produce 2-4 relevant follow-up commands.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel

from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings
from copado_hx.utils.state import load_state

console = Console()

# When True, print_suggestions() becomes a no-op (used by interactive workflow)
_suppress = False


# ---------------------------------------------------------------------------
# Suggestion rules
# ---------------------------------------------------------------------------

def recommend(override_action: Optional[str] = None) -> list[dict]:
    """Return a list of suggested next commands based on current state.

    Each item: {"cmd": "copado-hx ...", "why": "short reason"}
    """
    state = load_state()
    settings = get_settings()

    has_sf = get_token("sf_access_token") is not None
    has_cicd = get_token("copado_actions_key") is not None
    has_crt = get_token("crt") is not None
    has_ai = get_token("ai") is not None
    story = settings.current_story_id
    last = override_action or state.get("last_action", "")
    last_env = state.get("last_env", "")
    last_job = state.get("last_job_id", "")
    last_exec = state.get("last_execution_id", "")
    last_crt_job = state.get("last_crt_job_id", "")
    test_failed = state.get("last_test_result") == "Failed"

    suggestions: list[dict] = []

    # ── Not authenticated ──
    if not has_sf and not has_cicd:
        suggestions.append({"cmd": "copado-hx auth login", "why": "Authenticate with Salesforce"})
        suggestions.append({"cmd": "copado-hx auth status", "why": "Check authentication state"})
        return suggestions[:4]

    # ── Action-specific suggestions ──

    if last == "story_set" or last == "story_pick":
        if story:
            suggestions.append({"cmd": f"copado-hx story show --id {story}", "why": "View story details"})
            suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"your message\"", "why": "Commit changes"})
            if has_ai:
                suggestions.append({"cmd": "copado-hx ai ask --agent build \"Suggest metadata for this story\"", "why": "Get AI build guidance"})
            suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP", "why": "Promote to integration"})
        return suggestions[:4]

    if last == "commit":
        if story:
            suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP", "why": "Promote to next environment"})
            suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP --validate", "why": "Validate before promoting"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Check other stories"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent build \"Review my commit\"", "why": "AI code review"})
        return suggestions[:4]

    if last == "promote":
        if last_job:
            suggestions.append({"cmd": f"copado-hx status --job {last_job} --watch", "why": "Watch promotion progress"})
        if has_crt:
            suggestions.append({"cmd": "copado-hx test run --job 120649", "why": "Run tests before deploying"})
        if last_env:
            suggestions.append({"cmd": f"copado-hx deploy --env {last_env} --yes", "why": f"Deploy to {last_env}"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent release \"Generate release notes\"", "why": "AI release notes"})
        return suggestions[:4]

    if last == "deploy":
        if has_crt:
            suggestions.append({"cmd": "copado-hx test run --job 120649", "why": "Run post-deploy tests"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent release \"Generate release notes\"", "why": "AI release notes"})
            suggestions.append({"cmd": "copado-hx ai ask --agent operate \"Create change management plan\"", "why": "AI change management"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Pick next story"})
        return suggestions[:4]

    if last == "test_run":
        if last_exec and last_crt_job:
            suggestions.append({"cmd": f"copado-hx test results --execution {last_exec} --job {last_crt_job}", "why": "View test results + confidence score"})
            suggestions.append({"cmd": f"copado-hx test status --execution {last_exec} --job {last_crt_job} --watch", "why": "Watch test execution"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent test \"Analyze test coverage\"", "why": "AI test analysis"})
        return suggestions[:4]

    if last == "test_results":
        if test_failed and last_exec and last_crt_job:
            if has_ai:
                suggestions.append({"cmd": f"copado-hx ai triage --execution {last_exec} --job {last_crt_job}", "why": "AI failure triage"})
            suggestions.append({"cmd": f"copado-hx test run --job {last_crt_job}", "why": "Re-run tests after fix"})
        else:
            if last_env:
                suggestions.append({"cmd": f"copado-hx deploy --env {last_env} --yes", "why": "Tests passed — deploy"})
            if has_ai:
                suggestions.append({"cmd": "copado-hx ai ask --agent release \"Generate release notes\"", "why": "AI release notes"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Check other stories"})
        return suggestions[:4]

    if last == "ai_triage":
        if last_crt_job:
            suggestions.append({"cmd": f"copado-hx test run --job {last_crt_job}", "why": "Re-run tests after fix"})
        if story:
            suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"fix: address test failures\"", "why": "Commit the fix"})
        suggestions.append({"cmd": "copado-hx ai ask --agent build \"Help fix this issue\"", "why": "AI build assistance"})
        return suggestions[:4]

    if last == "story_list":
        suggestions.append({"cmd": "copado-hx story pick", "why": "Select a story to work on"})
        if story:
            suggestions.append({"cmd": f"copado-hx story show --id {story}", "why": "View current story details"})
            suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"your message\"", "why": "Commit changes"})
        else:
            suggestions.append({"cmd": "copado-hx story set --id <ID>", "why": "Set a story as working context"})
        return suggestions[:4]

    if last == "story_show":
        if story:
            suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"your message\"", "why": "Commit changes"})
            suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP", "why": "Promote to integration"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse other stories"})
        return suggestions[:4]

    if last == "story_create":
        suggestions.append({"cmd": "copado-hx story list", "why": "View all stories"})
        suggestions.append({"cmd": "copado-hx story set --id <ID>", "why": "Set the new story as context"})
        return suggestions[:4]

    if last == "env_list":
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse user stories"})
        suggestions.append({"cmd": "copado-hx story pick", "why": "Select a story to work on"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent plan \"What should I work on?\"", "why": "AI planning advice"})
        return suggestions[:4]

    if last == "auth_login":
        suggestions.append({"cmd": "copado-hx auth status", "why": "Verify connection details"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse user stories"})
        suggestions.append({"cmd": "copado-hx env list", "why": "View pipeline environments"})
        return suggestions[:4]

    if last == "auth_status":
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse user stories"})
        suggestions.append({"cmd": "copado-hx env list", "why": "View pipeline environments"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent plan \"What should I work on?\"", "why": "AI planning advice"})
        return suggestions[:4]

    if last == "ai_ask" or last == "ai_chat":
        if story:
            suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"your message\"", "why": "Commit changes"})
            suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP", "why": "Promote to integration"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse stories"})
        if has_crt:
            suggestions.append({"cmd": "copado-hx test run --job 120649", "why": "Run tests"})
        return suggestions[:4]

    if last == "pipeline_status":
        if story:
            suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"your message\"", "why": "Commit changes"})
            suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP", "why": "Promote to integration"})
        if has_crt:
            suggestions.append({"cmd": "copado-hx test run --job 120649", "why": "Run tests"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse stories"})
        return suggestions[:4]

    # ── Default: no recent action ──
    if not story:
        suggestions.append({"cmd": "copado-hx story pick", "why": "Select a story to work on"})
        suggestions.append({"cmd": "copado-hx story list", "why": "Browse user stories"})
        suggestions.append({"cmd": "copado-hx env list", "why": "View pipeline environments"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent plan \"What should I work on?\"", "why": "AI planning advice"})
    else:
        suggestions.append({"cmd": f"copado-hx commit --us {story} -m \"your message\"", "why": "Commit changes"})
        suggestions.append({"cmd": f"copado-hx promote --us {story} --env INT-SFP", "why": "Promote to next env"})
        if has_ai:
            suggestions.append({"cmd": "copado-hx ai ask --agent build \"Help with this story\"", "why": "AI build guidance"})
        if has_crt:
            suggestions.append({"cmd": "copado-hx test run --job 120649", "why": "Run tests"})

    return suggestions[:4]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_suggestions(suggestions: Optional[list[dict]] = None, after_action: Optional[str] = None) -> None:
    """Print a compact 'Suggested next steps' block."""
    if _suppress:
        return
    items = suggestions or recommend(override_action=after_action)
    if not items:
        return

    lines = []
    for i, s in enumerate(items, 1):
        lines.append(f"  [bold cyan]{i}.[/bold cyan] [bold]{s['cmd']}[/bold]")
        lines.append(f"     [dim]{s['why']}[/dim]")

    console.print()
    console.print(Panel(
        "\n".join(lines),
        title="[bold]Suggested next steps[/bold]",
        border_style="blue",
        expand=False,
    ))
