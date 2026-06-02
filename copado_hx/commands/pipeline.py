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
from rich.prompt import Confirm, Prompt

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
from copado_hx.utils.polling import poll_until_done, SUCCESS_STATUSES, FAILURE_STATUSES

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
# Commit — interactive metadata picker
# ---------------------------------------------------------------------------

_COMMON_TYPES = [
    "ApexClass",
    "ApexTrigger",
    "LightningComponentBundle",
    "AuraDefinitionBundle",
    "Flow",
    "CustomObject",
    "CustomLabel",
    "ApexPage",
    "ApexComponent",
    "StaticResource",
    "PermissionSet",
]


def _interactive_metadata_picker() -> list[dict]:
    """Interactive component selector — query org metadata and let user pick."""
    from rich.table import Table
    from rich import box

    selected: list[dict] = []

    print_warning("No metadata found on this User Story. Let's select components to commit.")
    console.print()

    while True:
        # ── Step 1: pick metadata type ──
        table = Table(title="Metadata Types", box=box.SIMPLE, show_lines=False)
        table.add_column("#", style="bold cyan", width=4)
        table.add_column("Type")
        for i, t in enumerate(_COMMON_TYPES, 1):
            table.add_row(str(i), t)
        console.print(table)
        console.print("[dim]Or type a custom metadata type name.[/dim]")

        type_input = Prompt.ask(
            "[bold]Select type[/bold]",
            default="",
        ).strip()
        if not type_input:
            break

        # Resolve to type name
        try:
            idx = int(type_input) - 1
            if 0 <= idx < len(_COMMON_TYPES):
                meta_type = _COMMON_TYPES[idx]
            else:
                print_error(f"Invalid selection: {type_input}")
                continue
        except ValueError:
            meta_type = type_input  # custom type name

        # ── Step 2: query org for components of this type ──
        console.print(f"[dim]Querying org for {meta_type} components...[/dim]")
        components = cicd.list_org_metadata(meta_type)

        if components:
            comp_table = Table(title=f"{meta_type} ({len(components)} found)", box=box.SIMPLE)
            comp_table.add_column("#", style="bold cyan", width=4)
            comp_table.add_column("Name")
            for i, name in enumerate(components, 1):
                comp_table.add_row(str(i), name)
            console.print(comp_table)

            pick = Prompt.ask(
                "[bold]Select components (comma-separated, e.g. 1,3,5)[/bold]",
                default="",
            ).strip()
            if pick:
                for p in pick.split(","):
                    p = p.strip()
                    try:
                        ci = int(p) - 1
                        if 0 <= ci < len(components):
                            entry = {"a": "Add", "t": meta_type, "n": components[ci]}
                            if entry not in selected:
                                selected.append(entry)
                                console.print(f"  [green]✓[/green] {meta_type}/{components[ci]}")
                    except ValueError:
                        pass
        else:
            # Tooling API didn't return results — let user type names manually
            console.print(f"[yellow]Could not query {meta_type} from org. Enter names manually.[/yellow]")
            names_input = Prompt.ask(
                f"[bold]Component names (comma-separated)[/bold]",
                default="",
            ).strip()
            if names_input:
                for n in names_input.split(","):
                    n = n.strip()
                    if n:
                        entry = {"a": "Add", "t": meta_type, "n": n}
                        if entry not in selected:
                            selected.append(entry)
                            console.print(f"  [green]✓[/green] {meta_type}/{n}")

        console.print()
        if selected:
            # Show current selections
            console.print(f"[bold]Selected ({len(selected)}):[/bold]")
            for i, s in enumerate(selected, 1):
                console.print(f"  {i}. {s['t']}/{s['n']}")

            # Allow removal
            remove_input = Prompt.ask(
                "[bold]Remove any? (enter #, or press Enter to skip)[/bold]",
                default="",
            ).strip()
            if remove_input:
                for r in remove_input.split(","):
                    r = r.strip()
                    try:
                        ri = int(r) - 1
                        if 0 <= ri < len(selected):
                            removed = selected.pop(ri)
                            console.print(f"  [red]✗[/red] Removed {removed['t']}/{removed['n']}")
                    except ValueError:
                        pass

            if not Confirm.ask("[bold]Add more components?[/bold]", default=False):
                break
        else:
            console.print("[dim]No components selected yet. Try again.[/dim]")

    # ── Summary ──
    while selected:
        console.print()
        summary = Table(title="Components to Commit", box=box.ROUNDED)
        summary.add_column("#", style="dim", width=4)
        summary.add_column("Type", style="cyan")
        summary.add_column("Name", style="bold")
        summary.add_column("Action")
        for i, s in enumerate(selected, 1):
            summary.add_row(str(i), s["t"], s["n"], s["a"])
        console.print(summary)
        console.print()

        action = Prompt.ask(
            "[bold]Proceed (p), remove entry (r), or cancel (c)?[/bold]",
            default="p",
        ).strip().lower()

        if action == "p":
            break
        elif action == "c":
            return []
        elif action == "r":
            rm = Prompt.ask("[bold]Enter # to remove[/bold]", default="").strip()
            for r in rm.split(","):
                r = r.strip()
                try:
                    ri = int(r) - 1
                    if 0 <= ri < len(selected):
                        removed = selected.pop(ri)
                        console.print(f"  [red]✗[/red] Removed {removed['t']}/{removed['n']}")
                except ValueError:
                    pass

    return selected


