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
# Entry point
# ---------------------------------------------------------------------------

def app_entry():
    """Entry point called by the `copado-hx` console script."""
    app()


if __name__ == "__main__":
    app_entry()
