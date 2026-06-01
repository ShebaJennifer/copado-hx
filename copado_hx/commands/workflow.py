"""
copado-hx workflow commands — guided DevOps assistant.

Usage:
  copado-hx next                          Show recommended next actions
  copado-hx next --interactive            Select and execute, then loop
  copado-hx story pick                    Interactive story picker
  copado-hx ship --us <id> --to <env>     Guided end-to-end pipeline
"""

from __future__ import annotations

import time
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Confirm, Prompt

from copado_hx.auth.store import get_token
from copado_hx.utils.config import get_settings, update_settings
from copado_hx.utils.state import load_state, record_action
from copado_hx.utils.suggestions import recommend, print_suggestions
from copado_hx.utils.output import (
    print_success,
    print_error,
    print_info,
    print_warning,
    print_panel,
    console,
    make_table,
)
from rich.table import Table
from rich import box

workflow_app = typer.Typer(help="Guided workflow assistant.")


# ---------------------------------------------------------------------------
# Context display
# ---------------------------------------------------------------------------

def _show_context() -> None:
    """Print current state context block."""
    settings = get_settings()
    state = load_state()

    has_sf = get_token("sf_access_token") is not None
    has_cicd = get_token("copado_actions_key") is not None
    has_crt = get_token("crt") is not None
    has_ai = get_token("ai") is not None
    story = settings.current_story_id
    last = state.get("last_action", "")

    sf_status = "[green]authenticated[/green]" if has_sf else "[red]not configured[/red]"
    cicd_status = "[green]authenticated[/green]" if has_cicd else "[red]not configured[/red]"
    crt_status = "[green]authenticated[/green]" if has_crt else "[red]not configured[/red]"
    ai_status = "[green]configured[/green]" if has_ai else "[yellow]not configured[/yellow]"
    story_status = f"[bold green]{story}[/bold green]" if story else "[yellow]not selected[/yellow]"
    last_status = last.replace("_", " ") if last else "[dim]none[/dim]"

    lines = [
        f"[bold]Salesforce:[/bold]  {sf_status}",
        f"[bold]CI/CD:[/bold]       {cicd_status}",
        f"[bold]CRT:[/bold]         {crt_status}",
        f"[bold]AI:[/bold]          {ai_status}",
        f"[bold]Story:[/bold]       {story_status}",
        f"[bold]Last action:[/bold] {last_status}",
    ]
    print_panel("Current context", "\n".join(lines), style="cyan")


