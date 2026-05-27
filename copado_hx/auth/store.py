"""
Secure token storage for copado-hx.

Stores API tokens using the OS keychain (via keyring library).
This means tokens are encrypted at rest and never stored in plaintext files.

Three separate tokens are managed:
  - cicd : Copado CI/CD API bearer token
  - crt  : CRT Personal Access Key (PAK)
  - ai   : Copado AI Platform API key

Think of this like a password manager for your API keys.
"""

from __future__ import annotations

from typing import Optional

import keyring

SERVICE_PREFIX = "copado-hx"

# The three token types we manage
TOKEN_TYPES = {
    "cicd": "Copado CI/CD API Token",
    "crt": "CRT Personal Access Key (PAK)",
    "ai": "Copado AI Platform API Key",
}


def _service_name(token_type: str) -> str:
    """Keyring service name for a given token type."""
    return f"{SERVICE_PREFIX}-{token_type}"


def store_token(token_type: str, token: str) -> None:
    """Save a token securely in the OS keychain."""
    if token_type not in TOKEN_TYPES:
        raise ValueError(f"Unknown token type '{token_type}'. Valid: {list(TOKEN_TYPES.keys())}")
    keyring.set_password(_service_name(token_type), "default", token)


def get_token(token_type: str) -> Optional[str]:
    """Retrieve a token from the OS keychain. Returns None if not stored."""
    if token_type not in TOKEN_TYPES:
        raise ValueError(f"Unknown token type '{token_type}'. Valid: {list(TOKEN_TYPES.keys())}")
    return keyring.get_password(_service_name(token_type), "default")


def delete_token(token_type: str) -> None:
    """Remove a token from the OS keychain."""
    if token_type not in TOKEN_TYPES:
        raise ValueError(f"Unknown token type '{token_type}'. Valid: {list(TOKEN_TYPES.keys())}")
    try:
        keyring.delete_password(_service_name(token_type), "default")
    except keyring.errors.PasswordDeleteError:
        pass  # Already gone


def get_auth_status() -> dict:
    """Check which tokens are stored and return a summary."""
    status = {}
    for token_type, label in TOKEN_TYPES.items():
        token = get_token(token_type)
        if token:
            # Show only last 4 chars for security
            masked = f"****{token[-4:]}" if len(token) > 4 else "****"
            status[label] = f"Authenticated ({masked})"
        else:
            status[label] = "Not configured"
    return status


def is_authenticated(token_type: Optional[str] = None) -> bool:
    """Check if a specific token (or any token) is available."""
    if token_type:
        return get_token(token_type) is not None
    return any(get_token(t) is not None for t in TOKEN_TYPES)
