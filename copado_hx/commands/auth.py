"""
copado-hx auth — Authentication commands.

Usage:
  copado-hx auth login --token <api-token>    Token-based auth
  copado-hx auth login                        Interactive prompt
  copado-hx auth status                       Show auth status
  copado-hx auth logout                       Clear stored tokens
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.prompt import Prompt

from copado_hx.auth.store import (
    store_token,
    delete_token,
    get_auth_status,
    is_authenticated,
    TOKEN_TYPES,
)
from copado_hx.utils.output import print_success, print_error, print_info, smart_output, print_panel

auth_app = typer.Typer(help="Manage authentication for Copado APIs.")


@auth_app.command("login")
def login(
    token: Optional[str] = typer.Option(None, "--token", "-t", help="API token (if omitted, interactive prompt)"),
    token_type: str = typer.Option("all", "--type", help="Token type: cicd | crt | ai | all"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Authenticate with Copado APIs. Tokens are stored securely in your OS keychain."""
    if token_type == "all" and token:
        # Single token provided — ask which type
        print_info("A single token was provided. Which API is it for?")
        token_type = Prompt.ask("Token type", choices=["cicd", "crt", "ai"])

    if token_type == "all" and not token:
        # Interactive: ask for each token
        print_info("Enter your API tokens (press Enter to skip any).")
        for t_type, label in TOKEN_TYPES.items():
            val = Prompt.ask(f"  {label}", default="", password=True)
            if val.strip():
                store_token(t_type, val.strip())
                print_success(f"{label}: stored")
            else:
                print_info(f"{label}: skipped")
    elif token:
        store_token(token_type, token)
        print_success(f"{TOKEN_TYPES.get(token_type, token_type)}: stored securely")
    else:
        val = Prompt.ask(f"Enter {TOKEN_TYPES.get(token_type, token_type)}", password=True)
        if val.strip():
            store_token(token_type, val.strip())
            print_success(f"{TOKEN_TYPES.get(token_type, token_type)}: stored securely")
        else:
            print_error("No token provided.")
            raise typer.Exit(1)

    smart_output(get_auth_status(), json_mode=json_output, title="Auth Status")


@auth_app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show the current authentication status for all Copado APIs."""
    auth = get_auth_status()
    if json_output:
        smart_output(auth, json_mode=True)
    else:
        authenticated = is_authenticated()
        title = "Auth Status — [green]Connected[/green]" if authenticated else "Auth Status — [red]Not Connected[/red]"
        print_panel(title, "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in auth.items()))
        if not authenticated:
            print_info("Run [bold]copado-hx auth login[/bold] to authenticate.")


@auth_app.command("logout")
def logout(
    token_type: str = typer.Option("all", "--type", help="Token type to clear: cicd | crt | ai | all"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Clear stored authentication tokens."""
    if token_type == "all":
        for t_type in TOKEN_TYPES:
            delete_token(t_type)
        print_success("All tokens cleared.")
    else:
        delete_token(token_type)
        print_success(f"{TOKEN_TYPES.get(token_type, token_type)} token cleared.")

    smart_output(get_auth_status(), json_mode=json_output, title="Auth Status")