def _show_capabilities() -> None:
    """Print a categorized table of all available actions."""
    settings = get_settings()
    story = settings.current_story_id
    state = load_state()
    last_exec = state.get("last_execution_id", "")
    last_crt_job = state.get("last_crt_job_id", "")

    has_crt = get_token("crt") is not None
    has_ai = get_token("ai") is not None

    table = Table(
        title="Available Actions",
        box=box.ROUNDED,
        show_lines=False,
        title_style="bold cyan",
        expand=False,
    )
    table.add_column("CI/CD", style="green", min_width=30)
    table.add_column("Testing", style="yellow", min_width=30)
    table.add_column("AI Agents", style="magenta", min_width=30)

    # Build rows — pair up CI/CD, Test, and AI actions
    cicd_cmds = [
        "story list",
        "story pick",
        f"story show --id {story}" if story else "story show",
        f"commit --us {story} -m \"msg\"" if story else "commit -m \"msg\"",
        f"promote --env INT-SFP" + (f" --us {story}" if story else ""),
        "deploy --env UAT-SFP",
        "status --watch",
        "env list",
    ]

    test_cmds: list[str] = []
    if has_crt:
        test_cmds.append("test list")
        test_cmds.append("test run --job <id>")
        if last_exec and last_crt_job:
            test_cmds.append(f"test results --exec {last_exec} --job {last_crt_job}")
            test_cmds.append(f"test status --exec {last_exec} --job {last_crt_job}")
        else:
            test_cmds.append("test results --exec <id> --job <id>")
            test_cmds.append("test status --exec <id> --job <id>")
    else:
        test_cmds.append("[dim]CRT not configured[/dim]")

    ai_cmds: list[str] = []
    if has_ai:
        ai_cmds.append("ai ask --agent plan \"...\"")
        ai_cmds.append("ai ask --agent build \"...\"")
        ai_cmds.append("ai ask --agent test \"...\"")
        ai_cmds.append("ai ask --agent release \"...\"")
        ai_cmds.append("ai ask --agent operate \"...\"")
        ai_cmds.append("ai chat --agent <name>")
        if last_exec and last_crt_job:
            ai_cmds.append(f"ai triage --exec {last_exec} --job {last_crt_job}")
        else:
            ai_cmds.append("ai triage --exec <id> --job <id>")
    else:
        ai_cmds.append("[dim]AI not configured[/dim]")

    max_rows = max(len(cicd_cmds), len(test_cmds), len(ai_cmds))
    for i in range(max_rows):
        table.add_row(
            cicd_cmds[i] if i < len(cicd_cmds) else "",
            test_cmds[i] if i < len(test_cmds) else "",
            ai_cmds[i] if i < len(ai_cmds) else "",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# copado-hx guide — adaptive, non-interactive context + available actions
# ---------------------------------------------------------------------------

@workflow_app.command("guide")
def guide_cmd():
    """Context summary + available actions for current state (non-interactive)."""
    settings = get_settings()
    state = load_state()

    has_sf = get_token("sf_access_token") is not None
    has_cicd = get_token("copado_actions_key") is not None
    has_crt = get_token("crt") is not None
    has_ai = get_token("ai") is not None
    has_auth = has_sf or has_cicd
    story = settings.current_story_id
    last = state.get("last_action", "")
    test_failed = state.get("last_test_result") == "Failed"

    console.print()

    # ── First-time welcome (no auth) ──
    if not has_auth:
        console.print("[bold cyan]Welcome to copado-hx[/bold cyan] — your headless DevOps CLI.\n")
        ctx_lines = ["[bold]Status:[/bold]  [red]not authenticated[/red]"]
        print_panel("Current context", "\n".join(ctx_lines), style="cyan")
        console.print()
        _print_actions([
            {"cmd": "copado-hx auth login", "why": "Authenticate with Salesforce + CRT + AI"},
            {"cmd": "copado-hx auth status", "why": "Check current auth state"},
        ])
        return

    # ── Build adaptive context ──
    ctx_lines: list[str] = []
    story_label = f"[bold green]{story}[/bold green]" if story else "[yellow]not selected[/yellow]"
    ctx_lines.append(f"[bold]Story:[/bold]       {story_label}")

    if last:
        display_last = last.replace("_", " ")
        last_status = state.get("last_status", "")
        last_error = state.get("last_error", "")
        if last_status == "failed":
            display_last += f" [red](failed{': ' + last_error if last_error else ''})[/red]"
        elif last == "test_results" and test_failed:
            display_last += " [red](tests failed)[/red]"
        elif last_status == "success":
            display_last += " [green](success)[/green]"
        ctx_lines.append(f"[bold]Last action:[/bold] {display_last}")

    last_env = state.get("last_env", "")
    if last_env:
        ctx_lines.append(f"[bold]Environment:[/bold] {last_env}")

    print_panel("Current context", "\n".join(ctx_lines), style="cyan")
    console.print()

    # ── Available actions from recommendation engine ──
    suggestions = recommend()
    if suggestions:
        _print_actions(suggestions)
    else:
        print_info("No actions available. Run [bold]copado-hx auth login[/bold] to get started.")


def _print_actions(actions: list[dict]) -> None:
    """Render actions as a clean bullet list (no numbers, no interaction)."""
    lines: list[str] = []
    for a in actions:
        lines.append(f"  [bold cyan]→[/bold cyan] [bold]{a['cmd']}[/bold]")
        lines.append(f"    [dim]{a['why']}[/dim]")
    console.print(Panel(
        "\n".join(lines),
        title="[bold]Suggested Next Steps[/bold]",
        border_style="blue",
        expand=False,
    ))
    console.print("[dim]You can also run any copado-hx command directly.[/dim]")


# ---------------------------------------------------------------------------
# copado-hx interactive — guided workflow with entry paths
# ---------------------------------------------------------------------------

@workflow_app.command("work")
def work_cmd(
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all available actions table"),
):
    """Interactive guided workflow — select → execute → loop."""
    from copado_hx.utils import suggestions as _suggestions_mod
    _suggestions_mod._suppress = True

    console.print()
    console.print("[bold cyan]copado-hx[/bold cyan] — Interactive Mode")

    try:
        while True:
            choice = _main_menu()
            if choice == 0:
                print_info("Exiting interactive mode.")
                break
            elif choice == 1:
                _story_flow()
            elif choice == 2:
                _deploy_flow()
            elif choice == 3:
                _testing_flow()
            elif choice == 4:
                _ai_flow()
            else:
                print_warning("Invalid choice. Pick 1–4 or 0 to exit.")
    finally:
        _suggestions_mod._suppress = False


def _main_menu() -> int:
    """Show the 4 entry paths and return user choice."""
    console.print()
    console.print("[bold]What would you like to do?[/bold]")
    console.print("  [bold cyan]1.[/bold cyan] Story Management")
    console.print("  [bold cyan]2.[/bold cyan] Deploy (CI/CD / DevOps)")
    console.print("  [bold cyan]3.[/bold cyan] Testing")
    console.print("  [bold cyan]4.[/bold cyan] Ask AI Agent")
    console.print("  [dim]0.[/dim] Exit")
    console.print()
    try:
        return IntPrompt.ask("[bold]Select[/bold]", default=0)
    except (KeyboardInterrupt, EOFError):
        return 0


def _flow_menu(title: str, options: list[dict]) -> int:
    """Generic numbered sub-menu. Returns 0 for back, 1-N for selection, -1 for invalid."""
    console.print()
    console.print(f"[bold]{title}[/bold]")
    for i, opt in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}.[/bold cyan] {opt['label']}")
    console.print(f"  [dim]0.[/dim] ← Back to main menu")
    console.print()
    try:
        choice = IntPrompt.ask("[bold]Select[/bold]", default=0)
    except (KeyboardInterrupt, EOFError):
        return 0
    if choice < 0 or choice > len(options):
        print_warning(f"Invalid choice. Pick 1–{len(options)} or 0 to go back.")
        return -1
    return choice


