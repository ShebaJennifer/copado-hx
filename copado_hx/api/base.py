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


class AuthExpiredError(Exception):
    """Raised when auth token is expired or invalid (401/403)."""

    def __init__(self, message: str = "Authentication token expired or invalid"):
        self.message = message
        super().__init__(message)


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
            # Detect auth errors (401/403) and raise specific exception
            if resp.status_code == 401 or resp.status_code == 403:
                raise AuthExpiredError(
                    "Authentication token expired or invalid. "
                    "Run 'copado-hx auth refresh-sf' to refresh Salesforce token."
                )
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

    def patch(self, path: str, json_body: Optional[dict] = None) -> Any:
        try:
            resp = httpx.patch(
                self._url(path),
                headers=self.headers,
                json=json_body,
                timeout=self.timeout,
            )
            return self._handle_response(resp)
        except httpx.RequestError as e:
            print_error(f"Network error: {e}")
            raise CopadoAPIError(0, f"Network error: {e}")


class SalesforceClient(BaseClient):
    """Salesforce REST API client with SOQL query support for Copado CI/CD."""

    def __init__(self, instance_url: str, session_token: str, timeout: int = 60):
        # Salesforce REST API base: /services/data/vXX.0
        base_url = f"{instance_url.rstrip('/')}/services/data/v62.0"
        headers = {
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        super().__init__(base_url=base_url, headers=headers, timeout=timeout)
        self.instance_url = instance_url.rstrip("/")

    def query(self, soql: str) -> list[dict]:
        """Execute a SOQL query and return the list of records."""
        import urllib.parse
        encoded = urllib.parse.quote(soql)
        result = self.get(f"/query?q={encoded}")
        if isinstance(result, dict):
            return result.get("records", [])
        return []

    def query_one(self, soql: str) -> Optional[dict]:
        """Execute a SOQL query and return the first record or None."""
        records = self.query(soql)
        return records[0] if records else None

    def tooling_query(self, soql: str) -> list[dict]:
        """Execute a Tooling API SOQL query and return the list of records."""
        import urllib.parse
        encoded = urllib.parse.quote(soql)
        result = self.get(f"/tooling/query?q={encoded}")
        if isinstance(result, dict):
            return result.get("records", [])
        return []

    def apexrest(self, path: str, method: str = "GET", json_body: Optional[dict] = None) -> Any:
        """Call a Copado Apex REST endpoint (e.g. /services/apexrest/copado/v1/...)."""
        url = f"{self.instance_url}/services/apexrest/{path.lstrip('/')}"
        try:
            if method.upper() == "GET":
                resp = httpx.get(url, headers=self.headers, timeout=self.timeout)
            else:
                resp = httpx.post(url, headers=self.headers, json=json_body, timeout=self.timeout)
            return self._handle_response(resp)
        except httpx.RequestError as e:
            print_error(f"Network error: {e}")
            raise CopadoAPIError(0, f"Network error: {e}")
