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
from copado_hx.utils.state import record_action
from copado_hx.utils.output import print_success, print_error, print_info, smart_output, print_panel, print_warning

auth_app = typer.Typer(help="Manage authentication for Copado APIs.")


def _try_oauth_flow(login_url: str) -> bool:
    """Attempt SF OAuth to obtain an access token.

    Strategy (in order):
      1. Browser-based authorization code flow (works on all orgs)
      2. Username-password flow (fallback for headless envs)

    Returns True if a token was obtained, False otherwise.
    """
    from copado_hx.auth.sf_oauth import browser_login, password_grant, SFOAuthError
    from copado_hx.auth.store import get_token as _get_token

    settings = get_settings()
    client_id = settings.sf_client_id
    client_secret = _get_token("sf_client_secret") or ""

    if not client_id:
        print_info("  OAuth skipped (no client ID configured).")
        return False

    # ── Try 1: Browser flow ──
    print_info("\n  Opening browser for Salesforce login...")
    print_info("  (Waiting up to 120 seconds — log in and approve access)")
    try:
        result = browser_login(
            login_url=login_url,
            client_id=client_id,
            client_secret=client_secret,
        )
        store_token("sf_access_token", result.access_token)
        update_settings(
            sf_instance_url=result.instance_url,
            copado_sf_instance_url=result.instance_url,
        )
        print_success(f"  OAuth success! Instance: {result.instance_url}")
        print_success(f"  Access token stored (****{result.access_token[-4:]})")
        return True
    except SFOAuthError as exc:
        print_warning(f"  Browser login failed: {exc}")

    # ── Try 2: Password flow (if credentials are available) ──
    username = settings.sf_username
    password = _get_token("sf_password")
    if username and password:
        security_token = _get_token("sf_security_token") or ""
        print_info("  Trying password flow as fallback...")
        try:
            result = password_grant(
                login_url=login_url,
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
                security_token=security_token,
            )
            store_token("sf_access_token", result.access_token)
            update_settings(
                sf_instance_url=result.instance_url,
                copado_sf_instance_url=result.instance_url,
            )
            print_success(f"  OAuth success! Instance: {result.instance_url}")
            print_success(f"  Access token stored (****{result.access_token[-4:]})")
            return True
        except SFOAuthError as exc:
            print_warning(f"  Password flow failed: {exc}")

    print_warning("  Could not obtain token automatically. You can paste one manually later.")
    return False


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
        print_info("[bold]\n── Copado CI/CD (Salesforce OAuth) ──[/bold]")
        print_info("  Reads use SF OAuth → SOQL.  Actions use mcwebhook + Copado Actions key.")

        sf_url = Prompt.ask(
            "  Salesforce login URL (e.g. https://login.salesforce.com or My Domain)",
            default=settings.sf_instance_url or settings.copado_sf_instance_url or "https://login.salesforce.com",
        )
        if sf_url.strip():
            sf_url = sf_url.strip().split("/one/")[0].split("/lightning/")[0].rstrip("/")
            if ".lightning.force.com" in sf_url:
                subdomain = sf_url.replace("https://", "").replace("http://", "").split(".")[0]
                sf_url = f"https://{subdomain}.my.salesforce.com"
            update_settings(sf_instance_url=sf_url, copado_sf_instance_url=sf_url)
            print_success(f"Salesforce URL: {sf_url}")

        sf_client_id = Prompt.ask(
            "  Connected App Client ID (consumer key)",
            default=settings.sf_client_id or "",
        )
        if sf_client_id.strip():
            update_settings(sf_client_id=sf_client_id.strip())

        sf_client_secret = Prompt.ask(
            "  Connected App Client Secret (blank to reuse stored)", default="", password=True
        )
        if sf_client_secret.strip():
            store_token("sf_client_secret", sf_client_secret.strip())
            print_success("SF client secret: stored in keyring")

        # ── Browser OAuth — opens browser, captures token automatically ──
        _try_oauth_flow(sf_url)

        # Copado Actions API Key (for mcwebhook calls)
        print_info("[bold]\n── Copado Actions API Key (for commit/promote/deploy) ──[/bold]")
        actions_key = Prompt.ask(
            "  Copado Actions API Key (from Copado Actions API tab)", default="", password=True
        )
        if actions_key.strip():
            store_token("copado_actions_key", actions_key.strip())
            print_success("Copado Actions key: stored")
        else:
            print_info("Copado Actions key: skipped")

        # Pipeline ID for source format validation
        pipeline_id = Prompt.ask(
            "  Pipeline ID (18-char SF Id, optional)",
            default=settings.copado_actions_pipeline_id or "",
        )
        if pipeline_id.strip():
            update_settings(copado_actions_pipeline_id=pipeline_id.strip())

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
    record_action("auth_login")


@auth_app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show the current authentication status for all Copado APIs."""
    auth = get_auth_status()
    settings = get_settings()

    # Add connection details to status
    connection_info = {
        "Salesforce Org": settings.sf_instance_url or settings.copado_sf_instance_url or "Not configured",
        "SF Username": settings.sf_username or "Not configured",
        "SF Client ID": (settings.sf_client_id[:8] + "...") if settings.sf_client_id else "Not configured",
        "Pipeline ID": settings.copado_actions_pipeline_id or "Not configured",
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
    record_action("auth_status")


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
