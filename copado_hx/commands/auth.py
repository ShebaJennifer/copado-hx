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
from copado_hx.utils.config import get_settings, update_settings
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
        # Interactive: ask for each token + connection details
        settings = get_settings()

        # --- Salesforce / CI/CD ---
        print_info("[bold]\n── Copado CI/CD (Salesforce) ──[/bold]")
        sf_url = Prompt.ask(
            "  Salesforce org URL (e.g. https://myorg.my.salesforce.com)",
            default=settings.copado_sf_instance_url or "",
        )
        if sf_url.strip():
            # Normalize: strip trailing slashes and /one/one.app etc.
            sf_url = sf_url.strip().split("/one/")[0].split("/lightning/")[0].rstrip("/")
            # Convert lightning URL to .my.salesforce.com
            if ".lightning.force.com" in sf_url:
                subdomain = sf_url.replace("https://", "").replace("http://", "").split(".")[0]
                sf_url = f"https://{subdomain}.my.salesforce.com"
            update_settings(copado_sf_instance_url=sf_url)
            print_success(f"Salesforce URL: {sf_url}")

        cicd_val = Prompt.ask("  CI/CD API Token (Session ID or API key)", default="", password=True)
        if cicd_val.strip():
            store_token("cicd", cicd_val.strip())
            print_success("CI/CD token: stored")
        else:
            print_info("CI/CD token: skipped")

        # --- CRT ---
        print_info("[bold]\n── Copado Robotic Testing (CRT) ──[/bold]")
        crt_url = Prompt.ask(
            "  CRT base URL",
            default=settings.copado_crt_base_url or "https://eu-robotic.copado.com",
        )
        if crt_url.strip():
            update_settings(copado_crt_base_url=crt_url.strip().rstrip("/"))
            print_success(f"CRT URL: {crt_url.strip()}")

        crt_org = Prompt.ask("  CRT Org ID", default=settings.crt_org_id or "")
        if crt_org.strip():
            update_settings(crt_org_id=crt_org.strip())
            print_success(f"CRT Org ID: {crt_org.strip()}")

        crt_project = Prompt.ask("  CRT Project ID", default=settings.crt_project_id or "")
        if crt_project.strip():
            update_settings(crt_project_id=crt_project.strip())
            print_success(f"CRT Project ID: {crt_project.strip()}")

        crt_val = Prompt.ask("  CRT Personal Access Key (PAK)", default="", password=True)
        if crt_val.strip():
            store_token("crt", crt_val.strip())
            print_success("CRT PAK: stored")
        else:
            print_info("CRT PAK: skipped")

        # --- AI ---
        print_info("[bold]\n── Copado AI Platform ──[/bold]")
        ai_val = Prompt.ask("  AI Platform API Key", default="", password=True)
        if ai_val.strip():
            store_token("ai", ai_val.strip())
            print_success("AI API Key: stored")
        else:
            print_info("AI API Key: skipped")

        # Disable mock mode if any real tokens were stored
        if is_authenticated():
            update_settings(mock_mode=False)
            print_success("\nMock mode: [bold]disabled[/bold] (using real APIs)")

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
    settings = get_settings()

    # Add connection details to status
    connection_info = {
        "Salesforce Org": settings.copado_sf_instance_url or "Not configured",
        "CRT URL": settings.copado_crt_base_url or "Not configured",
        "CRT Org ID": settings.crt_org_id or "Not configured",
        "CRT Project ID": settings.crt_project_id or "Not configured",
        "Mock Mode": "Enabled" if settings.mock_mode else "Disabled",
    }

    if json_output:
        smart_output({**auth, **connection_info}, json_mode=True)
    else:
        authenticated = is_authenticated()
        title = "Auth Status — [green]Connected[/green]" if authenticated else "Auth Status — [red]Not Connected[/red]"
        lines = [f"[bold]{k}:[/bold] {v}" for k, v in auth.items()]
        lines.append("")
        lines.extend(f"[bold]{k}:[/bold] {v}" for k, v in connection_info.items())
        print_panel(title, "\n".join(lines))
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
