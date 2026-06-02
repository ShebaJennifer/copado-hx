"""
copado-hx story — User Story management commands.

Usage:
  copado-hx story list                          List user stories assigned to me
  copado-hx story list --pipeline <id> --status "In Progress"
  copado-hx story show                          Show current user story details
  copado-hx story show --id US-1234
  copado-hx story set --id US-1234              Set working context
  copado-hx story create --title "..." --project <id> --release <id> --credential <id> --env <id>
  copado-hx story create                        Interactive mode with auto-discovery pickers
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
    title: Optional[str] = typer.Option(None, "--title", "-t", help="User story title"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    release: Optional[str] = typer.Option(None, "--release", "-r", help="Release ID"),
    credential: Optional[str] = typer.Option(None, "--credential", "-c", help="Org Credential ID"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment ID"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Story status (default: Draft)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Create a new user story.

    Dual mode:
    - Scripting mode: If all required flags provided, create without prompts
    - Interactive mode: If flags missing, launch numbered pickers for auto-discovery
    """
    from rich.prompt import Prompt
    from rich.table import Table
    from rich import box

    # Interactive mode: collect missing values via pickers
    if not title or not project:
        # Title
        if not title:
            title = Prompt.ask("[bold]Story title[/bold]")

        # Project picker (effectively required for usability)
        try:
            projects = cicd.list_projects()
            if projects:
                console.print()
                table = Table(title="Available Projects", box=box.ROUNDED, show_header=True)
                table.add_column("#", style="cyan", width=4)
                table.add_column("ID", style="dim")
                table.add_column("Name", style="green")
                for i, p in enumerate(projects, 1):
                    table.add_row(str(i), p.get("id", ""), p.get("name", ""))
                console.print(table)
                project_choice = Prompt.ask(
                    f"[bold]Select project (1-{len(projects)})[/bold] [dim]or leave blank to skip[/dim]",
                    default="",
                )
                if project_choice.strip():
                    try:
                        idx = int(project_choice) - 1
                        if 0 <= idx < len(projects):
                            project = projects[idx]["id"]
                            console.print(f"[green]Selected project:[/green] {projects[idx]['name']}")
                    except ValueError:
                        pass
                if not project:
                    console.print("[yellow]Warning:[/yellow] Skipping project. Story may not be usable in pipeline.")
            else:
                console.print("[yellow]No projects found. Continuing without project.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Failed to load projects: {e}[/yellow]")

        # Release picker (scoped to selected project)
        if project:
            try:
                releases = cicd.list_releases(project_id=project)
                if releases:
                    console.print()
                    table = Table(title=f"Releases for Project", box=box.ROUNDED, show_header=True)
                    table.add_column("#", style="cyan", width=4)
                    table.add_column("ID", style="dim")
                    table.add_column("Name", style="green")
                    for i, r in enumerate(releases, 1):
                        table.add_row(str(i), r.get("id", ""), r.get("name", ""))
                    console.print(table)
                    release_choice = Prompt.ask(
                        f"[bold]Select release (1-{len(releases)})[/bold] [dim]or leave blank to skip[/dim]",
                        default="",
                    )
                    if release_choice.strip():
                        try:
                            idx = int(release_choice) - 1
                            if 0 <= idx < len(releases):
                                release = releases[idx]["id"]
                                console.print(f"[green]Selected release:[/green] {releases[idx]['name']}")
                        except ValueError:
                            pass
            except Exception as e:
                console.print(f"[yellow]Failed to load releases: {e}[/yellow]")

        # Credential picker (effectively required for usability)
        try:
            credentials = cicd.list_credentials()
            if credentials:
                console.print()
                table = Table(title="Available Org Credentials", box=box.ROUNDED, show_header=True)
                table.add_column("#", style="cyan", width=4)
                table.add_column("ID", style="dim")
                table.add_column("Name", style="green")
                for i, c in enumerate(credentials, 1):
                    table.add_row(str(i), c.get("id", ""), c.get("name", ""))
                console.print(table)
                cred_choice = Prompt.ask(
                    f"[bold]Select credential (1-{len(credentials)})[/bold] [dim]or leave blank to skip[/dim]",
                    default="",
                )
                if cred_choice.strip():
                    try:
                        idx = int(cred_choice) - 1
                        if 0 <= idx < len(credentials):
                            credential = credentials[idx]["id"]
                            console.print(f"[green]Selected credential:[/green] {credentials[idx]['name']}")
                    except ValueError:
                        pass
                if not credential:
                    console.print("[yellow]Warning:[/yellow] Skipping credential. Story may not be valid for pipeline.")
            else:
                console.print("[yellow]No credentials found. Continuing without credential.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Failed to load credentials: {e}[/yellow]")

        # Environment picker (optional)
        try:
            environments = cicd.list_environments()
            if environments:
                console.print()
                table = Table(title="Available Environments", box=box.ROUNDED, show_header=True)
                table.add_column("#", style="cyan", width=4)
                table.add_column("ID", style="dim")
                table.add_column("Name", style="green")
                table.add_column("Platform", style="dim")
                for i, env in enumerate(environments, 1):
                    table.add_row(str(i), env.get("id", ""), env.get("name", ""), env.get("platform", ""))
                console.print(table)
                env_choice = Prompt.ask(
                    f"[bold]Select environment (1-{len(environments)})[/bold] [dim]or leave blank to skip[/dim]",
                    default="",
                )
                if env_choice.strip():
                    try:
                        idx = int(env_choice) - 1
                        if 0 <= idx < len(environments):
                            environment = environments[idx]["id"]
                            console.print(f"[green]Selected environment:[/green] {environments[idx]['name']}")
                    except ValueError:
                        pass
        except Exception as e:
            console.print(f"[yellow]Failed to load environments: {e}[/yellow]")

        # Status picker (optional, default Draft)
        if not status:
            status = Prompt.ask("[bold]Status[/bold]", default="Draft")

    # Scripting mode: use provided flags
    if not status:
        status = "Draft"

    console.print()
    print_info(f"Creating user story: [bold]{title}[/bold]")

    try:
        result = cicd.create_user_story(
            title=title or "",
            project_id=project or "",
            release_id=release or "",
            credential_id=credential or "",
            environment_id=environment or "",
            status=status,
        )
        story_name = result.get("name", result.get("id", ""))
        print_success(f"User story [bold]{story_name}[/bold] created")

        if json_output:
            smart_output(result, json_mode=True)
        else:
            # Rich panel display
            lines = []
            if result.get("name"):
                lines.append(f"[bold]Name:[/bold] {result['name']}")
            if result.get("title"):
                lines.append(f"[bold]Title:[/bold] {result['title']}")
            if result.get("status"):
                lines.append(f"[bold]Status:[/bold] {result['status']}")
            if result.get("record_type"):
                lines.append(f"[bold]Record Type:[/bold] {result['record_type']}")
            if result.get("project"):
                lines.append(f"[bold]Project:[/bold] {result['project']} ({result.get('project_id', '')})")
            if result.get("release"):
                lines.append(f"[bold]Release:[/bold] {result['release']} ({result.get('release_id', '')})")
            if result.get("environment"):
                lines.append(f"[bold]Environment:[/bold] {result['environment']} ({result.get('environment_id', '')})")
            if result.get("credential"):
                lines.append(f"[bold]Credential:[/bold] {result['credential']} ({result.get('credential_id', '')})")
            print_panel(f"New User Story — {story_name}", "\n".join(lines))
            print_info(f"Run [bold]copado-hx story set --id {story_name}[/bold] to set as working context")

        record_action("story_create", last_status="success", last_story=story_name)
    except Exception as e:
        record_action("story_create", last_status="failed", last_error=str(e))
        print_error(f"Failed to create story: {e}")
        raise typer.Exit(1)
