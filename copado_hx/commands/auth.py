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
    get_token,
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


def _validate_sf_token() -> Optional[bool]:
    """Validate Salesforce OAuth token via lightweight SOQL query.

    Returns:
        True if token is valid
        False if token is expired/invalid
        None if network error or token not configured
    """
    token = get_token("sf_access_token")
    if not token:
        return None

    settings = get_settings()
    instance_url = settings.sf_instance_url or settings.copado_sf_instance_url
    if not instance_url:
        return None

    try:
        import httpx
        url = f"{instance_url.rstrip('/')}/services/data/v62.0/query?q=SELECT+Id+FROM+User+LIMIT+1"
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 401 or resp.status_code == 403:
            return False
        return resp.status_code == 200
    except Exception:
        return None


def _validate_crt_token() -> Optional[bool]:
    """Validate CRT token via test API call.

    Returns:
        True if token is valid
        False if token is expired/invalid
        None if network error or token not configured
    """
    token = get_token("crt")
    if not token:
        return None

    settings = get_settings()
    base_url = settings.copado_crt_base_url or "https://api.eu-robotic.copado.com"
    project_id = settings.crt_project_id
    org_id = settings.crt_org_id
    if not project_id:
        return None

    try:
        import httpx
        # Use the jobs endpoint with correct CRT header format (X-Authorization, not Authorization)
        url = f"{base_url.rstrip('/')}/pace/v4/projects/{project_id}/jobs"
        params = {"orgId": org_id} if org_id else None
        resp = httpx.get(
            url,
            headers={"X-Authorization": token, "Content-Type": "application/json"},
            params=params,
            timeout=10,
        )
        if resp.status_code == 401 or resp.status_code == 403:
            return False
        return resp.status_code == 200
    except Exception:
        return None


def _validate_ai_token() -> Optional[bool]:
    """Validate AI Platform token via test API call.

    Returns:
        True if token is valid
        False if token is expired/invalid
        None if network error or token not configured
    """
    token = get_token("ai")
    if not token:
        return None

    settings = get_settings()
    base_url = settings.copado_ai_base_url or "https://copadogpt-api.robotic.copado.com"

    try:
        import httpx
        # Use the prompts endpoint which is simpler and doesn't require org_id
        url = f"{base_url.rstrip('/')}/prompts"
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 401 or resp.status_code == 403:
            return False
        return resp.status_code == 200
    except Exception:
        return None


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
    verify_all: bool = typer.Option(False, "--verify-all", help="Validate all tokens (SF, CRT, AI) instead of just SF"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show the current authentication status for all Copado APIs.

    Status semantics:
    - Configured = token exists in keyring
    - Verified = lightweight API check succeeded
    - Expired/Invalid = verification failed

    By default, only validates Salesforce token. Use --verify-all to validate all tokens.
    """
    auth = get_auth_status()
    settings = get_settings()

    # Validate tokens
    sf_valid = _validate_sf_token()
    crt_valid = _validate_crt_token() if verify_all else None
    ai_valid = _validate_ai_token() if verify_all else None

    # Build enhanced auth status with validation results
    enhanced_auth = {}
    for label, status_val in auth.items():
        if "Salesforce OAuth" in label:
            if sf_valid is True:
                enhanced_auth[label] = f"{status_val} [green][Verified][/green]"
            elif sf_valid is False:
                enhanced_auth[label] = f"{status_val} [red][Expired/Invalid][/red]"
            else:
                enhanced_auth[label] = f"{status_val} [yellow][Unknown][/yellow]"
        elif "CRT" in label and verify_all:
            if crt_valid is True:
                enhanced_auth[label] = f"{status_val} [green][Verified][/green]"
            elif crt_valid is False:
                enhanced_auth[label] = f"{status_val} [red][Expired/Invalid][/red]"
            else:
                enhanced_auth[label] = f"{status_val} [yellow][Unknown][/yellow]"
        elif "AI Platform" in label and verify_all:
            if ai_valid is True:
                enhanced_auth[label] = f"{status_val} [green][Verified][/green]"
            elif ai_valid is False:
                enhanced_auth[label] = f"{status_val} [red][Expired/Invalid][/red]"
            else:
                enhanced_auth[label] = f"{status_val} [yellow][Unknown][/yellow]"
        else:
            enhanced_auth[label] = status_val

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
        # For JSON output, include validation results
        json_data = {**enhanced_auth, **connection_info}
        json_data["sf_token_valid"] = sf_valid
        if verify_all:
            json_data["crt_token_valid"] = crt_valid
            json_data["ai_token_valid"] = ai_valid
        smart_output(json_data, json_mode=True)
    else:
        # Determine overall connection status based on SF token validity
        sf_token_configured = get_token("sf_access_token") is not None
        if sf_token_configured:
            if sf_valid is True:
                title = "Auth Status — [green]Connected (SF Token Verified)[/green]"
            elif sf_valid is False:
                title = "Auth Status — [red]Connected (SF Token Expired)[/red]"
            else:
                title = "Auth Status — [yellow]Connected (SF Token Status Unknown)[/yellow]"
        else:
            title = "Auth Status — [red]Not Connected[/red]"

        lines = [f"[bold]{k}:[/bold] {v}" for k, v in enhanced_auth.items()]
        lines.append("")
        lines.extend(f"[bold]{k}:[/bold] {v}" for k, v in connection_info.items())
        print_panel(title, "\n".join(lines))
        if not sf_token_configured:
            print_info("Run [bold]copado-hx auth login[/bold] to authenticate.")
        elif sf_valid is False:
            print_info("Salesforce token expired. Run [bold]copado-hx auth refresh-sf[/bold] to refresh.")
    record_action("auth_status")


@auth_app.command("refresh-sf")
def refresh_sf():
    """Refresh Salesforce OAuth token only (quick re-auth without full setup).

    Reuses stored Salesforce instance URL, client ID, and client secret.
    Only runs the browser OAuth flow - does not prompt for CRT, AI, or Actions keys.

    Use this when your Salesforce session expires but other credentials are still valid.
    """
    from copado_hx.auth.sf_oauth import browser_login, SFOAuthError
    from copado_hx.auth.store import get_token as _get_token

    settings = get_settings()
    login_url = settings.sf_instance_url or settings.copado_sf_instance_url
    client_id = settings.sf_client_id
    client_secret = _get_token("sf_client_secret") or ""

    if not login_url:
        print_error("Salesforce instance URL not configured. Run [bold]copado-hx auth login[/bold] for full setup.")
        raise typer.Exit(1)

    if not client_id:
        print_error("Salesforce client ID not configured. Run [bold]copado-hx auth login[/bold] for full setup.")
        raise typer.Exit(1)

    print_info("[bold]Refreshing Salesforce OAuth token...[/bold]")
    print_info("Opening browser for Salesforce login...")

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
        print_success(f"✅ Salesforce token refreshed successfully!")
        print_success(f"Instance: {result.instance_url}")
        print_success(f"Access token stored (****{result.access_token[-4:]})")
        record_action("auth_refresh_sf")
    except SFOAuthError as exc:
        print_error(f"OAuth failed: {exc}")
        print_info("If the issue persists, run [bold]copado-hx auth login[/bold] for full reconfiguration.")
        raise typer.Exit(1)


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
