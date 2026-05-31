"""
copado-hx ai — Copado AI Agent commands.

Usage:
  copado-hx ai ask --agent plan "Refine user story US-1234"
  copado-hx ai ask --agent build "Generate Apex for lead scoring"
  copado-hx ai ask --agent test "Generate CRT QWord test script"
  copado-hx ai ask --agent release "Generate release notes for US-1234"
  copado-hx ai ask --agent operate "Create change management plan"
  copado-hx ai chat --agent build                  Interactive REPL
  copado-hx ai chat --agent release --us US-1234   Scoped to a story

The 5 Copado AI Agents:
  plan    — Sprint planning, user story refinement, conflict detection
  build   — Code generation, metadata analysis, coverage improvement
  test    — CRT QWord test script generation, automation advice
  release — Deployment coordination, error analysis, release notes
  operate — Post-release docs, change management, training materials
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.markdown import Markdown
from rich.prompt import Prompt

from copado_hx.api import ai_platform
from copado_hx.utils.config import get_settings
from copado_hx.utils.output import (
    smart_output,
    print_success,
    print_error,
    print_info,
    print_panel,
    console,
)

ai_app = typer.Typer(help="Interact with Copado's 5 specialist AI agents.")

AGENT_LABELS = {
    "plan": "Plan Agent",
    "build": "Build Agent",
    "test": "Test Agent",
    "release": "Release Agent",
    "operate": "Operate Agent",
}


# ---------------------------------------------------------------------------
# Ask — single-turn question
# ---------------------------------------------------------------------------

@ai_app.command("ask")
def ask(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent: plan | build | test | release | operate"),
    prompt: str = typer.Argument(..., help="Your question or instruction for the agent"),
    us: Optional[str] = typer.Option(None, "--us", help="User story ID for context"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Send a single prompt to a Copado AI agent and get a response."""
    try:
        agent = ai_platform.validate_agent(agent)
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)

    # Enrich prompt with user story context if provided
    full_prompt = prompt
    if us:
        full_prompt = f"[Context: User Story {us}] {prompt}"
    elif get_settings().current_story_id:
        full_prompt = f"[Context: User Story {get_settings().current_story_id}] {prompt}"

    label = AGENT_LABELS.get(agent, agent)
    print_info(f"Asking [bold]{label}[/bold]...")

    try:
        # Start dialogue and send message
        dialogue = ai_platform.start_dialogue(agent)
        dialogue_id = dialogue.get("dialogueId", "")

        response = ai_platform.send_message(dialogue_id, full_prompt, agent=agent)

        if json_output:
            smart_output(response, json_mode=True)
        else:
            content = response.get("content", "No response received.")
            console.print()
            print_panel(
                f"{label} Response",
                "",
                style="magenta",
            )
            # Render as Markdown for beautiful formatting
            console.print(Markdown(content))
            console.print()

    except Exception as e:
        print_error(f"AI request failed: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Chat — interactive multi-turn REPL
# ---------------------------------------------------------------------------

@ai_app.command("chat")
def chat(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent: plan | build | test | release | operate"),
    us: Optional[str] = typer.Option(None, "--us", help="User story ID for context"),
):
    """Open an interactive chat session with a Copado AI agent (type 'exit' to quit)."""
    try:
        agent = ai_platform.validate_agent(agent)
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)

    label = AGENT_LABELS.get(agent, agent)
    story_ctx = us or get_settings().current_story_id

    console.print()
    console.print(f"[bold magenta]{'═' * 60}[/bold magenta]")
    console.print(f"[bold magenta]  Chat Session — {label}[/bold magenta]")
    if story_ctx:
        console.print(f"[bold magenta]  Context: {story_ctx}[/bold magenta]")
    console.print(f"[bold magenta]  Type 'exit' or 'quit' to end session[/bold magenta]")
    console.print(f"[bold magenta]{'═' * 60}[/bold magenta]")
    console.print()

    try:
        dialogue = ai_platform.start_dialogue(agent)
        dialogue_id = dialogue.get("dialogueId", "")

        while True:
            try:
                user_input = Prompt.ask(f"[bold cyan]You[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.strip().lower() in ("exit", "quit", "q"):
                break

            if not user_input.strip():
                continue

            # Enrich with story context
            full_prompt = user_input
            if story_ctx:
                full_prompt = f"[Context: User Story {story_ctx}] {user_input}"

            try:
                response = ai_platform.send_message(dialogue_id, full_prompt, agent=agent)
                content = response.get("content", "No response.")
                console.print()
                console.print(f"[bold magenta]{label}:[/bold magenta]")
                console.print(Markdown(content))
                console.print()
            except Exception as e:
                print_error(f"Error: {e}")

    except Exception as e:
        print_error(f"Failed to start chat session: {e}")
        raise typer.Exit(1)

    print_info("Chat session ended.")


# ---------------------------------------------------------------------------
# Triage — AI-powered test failure analysis (WOW feature)
# ---------------------------------------------------------------------------

@ai_app.command("triage")
def triage(
    execution: str = typer.Option(..., "--execution", "-e", help="CRT execution ID with failures"),
    job_id: str = typer.Option(..., "--job", "-j", help="CRT job ID (required — from test run output)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """AI-powered test failure triage — analyze why tests failed and suggest fixes."""
    from copado_hx.api import crt

    print_info(f"Fetching test results for execution [bold]{execution}[/bold]...")

    try:
        results = crt.get_test_results(execution, job_id=job_id)
        failures = results.get("failures", [])

        if not failures:
            print_success("No failures found — all tests passed!")
            return

        # Build a prompt from the failure data
        failure_summary = "\n".join(
            f"- {f.get('testName', 'Unknown')}: {f.get('error', 'No error message')}"
            for f in failures
        )
        prompt = (
            f"Analyze these CRT test failures and suggest fixes:\n\n{failure_summary}\n\n"
            f"Total tests: {results.get('totalTests', 0)}, "
            f"Passed: {results.get('passed', 0)}, "
            f"Failed: {results.get('failed', 0)}"
        )

        print_info("Asking [bold]Release Agent[/bold] to analyze failures...")

        dialogue = ai_platform.start_dialogue("release")
        dialogue_id = dialogue.get("dialogueId", "")
        response = ai_platform.send_message(dialogue_id, prompt, agent="release")

        if json_output:
            smart_output({
                "failures": failures,
                "ai_analysis": response.get("content", ""),
            }, json_mode=True)
        else:
            # Show failures
            print_panel(
                f"Test Failures — {execution}",
                "\n".join(f"[red]\u2718 {f.get('testName', '?')}[/red]: {f.get('error', '')}" for f in failures),
                style="red",
            )
            console.print()
            # Show AI analysis
            content = response.get("content", "No analysis available.")
            print_panel("AI Triage — Release Agent", "", style="magenta")
            console.print(Markdown(content))

    except Exception as e:
        print_error(f"Triage failed: {e}")
        raise typer.Exit(1)