def _run_selected(cmd: str) -> None:
    """Execute a command and print a separator."""
    console.print()
    print_info(f"Running: [bold]{cmd}[/bold]")
    console.print()
    _execute_cmd(cmd)
    console.print()
    console.print("[bold cyan]" + "─" * 50 + "[/bold cyan]")


def _add_if_missing(opts: list[dict], keyword: str, option: dict) -> None:
    """Add option only if no existing option contains the keyword in its cmd."""
    if not any(keyword in o.get("cmd", "") for o in opts):
        opts.append(option)


# ── Deploy (CI/CD) flow ──────────────────────────────────────────────────

def _deploy_flow():
    """Deploy flow — generic 5-option menu with prompts."""
    while True:
        settings = get_settings()
        state = load_state()
        default_story = settings.current_story_id or ""
        default_env = state.get("last_env", "") or "INT-SFP"

        opts = [
            {"label": "Commit changes", "cmd": "__commit__"},
            {"label": "Validate promotion (dry run)", "cmd": "__validate__"},
            {"label": "Promote to environment", "cmd": "__promote__"},
            {"label": "Deploy to environment", "cmd": "__deploy__"},
            {"label": "Check pipeline status", "cmd": "copado-hx status --watch"},
        ]

        choice = _flow_menu("Deploy (CI/CD)", opts)
        if choice == 0:
            break
        if choice < 0 or choice > len(opts):
            continue

        selected = opts[choice - 1]

        if selected["cmd"] == "__commit__":
            sid = Prompt.ask("[bold]Story ID[/bold]", default=default_story) if default_story else Prompt.ask("[bold]Story ID[/bold]")
            msg = Prompt.ask("[bold]Commit message[/bold]", default=f"update: {sid}")
            _run_selected(f'copado-hx commit --us {sid} -m "{msg}"')

        elif selected["cmd"] == "__validate__":
            sid = Prompt.ask("[bold]Story ID[/bold]", default=default_story) if default_story else Prompt.ask("[bold]Story ID[/bold]")
            env = Prompt.ask("[bold]Target environment[/bold]", default=default_env)
            _run_selected(f"copado-hx promote --us {sid} --env {env} --validate")

        elif selected["cmd"] == "__promote__":
            sid = Prompt.ask("[bold]Story ID[/bold]", default=default_story) if default_story else Prompt.ask("[bold]Story ID[/bold]")
            env = Prompt.ask("[bold]Target environment[/bold]", default=default_env)
            _run_selected(f"copado-hx promote --us {sid} --env {env}")

        elif selected["cmd"] == "__deploy__":
            env = Prompt.ask("[bold]Target environment[/bold]", default=default_env)
            _run_selected(f"copado-hx deploy --env {env} --yes")

        else:
            _run_selected(selected["cmd"])


