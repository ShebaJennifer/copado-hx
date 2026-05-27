"""
Base HTTP client shared by all Copado API clients.

Handles:
  - Common headers (auth tokens)
  - Error handling with human-friendly messages
  - JSON response parsing
  - Timeout configuration
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from copado_hx.utils.output import print_error


class CopadoAPIError(Exception):
    """Raised when a Copado API call returns an error."""

    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"[{status_code}] {message}")


class BaseClient:
    """Thin wrapper around httpx for Copado API calls."""

    def __init__(self, base_url: str, headers: Optional[dict] = None, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _handle_response(self, resp: httpx.Response) -> Any:
        """Parse response or raise a clear error."""
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("message") or body.get("error") or str(body)
            except Exception:
                msg = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
            raise CopadoAPIError(resp.status_code, msg)
        if resp.status_code == 204:
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        try:
            resp = httpx.get(
                self._url(path),
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )
            return self._handle_response(resp)
        except httpx.RequestError as e:
            print_error(f"Network error: {e}")
            raise CopadoAPIError(0, f"Network error: {e}")

    def post(self, path: str, json_body: Optional[dict] = None) -> Any:
        try:
            resp = httpx.post(
                self._url(path),
                headers=self.headers,
                json=json_body,
                timeout=self.timeout,
            )
            return self._handle_response(resp)
        except httpx.RequestError as e:
            print_error(f"Network error: {e}")
            raise CopadoAPIError(0, f"Network error: {e}")
