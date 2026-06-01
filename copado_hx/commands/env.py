"""
copado-hx env — Environment management commands.

Usage:
  copado-hx env list          List pipeline environments
"""

from __future__ import annotations

import typer

from copado_hx.api import cicd
from copado_hx.utils.output import smart_output, print_error
from copado_hx.utils.state import record_action

env_app = typer.Typer(help="Manage Copado pipeline environments.")


@env_app.command("list")
def list_envs(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all pipeline environments."""
    try:
        envs = cicd.list_environments()
        smart_output(
            envs,
            json_mode=json_output,
            title="Environments",
            columns=["name", "platform", "type"],
        )
        record_action("env_list")
    except Exception as e:
        record_action("env_list")
        print_error(f"Failed to list environments: {e}")
        raise typer.Exit(1)
