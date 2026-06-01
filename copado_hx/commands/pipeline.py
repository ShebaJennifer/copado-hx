"""
copado-hx commit / promote / deploy / status — CI/CD Pipeline commands.

Usage:
  copado-hx commit --message "feat: lead scoring"
  copado-hx promote --env UAT --validate
  copado-hx deploy --env PROD
  copado-hx status
  copado-hx status --watch
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.prompt import Confirm

from copado_hx.api import cicd
from copado_hx.utils.config import get_settings
from copado_hx.utils.state import record_action
from copado_hx.utils.suggestions import print_suggestions
from copado_hx.utils.output import (
    smart_output,
    print_success,
    print_error,
    print_info,
    print_warning,
    print_panel,
    console,
    make_table,
)
from copado_hx.utils.polling import poll_until_done

pipeline_app = typer.Typer(help="CI/CD pipeline operations: commit, promote, deploy, status.")


def _require_story() -> str:
    """Return current story ID or exit with a helpful error."""
    sid = get_settings().current_story_id
    if not sid:
        print_error(
            "No active user story. Run [bold]copado-hx story set --id <ID>[/bold] first."
        )
        raise typer.Exit(1)
    return sid


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

@pipeline_app.command("commit")
def commit_cmd(
    message: str = typer.Option(..., "--message", "-m", help="Commit message"),
    us: Optional[str] = typer.Option(None, "--us", help="User story ID (defaults to current context)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Commit metadata changes from the current user story to Git."""
    story_id = us or _require_story()
    print_info(f"Committing for [bold]{story_id}[/bold]: {message}")

    try:
        result = cicd.commit(message=message, story_id=story_id)
        status = result.get("status", "Unknown")

        if "Error" in status or "Failed" in status:
            print_error(f"Commit failed: {result.get('logs', status)}")
            smart_output(result, json_mode=json_output, title="Commit Failed")
            raise typer.Exit(1)

        print_success(f"Commit successful — {result.get('commitId', 'N/A')}")
        files = result.get("filesCommitted", [])
        if files and not json_output:
            print_info(f"Files committed: {', '.join(files)}")

        smart_output(result, json_mode=json_output, title="Commit Result")
        record_action("commit", last_story=story_id)
        if not json_output:
            print_suggestions(after_action="commit")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Commit failed: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Promote
# ---------------------------------------------------------------------------

@pipeline_app.command("promote")
def promote_cmd(
    env: str = typer.Option(..., "--env", "-e", help="Target environment (e.g. UAT, SIT, PROD)"),
    us: Optional[str] = typer.Option(None, "--us", help="User story ID (defaults to current context)"),
    validate: bool = typer.Option(False, "--validate", help="Run validation-only deployment (no actual deploy)"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until promotion completes"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Promote a user story to the next environment in the pipeline."""
    story_id = us or _require_story()
    action = "Validating" if validate else "Promoting"
    print_info(f"{action} [bold]{story_id}[/bold] to [bold]{env}[/bold]...")

    try:
        result = cicd.promote(
            story_id=story_id,
            environment=env,
            validate_only=validate,
        )
        job_id = result.get("jobExecutionId", "")
        print_success(f"Promotion triggered — Job: [bold]{job_id}[/bold]")
        smart_output(result, json_mode=json_output, title="Promotion Triggered")
        record_action("promote", last_story=story_id, last_env=env, last_job_id=job_id)
        if not json_output:
            print_suggestions(after_action="promote")

        if watch and job_id:
            print_info("Polling for completion...")
            final = poll_until_done(
                fetch_fn=lambda: cicd.get_job_status(job_id),
                status_key="status",
                watch=True,
                label=f"{action} {story_id} → {env}",
            )
            smart_output(final, json_mode=json_output, title="Promotion Result")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Promotion failed: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

@pipeline_app.command("deploy")
def deploy_cmd(
    env: str = typer.Option(..., "--env", "-e", help="Target environment (e.g. PROD)"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until deployment completes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Execute a deployment to the target environment (requires confirmation for PROD)."""
    # Safety gate: always confirm PROD deployments
    is_prod = env.upper() in ("PROD", "PRODUCTION")
    if is_prod and not yes:
        print_warning(f"You are about to deploy to [bold red]{env}[/bold red].")
        confirmed = Confirm.ask("Are you sure you want to proceed?")
        if not confirmed:
            print_info("Deployment cancelled.")
            raise typer.Exit(0)

    print_info(f"Deploying to [bold]{env}[/bold]...")

    try:
        result = cicd.deploy(environment=env)
        job_id = result.get("jobExecutionId", "")
        print_success(f"Deployment triggered — Job: [bold]{job_id}[/bold]")
        smart_output(result, json_mode=json_output, title="Deployment Triggered")
        record_action("deploy", last_env=env, last_job_id=job_id)
        if not json_output:
            print_suggestions(after_action="deploy")

        if watch and job_id:
            print_info("Polling for completion...")
            final = poll_until_done(
                fetch_fn=lambda: cicd.get_job_status(job_id),
                status_key="status",
                watch=True,
                label=f"Deploying to {env}",
            )
            smart_output(final, json_mode=json_output, title="Deployment Result")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Deployment failed: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@pipeline_app.command("status")
def status_cmd(
    job: Optional[str] = typer.Option(None, "--job", "-j", help="Specific job execution ID to check"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Live-poll until completion"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show pipeline status: promotions, deployments, quality gates."""
    if job:
        # Poll a specific job
        try:
            if watch:
                print_info(f"Watching job [bold]{job}[/bold]... (Ctrl+C to stop)")
                result = poll_until_done(
                    fetch_fn=lambda: cicd.get_job_status(job),
                    status_key="status",
                    watch=True,
                    label=f"Job {job}",
                )
            else:
                result = cicd.get_job_status(job)

            smart_output(result, json_mode=json_output, title=f"Job Status — {job}")
            record_action("pipeline_status")
        except Exception as e:
            record_action("pipeline_status")
            print_error(f"Failed to get job status: {e}")
            raise typer.Exit(1)
    else:
        # Show overview: current story context + environments
        settings = get_settings()
        story_id = settings.current_story_id

        overview = {
            "active_story": story_id or "(none — run copado-hx story set)",
            "mock_mode": str(settings.mock_mode),
        }

        if story_id:
            try:
                detail = cicd.get_user_story(story_id)
                overview["story_title"] = detail.get("title", "")
                overview["story_status"] = detail.get("status", "")
                overview["environment"] = detail.get("environment", "")
            except Exception:
                pass

        smart_output(overview, json_mode=json_output, title="Pipeline Status")
        record_action("pipeline_status")

        if not json_output:
            # Show environments
            try:
                envs = cicd.list_environments()
                smart_output(
                    envs,
                    json_mode=False,
                    title="Environments",
                    columns=["name", "type"],
                )
            except Exception:
                pass