# ── Testing flow ─────────────────────────────────────────────────────────

def _testing_flow():
    """Testing flow — generic 2-option menu + post-run sub-menu."""
    has_crt = get_token("crt") is not None
    if not has_crt:
        print_warning("CRT is not configured. Run [bold]copado-hx auth login[/bold] to set up testing.")
        return

    from copado_hx.api import crt
    from copado_hx.utils.output import make_table

    cached_jobs: list[dict] = []

    while True:
        opts = [
            {"label": "List test jobs", "cmd": "__list__"},
            {"label": "Run test job", "cmd": "__run__"},
        ]

        choice = _flow_menu("Testing", opts)
        if choice == 0:
            break
        if choice < 0 or choice > len(opts):
            continue

        selected = opts[choice - 1]

        # List test jobs — fetch + display + cache
        if selected["cmd"] == "__list__":
            try:
                cached_jobs = crt.list_test_jobs()
            except Exception as e:
                print_error(f"Failed to list test jobs: {e}")
                continue
            if not cached_jobs:
                print_warning("No test jobs found.")
                continue
            console.print()
            table = make_table(
                "Test Jobs",
                ["#", "jobId", "name", "testCount"],
                [
                    [str(i + 1), j.get("jobId", ""), j.get("name", ""), str(j.get("testCount", ""))]
                    for i, j in enumerate(cached_jobs)
                ],
            )
            console.print(table)
            continue

        # Run test job — pick by # from cached list
        if selected["cmd"] == "__run__":
            if not cached_jobs:
                print_info("Run [bold]List test jobs[/bold] first to load available jobs.")
                continue
            console.print()
            try:
                sno = IntPrompt.ask(
                    f"[bold]Enter job # to run (1–{len(cached_jobs)})[/bold]",
                    choices=[str(i) for i in range(1, len(cached_jobs) + 1)],
                )
            except (KeyboardInterrupt, EOFError):
                continue
            picked = cached_jobs[sno - 1]
            job_id = picked.get("jobId", "")
            _run_selected(f"copado-hx test run --job {job_id}")

            # Post-run sub-menu
            state = load_state()
            last_exec = state.get("last_execution_id", "")
            has_ai = get_token("ai") is not None

            if not last_exec:
                print_warning("No execution ID returned — cannot view results.")
                continue

            while True:
                post_opts = [
                    {"label": "View test results", "cmd": f"copado-hx test results --execution {last_exec} --job {job_id}"},
                ]
                if has_ai:
                    post_opts.append({"label": "Debug results with AI", "cmd": f"copado-hx ai triage --execution {last_exec} --job {job_id}"})

                post_choice = _flow_menu("Test job triggered! What next?", post_opts)
                if post_choice == 0:
                    break
                if post_choice < 0 or post_choice > len(post_opts):
                    continue
                _run_selected(post_opts[post_choice - 1]["cmd"])


# ── Post-story-pick guided flow ──────────────────────────────────────────