# ---------------------------------------------------------------------------
# Commit command
# ---------------------------------------------------------------------------

@pipeline_app.command("commit")
def commit_cmd(
    message: str = typer.Option(..., "--message", "-m", help="Commit message"),
    us: Optional[str] = typer.Option(None, "--us", help="User story ID (defaults to current context)"),
    changes_file: Optional[str] = typer.Option(None, "--changes", help="JSON file with changes array (auto-detected if omitted)"),
    watch: bool = typer.Option(True, "--watch/--no-watch", "-w", help="Poll until completion (default: on)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Commit metadata changes from the current user story to Git."""
    story_id = us or _require_story()

    # Load changes from file if provided
    changes = None
    if changes_file:
        import json
        try:
            with open(changes_file) as f:
                changes = json.load(f)
            print_info(f"Loaded {len(changes)} components from [bold]{changes_file}[/bold]")
        except Exception as exc:
            print_error(f"Failed to load changes file: {exc}")
            raise typer.Exit(1)
    else:
        # Auto-detect: show what we found
        if not get_settings().mock_mode:
            try:
                sf_id = cicd._resolve_story_sf_id(story_id)
                changes = cicd.list_story_metadata(sf_id)
                if changes:
                    types_summary = {}
                    for c in changes:
                        t = c.get("t", "Unknown")
                        types_summary[t] = types_summary.get(t, 0) + 1
                    parts = [f"{v} {k}" for k, v in types_summary.items()]
                    print_info(f"Auto-detected {len(changes)} components: {', '.join(parts)}")
                else:
                    # No existing metadata — launch interactive picker
                    changes = _interactive_metadata_picker()
                    if not changes:
                        print_info("No components selected. Commit cancelled.")
                        raise typer.Exit(0)
            except typer.Exit:
                raise
            except Exception:
                pass  # Let cicd.commit() handle the error

    print_info(f"Committing for [bold]{story_id}[/bold]: {message}")

    try:
        result = cicd.commit(message=message, story_id=story_id, changes=changes)
        status = result.get("status", "Unknown")
        job_id = result.get("jobExecutionId", "")

        print_success(f"Commit triggered — Job: [bold]{job_id}[/bold]")
        smart_output(result, json_mode=json_output, title="Commit Triggered")
        record_action("commit", last_story=story_id, last_job_id=job_id)

        if watch and job_id:
            print_info("Polling for completion... (Ctrl+C to exit this view)")
            final = poll_until_done(
                fetch_fn=lambda: cicd.get_job_status(job_id),
                status_key="status",
                watch=True,
                label=f"Committing {story_id}",
            )
            # If user exited the polling view, don't process further
            if not final or final.get("_poll_interrupted"):
                return

            final_status = final.get("status", "")
            if final_status in FAILURE_STATUSES:
                print_error(f"Commit failed: {final.get('error', final_status)}")
                smart_output(final, json_mode=json_output, title="Commit Failed")
                raise typer.Exit(1)
            elif final_status not in SUCCESS_STATUSES:
                print_warning(f"Commit ended with status: {final_status}")
                smart_output(final, json_mode=json_output, title="Commit Result")
                return

            print_success("Commit succeeded!")
            smart_output(final, json_mode=json_output, title="Commit Result")

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
    env: str = typer.Option("", "--env", "-e", help="Target environment (e.g. UAT, SIT, PROD)"),
    us: Optional[str] = typer.Option(None, "--us", help="User story ID (defaults to current context)"),
    validate: bool = typer.Option(False, "--validate", help="Run validation only (no merge, no deploy)"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until completion"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Promote or validate a user story."""
    story_id = us or _require_story()

    if validate:
        # Validate — always auto-poll (validation is meaningless without result)
        print_info(f"Validating [bold]{story_id}[/bold]...")
        try:
            result = cicd.validate(story_id=story_id)
            job_id = result.get("jobExecutionId", "")
            print_success(f"Validation triggered — Job: [bold]{job_id}[/bold]")
            smart_output(result, json_mode=json_output, title="Validation Triggered")
            record_action("validate", last_story=story_id, last_job_id=job_id,
                          last_promotion_id=result.get("promotionId", ""))
            if not json_output:
                print_suggestions(after_action="validate")

            if job_id:
                print_info("Waiting for validation to complete... (Ctrl+C to exit this view)")
                final = poll_until_done(
                    fetch_fn=lambda: cicd.get_job_status(job_id),
                    status_key="status",
                    watch=True,
                    label=f"Validating {story_id}",
                )
                # If user exited the polling view, don't process further
                if not final or final.get("_poll_interrupted"):
                    return
                smart_output(final, json_mode=json_output, title="Validation Result")
                from copado_hx.utils.polling import SUCCESS_STATUSES, FAILURE_STATUSES
                final_status = final.get("status", "")
                if final_status in SUCCESS_STATUSES:
                    print_success("Validation succeeded!")
                elif final_status in FAILURE_STATUSES:
                    print_error(f"Validation failed: {final.get('error', final_status)}")
        except typer.Exit:
            raise
        except Exception as e:
            print_error(f"Validation failed: {e}")
            raise typer.Exit(1)
    else:
        # Promote (Git merge) — POST /actions/promote
        if not env:
            print_error("Target environment required for promote. Use --env <ENV>.")
            raise typer.Exit(1)
        print_info(f"Promoting [bold]{story_id}[/bold] → [bold]{env}[/bold]...")
        try:
            result = cicd.promote(story_id=story_id, environment=env)
            job_id = result.get("jobExecutionId", "")
            print_success(f"Promote triggered — Job: [bold]{job_id}[/bold]")
            smart_output(result, json_mode=json_output, title="Promote Triggered")
            record_action("promote", last_story=story_id, last_env=env, last_job_id=job_id,
                          last_promotion_id=result.get("promotionId", ""))
            if not json_output:
                print_suggestions(after_action="promote")

            if watch and job_id:
                print_info("Polling for completion... (Ctrl+C to exit this view)")
                final = poll_until_done(
                    fetch_fn=lambda: cicd.get_job_status(job_id),
                    status_key="status",
                    watch=True,
                    label=f"Promoting {story_id} → {env}",
                )
                # If user exited the polling view, don't process further
                if not final or final.get("_poll_interrupted"):
                    return
                smart_output(final, json_mode=json_output, title="Promote Result")
        except typer.Exit:
            raise
        except Exception as e:
            print_error(f"Promote failed: {e}")
            raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

@pipeline_app.command("deploy")
def deploy_cmd(
    promotion: str = typer.Option(..., "--promotion", "-p", help="Promotion ID to deploy"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until deployment completes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Execute a deployment for a promoted user story."""
    if not yes:
        print_warning(f"You are about to deploy promotion [bold]{promotion}[/bold].")
        confirmed = Confirm.ask("Are you sure you want to proceed?")
        if not confirmed:
            print_info("Deployment cancelled.")
            raise typer.Exit(0)

    print_info(f"Deploying promotion [bold]{promotion}[/bold]...")

    try:
        result = cicd.deploy(promotion_id=promotion)
        job_id = result.get("jobExecutionId", "")
        print_success(f"Deploy triggered — Job: [bold]{job_id}[/bold]")
        smart_output(result, json_mode=json_output, title="Deploy Triggered")
        record_action("deploy", last_job_id=job_id)
        if not json_output:
            print_suggestions(after_action="deploy")

        if watch and job_id:
            print_info("Polling for completion... (Ctrl+C to exit this view)")
            final = poll_until_done(
                fetch_fn=lambda: cicd.get_job_status(job_id),
                status_key="status",
                watch=True,
                label=f"Deploying {promotion}",
            )
            # If user exited the polling view, don't process further
            if not final or final.get("_poll_interrupted"):
                return
            smart_output(final, json_mode=json_output, title="Deploy Result")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Deployment failed: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Merge and Deploy
# ---------------------------------------------------------------------------

@pipeline_app.command("merge-deploy")
def merge_deploy_cmd(
    us: Optional[str] = typer.Option(None, "--us", help="User story ID (defaults to current context)"),
    env: str = typer.Option(..., "--env", "-e", help="Target environment"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Merge and deploy — promotes (Git merge) then deploys to the target environment."""
    story_id = us or _require_story()
    print_info(f"Merge and Deploy: [bold]{story_id}[/bold] → [bold]{env}[/bold]")

    try:
        # Step 1: Promote (Git merge)
        print_info("Step 1/2: Promoting (Git merge)...")
        promo_result = cicd.promote(story_id=story_id, environment=env)
        promo_job_id = promo_result.get("jobExecutionId", "")
        promo_id = promo_result.get("promotionId", "")
        print_success(f"Promote triggered — Job: [bold]{promo_job_id}[/bold]")
        smart_output(promo_result, json_mode=json_output, title="Promote Triggered")

        if promo_job_id:
            print_info("Polling for promotion... (Ctrl+C to exit this view)")
            promo_final = poll_until_done(
                fetch_fn=lambda: cicd.get_job_status(promo_job_id),
                status_key="status",
                watch=True,
                label=f"Promoting {story_id} → {env}",
            )
            # If user exited the polling view, don't process further
            if not promo_final or promo_final.get("_poll_interrupted"):
                return
            smart_output(promo_final, json_mode=json_output, title="Promote Result")
            from copado_hx.utils.polling import SUCCESS_STATUSES, FAILURE_STATUSES
            if promo_final.get("status", "") in FAILURE_STATUSES:
                print_error(f"Promote failed: {promo_final.get('error', promo_final.get('status'))}")
                raise typer.Exit(1)

        # Step 2: Deploy
        if not promo_id:
            print_error("No promotion ID returned from promote step.")
            raise typer.Exit(1)

        print_info("Step 2/2: Deploying...")
        deploy_result = cicd.deploy(promotion_id=promo_id)
        deploy_job_id = deploy_result.get("jobExecutionId", "")
        print_success(f"Deploy triggered — Job: [bold]{deploy_job_id}[/bold]")
        smart_output(deploy_result, json_mode=json_output, title="Deploy Triggered")

        if deploy_job_id:
            print_info("Polling for deployment... (Ctrl+C to exit this view)")
            deploy_final = poll_until_done(
                fetch_fn=lambda: cicd.get_job_status(deploy_job_id),
                status_key="status",
                watch=True,
                label=f"Deploying to {env}",
            )
            # If user exited the polling view, don't process further
            if not deploy_final or deploy_final.get("_poll_interrupted"):
                return
            smart_output(deploy_final, json_mode=json_output, title="Deploy Result")

        record_action("merge_deploy", last_story=story_id, last_env=env,
                      last_promotion_id=promo_id, last_job_id=deploy_job_id)
        if not json_output:
            print_suggestions(after_action="merge_deploy")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Merge and Deploy failed: {e}")
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
                print_info(f"Watching job [bold]{job}[/bold]... (Ctrl+C to exit this view)")
                result = poll_until_done(
                    fetch_fn=lambda: cicd.get_job_status(job),
                    status_key="status",
                    watch=True,
                    label=f"Job {job}",
                )
                # If user exited the polling view, don't process further
                if not result or result.get("_poll_interrupted"):
                    return
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
