"""
copado-hx — Headless CLI for Copado DevOps.

The main entry point that registers all command groups:
  auth     — Authentication management
  story    — User story management
  commit   — Commit metadata (shortcut from pipeline)
  promote  — Promote to environment (shortcut from pipeline)
  deploy   — Deploy to environment (shortcut from pipeline)
  status   — Pipeline status
  test     — CRT test execution
  ai       — Copado AI agent interactions

This file is the 'wiring' — it connects all the command modules
into a single CLI app. Think of it like the test suite runner
that knows which test files exist.
"""

from __future__ import annotations

import typer
from rich.console import Console

from copado_hx import __version__
from copado_hx.commands.auth import auth_app
from copado_hx.commands.story import story_app
from copado_hx.commands.pipeline import pipeline_app
from copado_hx.commands.test import test_app
from copado_hx.commands.ai import ai_app
from copado_hx.commands.env import env_app

console = Console()

# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="copado-hx",
    help=(
        "copado-hx — The Headless Developer CLI for Copado DevOps.\n\n"
        "Manage your entire Salesforce release lifecycle from the terminal:\n"
        "user stories, commits, promotions, deployments, tests, and AI agents.\n\n"
        "No browser tab required."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register command groups
app.add_typer(auth_app, name="auth")
app.add_typer(story_app, name="story")
app.add_typer(test_app, name="test")
app.add_typer(ai_app, name="ai")
app.add_typer(env_app, name="env")

# Pipeline commands are registered both as a group and as top-level shortcuts
app.add_typer(pipeline_app, name="pipeline", hidden=True)


# ---------------------------------------------------------------------------
# Top-level shortcuts — so users can type `copado-hx commit` directly
# ---------------------------------------------------------------------------

@app.command("commit")
def commit_shortcut(
    message: str = typer.Option(..., "--message", "-m", help="Commit message"),
    us: str = typer.Option(None, "--us", help="User story ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Commit metadata changes from the current user story to Git."""
    from copado_hx.commands.pipeline import commit_cmd
    commit_cmd(message=message, us=us, json_output=json_output)


@app.command("promote")
def promote_shortcut(
    env: str = typer.Option(..., "--env", "-e", help="Target environment"),
    us: str = typer.Option(None, "--us", help="User story ID"),
    validate: bool = typer.Option(False, "--validate", help="Validation-only deployment"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until done"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Promote a user story to the next environment."""
    from copado_hx.commands.pipeline import promote_cmd
    promote_cmd(env=env, us=us, validate=validate, watch=watch, json_output=json_output)


@app.command("deploy")
def deploy_shortcut(
    env: str = typer.Option(..., "--env", "-e", help="Target environment"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until done"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Execute a deployment to the target environment."""
    from copado_hx.commands.pipeline import deploy_cmd
    deploy_cmd(env=env, watch=watch, yes=yes, json_output=json_output)


@app.command("status")
def status_shortcut(
    job: str = typer.Option(None, "--job", "-j", help="Job execution ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Live-poll"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show pipeline status."""
    from copado_hx.commands.pipeline import status_cmd
    status_cmd(job=job, watch=watch, json_output=json_output)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

@app.command("version")
def version():
    """Show copado-hx version."""
    console.print(f"[bold cyan]copado-hx[/bold cyan] v{__version__}")


# ---------------------------------------------------------------------------
# Demo — one-command showcase of the full lifecycle
# ---------------------------------------------------------------------------

@app.command("demo")
def demo():
    """Run a full lifecycle demo against the live Copado org."""
    import time
    from copado_hx.utils.output import print_success, print_info, print_error, print_panel

    STEP_DELAY = 1.5  # seconds between steps for readability

    def _banner():
        console.print()
        console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
        console.print("[bold cyan]  copado-hx  LIVE DEMO  —  Full DevOps Lifecycle[/bold cyan]")
        console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
        console.print()
        console.print("[dim]Every command hits a real Copado org. No mocks.[/dim]")
        console.print()

    def _step(num: int, title: str, cmd: str):
        console.print()
        console.print(f"[bold yellow]Step {num}[/bold yellow]  [bold]{title}[/bold]")
        console.print(f"[dim]$ {cmd}[/dim]")
        console.print()
        time.sleep(0.5)

    _banner()

    # Step 1 — Auth Status
    _step(1, "Check Authentication", "copado-hx auth status")
    try:
        from copado_hx.commands.auth import status as auth_status_cmd
        auth_status_cmd(json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 2 — List Environments
    _step(2, "List Pipeline Environments", "copado-hx env list")
    try:
        from copado_hx.commands.env import list_envs
        list_envs(json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 3 — List User Stories
    _step(3, "List User Stories", "copado-hx story list")
    try:
        from copado_hx.commands.story import list_stories
        list_stories(status=None, json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 4 — Show Story Detail
    _step(4, "Show Story Detail", "copado-hx story show --id US-0000024")
    try:
        from copado_hx.commands.story import show_story
        show_story(story_id="US-0000024", json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 5 — Commit
    _step(5, "Commit Changes", 'copado-hx commit --us US-0000024 -m "feat: lead scoring logic"')
    try:
        commit_shortcut(message="feat: lead scoring logic", us="US-0000024", json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 6 — Promote to INT-SFP
    _step(6, "Promote to Integration", "copado-hx promote --us US-0000024 --env INT-SFP")
    try:
        promote_shortcut(env="INT-SFP", us="US-0000024", validate=False, watch=False, json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 7 — Validate in UAT
    _step(7, "Validate in UAT", "copado-hx promote --us US-0000024 --env UAT-SFP --validate")
    try:
        promote_shortcut(env="UAT-SFP", us="US-0000024", validate=True, watch=False, json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 8 — List CRT Tests
    _step(8, "List CRT Test Jobs", "copado-hx test list")
    try:
        from copado_hx.commands.test import list_tests
        list_tests(project=None, json_output=False)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Finale
    console.print()
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold green]  DEMO COMPLETE — Full lifecycle from CLI[/bold green]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print()
    console.print("[dim]8 steps. Zero browser tabs. One CLI.[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def app_entry():
    """Entry point called by the `copado-hx` console script."""
    app()


if __name__ == "__main__":
    app_entry()