def _post_story_pick_flow():
    """After picking a story, show 'what next?' actions instead of returning to a menu."""
    while True:
        settings = get_settings()
        story = settings.current_story_id
        if not story:
            break

        has_ai = get_token("ai") is not None
        opts = [
            {"label": f"Commit changes for {story}", "cmd": f'copado-hx commit --us {story} -m "update"'},
        ]
        if has_ai:
            opts.append({"label": "Get AI build guidance", "cmd": f'copado-hx ai ask --agent build "Suggest metadata for {story}"'})
        opts.append({"label": "Promote to next environment", "cmd": f"copado-hx promote --us {story} --env __ENV__"})

        choice = _flow_menu("What would you like to do next?", opts)
        if choice == 0:
            break
        if choice < 0 or choice > len(opts):
            continue

        selected = opts[choice - 1]

        # Prompt for commit message
        if "commit" in selected["cmd"] and "promote" not in selected["cmd"]:
            msg = Prompt.ask("[bold]Commit message[/bold]", default=f"update: {story}")
            selected["cmd"] = f'copado-hx commit --us {story} -m "{msg}"'

        # Prompt for target environment
        if "__ENV__" in selected["cmd"]:
            env = Prompt.ask("[bold]Target environment[/bold]", default="INT-SFP")
            selected["cmd"] = selected["cmd"].replace("__ENV__", env)

        _run_selected(selected["cmd"])


# ── Story Management flow ────────────────────────────────────────────────

def _story_flow():
    """Story management flow."""
    from copado_hx.api import cicd
    from copado_hx.utils.output import make_table

    cached_stories: list[dict] = []

    while True:
        opts = [
            {"label": "List stories", "cmd": "__list__"},
            {"label": "View story details", "cmd": "__view__"},
            {"label": "Create a new story", "cmd": "copado-hx story create"},
        ]

        choice = _flow_menu("Story Management", opts)
        if choice == 0:
            break
        if choice < 0 or choice > len(opts):
            continue

        selected = opts[choice - 1]

        # List stories — fetch + display + cache
        if selected["cmd"] == "__list__":
            try:
                cached_stories = cicd.list_user_stories()
            except Exception as e:
                print_error(f"Failed to list stories: {e}")
                continue
            if not cached_stories:
                print_warning("No stories found.")
                continue
            console.print()
            table = make_table(
                "Your Stories",
                ["#", "name", "title", "status", "environment"],
                [
                    [str(i + 1), s.get("name", ""), s.get("title", ""), s.get("status", ""), s.get("environment", "")]
                    for i, s in enumerate(cached_stories)
                ],
            )
            console.print(table)
            record_action("story_list", last_status="success")
            continue

        # View details — pick by # from cached list
        if selected["cmd"] == "__view__":
            if not cached_stories:
                print_info("Run [bold]List stories[/bold] first to load your stories.")
                continue
            console.print()
            try:
                sno = IntPrompt.ask(
                    f"[bold]Enter story # (1–{len(cached_stories)})[/bold]",
                    choices=[str(i) for i in range(1, len(cached_stories) + 1)],
                )
            except (KeyboardInterrupt, EOFError):
                continue
            picked = cached_stories[sno - 1]
            sid = picked.get("name", "")
            update_settings(current_story_id=sid)
            record_action("story_pick", last_story=sid)
            _run_selected(f"copado-hx story show --id {sid}")
            # Bridge to Deploy
            console.print()
            proceed = Prompt.ask("[bold]Proceed to Deploy?[/bold] (y/n)", default="n")
            if proceed.lower() in ("y", "yes"):
                _deploy_flow()
            continue

        # Create — prompt for title
        if "story create" in selected["cmd"]:
            title_val = Prompt.ask("[bold]Story title[/bold]")
            pipeline_val = Prompt.ask("[bold]Pipeline ID[/bold] (blank for default)", default="")
            selected["cmd"] = f'copado-hx story create --title "{title_val}"'
            if pipeline_val:
                selected["cmd"] += f" --pipeline {pipeline_val}"

        _run_selected(selected["cmd"])


# ── AI Agent flow ────────────────────────────────────────────────────────

