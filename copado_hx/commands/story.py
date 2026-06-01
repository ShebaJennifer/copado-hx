"""
copado-hx story — User Story management commands.

Usage:
  copado-hx story list                          List user stories assigned to me
  copado-hx story list --pipeline <id> --status "In Progress"
  copado-hx story show                          Show current user story details
  copado-hx story show --id US-1234
  copado-hx story set --id US-1234              Set working context
  copado-hx story create --title "..." --pipeline <id>
"""

from __future__ import annotations

from typing import Optional

import typer

from copado_hx.api import cicd
from copado_hx.utils.config import get_settings, update_settings
from copado_hx.utils.state import record_action
from copado_hx.utils.suggestions import print_suggestions
from copado_hx.utils.output import (
    smart_output,
    print_success,
    print_error,
    print_info,
    print_panel,
    console,
    make_table,
)

story_app = typer.Typer(help="Manage Copado user stories.")


@story_app.command("list")
def list_stories(
    pipeline: Optional[str] = typer.Option(None, "--pipeline", "-p", help="Filter by pipeline ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List user stories assigned to me."""
    try:
        stories = cicd.list_user_stories(pipeline=pipeline, status=status)
        smart_output(
            stories,
            json_mode=json_output,
            title="User Stories",
            columns=["name", "title", "status", "environment", "last_modified"],
        )
        record_action("story_list", last_status="success")
    except Exception as e:
        record_action("story_list", last_status="failed", last_error=str(e))
        print_error(f"Failed to list stories: {e}")
        raise typer.Exit(1)


@story_app.command("show")
def show_story(
    story_id: Optional[str] = typer.Option(None, "--id", "-i", help="User story ID (defaults to current context)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details for a user story (defaults to the current working story)."""
    sid = story_id or get_settings().current_story_id
    if not sid:
        print_error("No user story specified. Use --id or run [bold]copado-hx story set --id <ID>[/bold] first.")
        raise typer.Exit(1)

    try:
        detail = cicd.get_user_story(sid)
        if json_output:
            smart_output(detail, json_mode=True)
        else:
            # Rich panel for story details
            lines = []
            for key in ["name", "title", "status", "pipeline", "environment", "developer", "feature_branch"]:
                if key in detail:
                    lines.append(f"[bold]{key}:[/bold] {detail[key]}")

            # Metadata scope sub-table
            meta = detail.get("metadata_scope", [])
            if meta:
                lines.append("")
                lines.append("[bold]Metadata Scope:[/bold]")
                for m in meta:
                    lines.append(f"  - {m.get('name', '?')} ({m.get('type', '?')})")

            print_panel(f"User Story — {sid}", "\n".join(lines))
        record_action("story_show", last_status="success")
    except Exception as e:
        record_action("story_show", last_status="failed", last_error=str(e))
        print_error(f"Failed to get story: {e}")
        raise typer.Exit(1)


@story_app.command("set")
def set_story(
    story_id: str = typer.Option(..., "--id", "-i", help="User story ID to set as working context"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Set the active user story context (like 'git checkout' for Copado)."""
    update_settings(current_story_id=story_id)
    record_action("story_set", last_story=story_id)
    print_success(f"Working context set to [bold]{story_id}[/bold]")
    print_info("All subsequent commit/promote/deploy commands will use this story.")

    # Show the story details immediately
    try:
        detail = cicd.get_user_story(story_id)
        smart_output(detail, json_mode=json_output, title=f"Active Story — {story_id}")
    except Exception:
        print_info("Story details will be available when connected to the Copado API.")

    if not json_output:
        print_suggestions(after_action="story_set")


@story_app.command("create")
def create_story(
    title: str = typer.Option(..., "--title", "-t", help="User story title"),
    pipeline: Optional[str] = typer.Option(None, "--pipeline", "-p", help="Pipeline ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Create a new user story."""
    settings = get_settings()
    pipe = pipeline or settings.default_pipeline

    if not pipe:
        record_action("story_create", last_status="failed", last_error="Pipeline ID required")
        print_error("Pipeline ID required. Use --pipeline or set default_pipeline in .copado-hx.json")
        raise typer.Exit(1)

    print_info(f"Creating user story: [bold]{title}[/bold] in pipeline [bold]{pipe}[/bold]")
    # In real mode, this would POST to the CI/CD API
    # For now, show confirmation
    if settings.mock_mode:
        result = {
            "id": "a1B5g00000US9999",
            "name": "US-9999",
            "title": title,
            "status": "Draft",
            "pipeline": pipe,
        }
        print_success(f"User story created: [bold]{result['name']}[/bold]")
        smart_output(result, json_mode=json_output, title="New User Story")
        record_action("story_create", last_status="success")
    else:
        record_action("story_create", last_status="failed", last_error="Not yet implemented")
        print_error("Story creation via API — not yet implemented. Use Copado UI for now.")
        raise typer.Exit(1)
