"""
Salesforce OAuth 2.0 username-password flow for headless CI/CD auth.

POST https://<instance>/services/oauth2/token
  grant_type=password
  client_id=<consumer_key>
  client_secret=<consumer_secret>
  username=<sf_username>
  password=<sf_password><security_token>

Returns: access_token, instance_url
"""

from __future__ import annotations

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