def _ai_flow():
    """AI Agent flow."""
    has_ai = get_token("ai") is not None
    if not has_ai:
        print_warning("AI is not configured. Run [bold]copado-hx auth login[/bold] to set up AI agents.")
        return

    while True:
        state = load_state()
        last_exec = state.get("last_execution_id", "")
        last_crt_job = state.get("last_crt_job_id", "")
        test_failed = state.get("last_test_result") == "Failed"

        opts: list[dict] = []

        # Prioritize triage if tests failed
        if test_failed and last_exec and last_crt_job:
            opts.append({"label": "AI failure triage", "cmd": f"copado-hx ai triage --execution {last_exec} --job {last_crt_job}"})

        opts.extend([
            {"label": "Ask Plan Agent", "agent": "plan"},
            {"label": "Ask Build Agent", "agent": "build"},
            {"label": "Ask Test Agent", "agent": "test"},
            {"label": "Ask Release Agent", "agent": "release"},
            {"label": "Ask Operate Agent", "agent": "operate"},
            {"label": "Ask Knowledge Agent", "agent": "knowledge"},
        ])

        choice = _flow_menu("AI Agents", opts)
        if choice == 0:
            break
        if choice < 0 or choice > len(opts):
            continue

        selected = opts[choice - 1]

        if "agent" in selected:
            question = Prompt.ask(f"[bold]Your question for the {selected['agent']} agent[/bold]")
            selected["cmd"] = f'copado-hx ai ask --agent {selected["agent"]} "{question}"'

        _run_selected(selected["cmd"])


def _execute_cmd(cmd: str) -> None:
    """Execute a copado-hx command string by dispatching to the right function."""
    # Strip the 'copado-hx ' prefix
    parts = cmd.replace("copado-hx ", "").strip().split()
    if not parts:
        return

    try:
        if parts[0] == "auth" and parts[1] == "login":
            from copado_hx.commands.auth import login
            token = _extract_opt(parts, "--token") or _extract_opt(parts, "-t")
            token_type = _extract_opt(parts, "--type") or "all"
            login(token=token, token_type=token_type, json_output=False)

        elif parts[0] == "auth" and parts[1] == "status":
            from copado_hx.commands.auth import status
            status(json_output=False)

        elif parts[0] == "story" and parts[1] == "list":
            from copado_hx.commands.story import list_stories
            list_stories(status=None, json_output=False)

        elif parts[0] == "story" and parts[1] == "pick":
            story_pick()

        elif parts[0] == "story" and parts[1] == "show":
            from copado_hx.commands.story import show_story
            sid = _extract_opt(parts, "--id")
            show_story(story_id=sid, json_output=False)

        elif parts[0] == "story" and parts[1] == "set":
            from copado_hx.commands.story import set_story
            sid = _extract_opt(parts, "--id")
            set_story(story_id=sid or "", json_output=False)

        elif parts[0] == "story" and parts[1] == "create":
            from copado_hx.commands.story import create_story
            title = _extract_quoted(cmd) or "New Story"
            pipeline = _extract_opt(parts, "--pipeline")
            create_story(title=title, pipeline=pipeline, json_output=False)

        elif parts[0] == "commit":
            from copado_hx.commands.pipeline import commit_cmd
            us = _extract_opt(parts, "--us")
            msg = _extract_opt(parts, "-m") or _extract_opt(parts, "--message") or "commit"
            commit_cmd(message=msg, us=us, json_output=False)

        elif parts[0] == "promote":
            from copado_hx.commands.pipeline import promote_cmd
            us = _extract_opt(parts, "--us")
            env = _extract_opt(parts, "--env")
            validate = "--validate" in parts
            promote_cmd(env=env or "", us=us, validate=validate, watch=False, json_output=False)

        elif parts[0] == "deploy":
            from copado_hx.commands.pipeline import deploy_cmd
            env = _extract_opt(parts, "--env")
            yes = "--yes" in parts
            deploy_cmd(env=env or "", watch=False, yes=yes, json_output=False)

        elif parts[0] == "test" and parts[1] == "list":
            from copado_hx.commands.test import list_tests
            list_tests(project=None, json_output=False)

        elif parts[0] == "test" and parts[1] == "run":
            from copado_hx.commands.test import run_test
            job = _extract_opt(parts, "--job")
            suite = _extract_opt(parts, "--suite")
            run_test(suite=suite, job=job, project=None, watch=False, json_output=False)

        elif parts[0] == "test" and parts[1] == "results":
            from copado_hx.commands.test import test_results
            exc = _extract_opt(parts, "--execution")
            job = _extract_opt(parts, "--job")
            test_results(execution=exc or "", job_id=job or "", project=None, format="table", json_output=False)

        elif parts[0] == "ai" and parts[1] == "ask":
            from copado_hx.commands.ai import ask as ai_ask
            agent = _extract_opt(parts, "--agent")
            # Find the prompt (last quoted string)
            prompt = _extract_quoted(cmd)
            ai_ask(agent=agent or "build", prompt=prompt or "Help me with my current task", us=None, json_output=False)

        elif parts[0] == "ai" and parts[1] == "chat":
            from copado_hx.commands.ai import chat as ai_chat
            agent = _extract_opt(parts, "--agent")
            us = _extract_opt(parts, "--us")
            ai_chat(agent=agent or "build", us=us)

        elif parts[0] == "ai" and parts[1] == "triage":
            from copado_hx.commands.ai import triage
            exc = _extract_opt(parts, "--execution")
            job = _extract_opt(parts, "--job")
            triage(execution=exc or "", job_id=job or "", json_output=False)

        elif parts[0] == "env" and parts[1] == "list":
            from copado_hx.commands.env import list_envs
            list_envs(json_output=False)

        elif parts[0] == "status":
            from copado_hx.commands.pipeline import status_cmd
            job = _extract_opt(parts, "--job")
            watch = "--watch" in parts
            status_cmd(job=job, watch=watch, json_output=False)

        else:
            print_warning(f"Command not recognized for interactive mode: {cmd}")
            print_info(f"Run it manually: [bold]{cmd}[/bold]")

    except SystemExit:
        pass
    except Exception as e:
        print_error(f"Command failed: {e}")


