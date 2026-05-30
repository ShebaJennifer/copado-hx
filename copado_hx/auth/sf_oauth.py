"""
Salesforce OAuth 2.0 flows for copado-hx authentication.

Supports two flows:
  1. Authorization Code (browser) — works on all orgs, no special settings needed
  2. Username-Password (headless) — requires org-level SOAP/OAuth settings

Returns: access_token, instance_url
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Optional

import httpx


class SFOAuthError(Exception):
    """Raised when the Salesforce OAuth flow fails."""

    def __init__(self, error: str, description: str = ""):
        self.error = error
        self.description = description
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        base = f"Salesforce OAuth failed: {self.error}"
        if self.description:
            base += f"\n  {self.description}"

        # ── actionable hints ──
        hints = {
            "invalid_grant": (
                "\nTroubleshooting:\n"
                "  1. Wrong username or password → double-check in Salesforce login\n"
                "  2. Missing security token → append it to your password\n"
                "     (Profile → Reset My Security Token → check email)\n"
                "  3. IP not whitelisted → add your IP to Connected App trusted ranges\n"
                "  4. User locked out → check login history in SF Setup"
            ),
            "invalid_client_id": (
                "\nTroubleshooting:\n"
                "  1. Consumer Key is wrong → copy it exactly from the Connected App\n"
                "  2. Connected App not yet active → wait a few minutes after creation"
            ),
            "invalid_client": (
                "\nTroubleshooting:\n"
                "  1. Consumer Secret is wrong → regenerate in the Connected App\n"
                "  2. Connected App policies block this user"
            ),
            "redirect_uri_mismatch": (
                "\nTroubleshooting:\n"
                "  Callback URL mismatch. For headless CLI use, set the\n"
                "  Connected App callback to: https://login.salesforce.com/services/oauth2/callback"
            ),
        }
        return base + hints.get(self.error, "")


@dataclass
class SFOAuthResult:
    access_token: str
    instance_url: str
    token_type: str = "Bearer"
    issued_at: str = ""


def password_grant(
    *,
    login_url: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
    security_token: str = "",
    timeout: int = 30,
) -> SFOAuthResult:
    """Execute the OAuth 2.0 username-password grant and return tokens.

    Parameters
    ----------
    login_url : str
        e.g. ``https://login.salesforce.com`` or ``https://test.salesforce.com``
        or a My Domain URL like ``https://myorg.my.salesforce.com``.
    client_id : str
        Connected-app consumer key.
    client_secret : str
        Connected-app consumer secret.
    username : str
        Salesforce username.
    password : str
        Salesforce password.  If a *security_token* is required, it will be
        appended automatically.
    security_token : str
        Salesforce security token (appended to password).
    """
    token_url = f"{login_url.rstrip('/')}/services/oauth2/token"
    full_password = f"{password}{security_token}"

    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": full_password,
            },
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise SFOAuthError("network_error", str(exc))

    if resp.status_code != 200:
        try:
            body = resp.json()
            raise SFOAuthError(
                body.get("error", f"http_{resp.status_code}"),
                body.get("error_description", resp.text[:300]),
            )
        except (ValueError, KeyError):
            raise SFOAuthError(f"http_{resp.status_code}", resp.text[:300])

    data = resp.json()
    return SFOAuthResult(
        access_token=data["access_token"],
        instance_url=data["instance_url"],
        token_type=data.get("token_type", "Bearer"),
        issued_at=data.get("issued_at", ""),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Authorization Code flow  (browser-based, works on all orgs)
# ═══════════════════════════════════════════════════════════════════════════

_CALLBACK_PORT = 8443
_REDIRECT_URI = f"https://localhost:{_CALLBACK_PORT}/callback"


def browser_login(
    *,
    login_url: str,
    client_id: str,
    client_secret: str = "",
    callback_url: str = "",
    timeout: int = 120,
) -> SFOAuthResult:
    """Run the OAuth 2.0 authorization-code flow via the user's browser.

    1. Opens the Salesforce authorize URL in the default browser
    2. User logs in and approves access
    3. Salesforce redirects to the callback URL with an auth code
    4. User pastes the full redirect URL back into the terminal
    5. Exchanges the code for an access_token

    Parameters
    ----------
    login_url : str
        e.g. ``https://login.salesforce.com`` or My Domain URL.
    client_id : str
        Connected-app / External Client App consumer key.
    client_secret : str
        Consumer secret (optional for some app types).
    callback_url : str
        Callback URL configured in the app (default: _REDIRECT_URI).
    timeout : int
        Not used in paste-based flow; kept for API compat.
    """
    redirect_uri = callback_url or _REDIRECT_URI

    # Build authorize URL
    authorize_url = (
        f"{login_url.rstrip('/')}/services/oauth2/authorize?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "api refresh_token",
            "prompt": "login consent",
        })
    )

    # Open browser
    webbrowser.open(authorize_url)

    # Ask the user to paste the redirect URL
    print("\n  After approving access, your browser will redirect to a URL")
    print("  that may show an error page — that's expected.")
    print("  Copy the FULL URL from your browser's address bar and paste it here.\n")
    redirect_response = input("  Paste redirect URL here: ").strip()

    if not redirect_response:
        raise SFOAuthError("no_input", "No URL was pasted.")

    # Extract the auth code from the pasted URL
    parsed = urllib.parse.urlparse(redirect_response)
    params = urllib.parse.parse_qs(parsed.query)

    if "error" in params:
        raise SFOAuthError(
            params["error"][0],
            params.get("error_description", [""])[0],
        )

    if "code" not in params:
        raise SFOAuthError(
            "no_code",
            "The pasted URL does not contain an authorization code.\n"
            "  Make sure you copy the full URL including the ?code= parameter.",
        )

    auth_code = params["code"][0]

    # Exchange auth code for access token
    token_url = f"{login_url.rstrip('/')}/services/oauth2/token"
    exchange_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    if client_secret:
        exchange_data["client_secret"] = client_secret

    try:
        resp = httpx.post(
            token_url,
            data=exchange_data,
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except httpx.RequestError as exc:
        raise SFOAuthError("network_error", f"Token exchange failed: {exc}")

    if resp.status_code != 200:
        try:
            body = resp.json()
            raise SFOAuthError(
                body.get("error", f"http_{resp.status_code}"),
                body.get("error_description", resp.text[:300]),
            )
        except (ValueError, KeyError):
            raise SFOAuthError(f"http_{resp.status_code}", resp.text[:300])

    data = resp.json()
    return SFOAuthResult(
        access_token=data["access_token"],
        instance_url=data["instance_url"],
        token_type=data.get("token_type", "Bearer"),
        issued_at=data.get("issued_at", ""),
    )