def _extract_opt(parts: list[str], flag: str) -> Optional[str]:
    """Extract the value after a flag like --env UAT from a parts list."""
    try:
        idx = parts.index(flag)
        if idx + 1 < len(parts):
            return parts[idx + 1]
    except ValueError:
        pass
    return None


def _extract_quoted(cmd: str) -> Optional[str]:
    """Extract a double-quoted string from a command."""
    import re
    match = re.search(r'"([^"]+)"', cmd)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# copado-hx story pick
# ---------------------------------------------------------------------------

@workflow_app.command("pick")
def story_pick():
    """Interactive story picker — choose a story and set context."""
    from copado_hx.api import cicd

    print_info("Fetching your stories...")

    try:
        stories = cicd.list_user_stories()
    except Exception as e:
        print_error(f"Failed to load stories: {e}")
        raise typer.Exit(1)

    if not stories:
        print_warning("No stories found.")
        return

    # Display stories with numbers
    console.print()
    table = make_table(
        "Open Stories",
        ["#", "name", "title", "status", "environment"],
        [
            [str(i + 1), s.get("name", ""), s.get("title", ""), s.get("status", ""), s.get("environment", "")]
            for i, s in enumerate(stories)
        ],
    )
    console.print(table)
    console.print()

    try:
        choice = IntPrompt.ask(
            "[bold]Select a story (0 to cancel)[/bold]",
            choices=[str(i) for i in range(len(stories) + 1)],
            default=0,
        )
    except (KeyboardInterrupt, EOFError):
        return

    if choice == 0:
        print_info("Cancelled.")
        return

    selected = stories[choice - 1]
    story_id = selected.get("name", "")

    # Set context
    update_settings(current_story_id=story_id)
    record_action("story_pick", last_story=story_id)
    console.print()
    print_success(f"Story selected: [bold]{story_id}[/bold]")
    console.print()
    console.print(f"  [bold]Title:[/bold]       {selected.get('title', 'N/A')}")
    console.print(f"  [bold]Status:[/bold]      {selected.get('status', 'N/A')}")
    console.print(f"  [bold]Environment:[/bold] {selected.get('environment', 'N/A')}")



# ---------------------------------------------------------------------------
# copado-hx ship — guided end-to-end pipeline
# ---------------------------------------------------------------------------

@workflow_app.command("ship")
def ship(
    us: str = typer.Option(..., "--us", help="User story ID"),
    to: str = typer.Option(..., "--to", help="Target environment (e.g. INT-SFP, UAT-SFP)"),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip CRT test execution"),
):
    """Guided end-to-end pipeline: commit → promote → test → deploy."""
    from copado_hx.api import cicd, crt as crt_api
    from copado_hx.commands.pipeline import commit_cmd, promote_cmd, deploy_cmd
    from copado_hx.commands.test import run_test, test_results

    STEP_DELAY = 1.5

    def _ship_step(num: int, title: str, cmd: str):
        console.print()
        console.print(f"[bold yellow]Ship Step {num}[/bold yellow]  [bold]{title}[/bold]")
        console.print(f"[dim]$ {cmd}[/dim]")
        console.print()
        time.sleep(0.5)

    console.print()
    print_panel(
        f"Shipping {us} → {to}",
        f"[bold]Story:[/bold] {us}\n[bold]Target:[/bold] {to}\n[bold]Steps:[/bold] commit → promote → test → deploy",
        style="cyan",
    )
    console.print()

    if not Confirm.ask(f"[bold]Ship {us} to {to}?[/bold]"):
        print_info("Cancelled.")
        return

    # Step 1 — Commit
    _ship_step(1, "Commit Changes", f'copado-hx commit --us {us} -m "ship: {us}"')
    try:
        commit_cmd(message=f"ship: {us}", us=us, json_output=False)
        record_action("commit", last_story=us)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 2 — Promote + Validate
    _ship_step(2, f"Promote to {to}", f"copado-hx promote --us {us} --env {to} --validate")
    try:
        promote_cmd(env=to, us=us, validate=True, watch=False, json_output=False)
        record_action("promote", last_story=us, last_env=to)
    except SystemExit:
        pass
    time.sleep(STEP_DELAY)

    # Step 3 — Run Tests (unless skipped)
    if not skip_tests:
        has_crt = get_token("crt") is not None
        if has_crt:
            _ship_step(3, "Run CRT Tests", "copado-hx test run --job 120649")
            try:
                run_test(suite=None, job="120649", project=None, watch=False, json_output=False)
            except SystemExit:
                pass
            time.sleep(STEP_DELAY)

            # Step 4 — Get Results
            state = load_state()
            exec_id = state.get("last_execution_id", "")
            crt_job = state.get("last_crt_job_id", "120649")
            if exec_id:
                _ship_step(4, "Check Test Results", f"copado-hx test results --execution {exec_id} --job {crt_job}")
                try:
                    test_results(execution=exec_id, job_id=crt_job, project=None, format="table", json_output=False)
                except SystemExit:
                    pass
                time.sleep(STEP_DELAY)
        else:
            print_warning("CRT not configured — skipping tests.")

    # Step 5 — Deploy
    step_num = 5 if not skip_tests else 3
    _ship_step(step_num, f"Deploy to {to}", f"copado-hx deploy --env {to} --yes")
    try:
        deploy_cmd(env=to, watch=False, yes=True, json_output=False)
        record_action("deploy", last_env=to)
    except SystemExit:
        pass

    # Step 6 — AI Release Notes
    has_ai = get_token("ai") is not None
    if has_ai:
        step_num += 1
        _ship_step(step_num, "AI Release Notes", f'copado-hx ai ask --agent release "Release notes for {us}"')
        try:
            from copado_hx.commands.ai import ask as ai_ask
            ai_ask(
                agent="release",
                prompt=f"Generate concise release notes for user story {us}",
                us=us,
                json_output=False,
            )
        except SystemExit:
            pass

    # Finale
    console.print()
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print(f"[bold green]  SHIPPED — {us} → {to}[/bold green]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print()
