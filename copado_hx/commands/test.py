"""
copado-hx test — Copado Robotic Testing (CRT) commands.

Usage:
  copado-hx test list                                  List available test suites/jobs
  copado-hx test run --suite <suite-id>                Trigger a test suite (suite = jobId)
  copado-hx test run --job <job-id>                    Trigger a specific test job
  copado-hx test status --execution <exec-id>          Poll execution status
  copado-hx test status --execution <exec-id> --watch  Live-poll until done
  copado-hx test results --execution <exec-id>         Retrieve test results
  copado-hx test results --execution <id> --format json

Note: --suite is a convenience alias. In the CRT API, both suites and individual
tests are addressed by a jobId.
"""

from __future__ import annotations

from typing import Optional

import typer

from copado_hx.api import crt
from copado_hx.utils.state import record_action
from copado_hx.utils.suggestions import print_suggestions
from copado_hx.utils.output import (
    smart_output,
    print_success,
    print_error,
    print_info,
    print_warning,
    print_panel,
    console,
    make_table,
)
from copado_hx.utils.polling import poll_until_done, SUCCESS_STATUSES, FAILURE_STATUSES

test_app = typer.Typer(help="Copado Robotic Testing (CRT) — run tests, check results.")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@test_app.command("list")
def list_tests(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="CRT project ID (uses default if omitted)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List available test suites and jobs."""
    try:
        jobs = crt.list_test_jobs(project_id=project)
        smart_output(
            jobs,
            json_mode=json_output,
            title="CRT Test Jobs",
            columns=["jobId", "name", "testCount"],
        )
    except Exception as e:
        print_error(f"Failed to list test jobs: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

@test_app.command("run")
def run_test(
    suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Test suite ID (alias for --job)"),
    job: Optional[str] = typer.Option(None, "--job", "-j", help="CRT job ID to execute"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="CRT project ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll until test execution completes"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Trigger a CRT test suite or job execution."""
    job_id = suite or job
    if not job_id:
        print_error("Specify --suite <id> or --job <id>.")
        raise typer.Exit(1)

    print_info(f"Triggering test job [bold]{job_id}[/bold]...")

    try:
        result = crt.run_test(job_id=job_id, project_id=project)
        exec_id = result.get("executionId") or (result.get("data", {}).get("executionId")) or ""
        print_success(f"Test execution started — Execution: [bold]{exec_id}[/bold]")
        smart_output(result, json_mode=json_output, title="Test Execution Started")
        record_action("test_run", last_execution_id=str(exec_id), last_crt_job_id=str(job_id))
        if not json_output:
            print_suggestions(after_action="test_run")

        if watch and exec_id:
            print_info("Polling for completion... (Ctrl+C to stop)")
            final = poll_until_done(
                fetch_fn=lambda: crt.get_test_status(exec_id, job_id=job_id, project_id=project),
                status_key="status",
                watch=True,
                label=f"Test {job_id}",
            )
            final_status = final.get("status", "Unknown")
            if final_status in SUCCESS_STATUSES:
                print_success(f"Tests completed — {final_status}")
            elif final_status in FAILURE_STATUSES:
                print_error(f"Tests finished with failures — {final_status}")
            smart_output(final, json_mode=json_output, title="Test Execution Result")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to trigger test: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@test_app.command("status")
def test_status(
    execution: str = typer.Option(..., "--execution", "-e", help="Execution ID to check"),
    job_id: str = typer.Option(..., "--job", "-j", help="CRT job ID (required — from test run output)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="CRT project ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Live-poll until done"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Poll the status of a running test execution."""
    try:
        if watch:
            print_info(f"Watching execution [bold]{execution}[/bold]... (Ctrl+C to stop)")
            result = poll_until_done(
                fetch_fn=lambda: crt.get_test_status(execution, job_id=job_id, project_id=project),
                status_key="status",
                watch=True,
                label=f"Execution {execution}",
            )
        else:
            result = crt.get_test_status(execution, job_id=job_id, project_id=project)

        smart_output(result, json_mode=json_output, title=f"Test Status — {execution}")
    except Exception as e:
        print_error(f"Failed to get test status: {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@test_app.command("results")
def test_results(
    execution: str = typer.Option(..., "--execution", "-e", help="Execution ID"),
    job_id: str = typer.Option(..., "--job", "-j", help="CRT job ID (required — from test run output)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="CRT project ID"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table | json | pdf"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON (shortcut for --format json)"),
):
    """Retrieve test results for a completed execution."""
    use_json = json_output or format.lower() == "json"

    try:
        results = crt.get_test_results(execution, job_id=job_id, project_id=project)

        if use_json:
            smart_output(results, json_mode=True)
            return

        # Rich formatted output — this is the QA Intelligence showcase
        total = results.get("totalTests", 0)
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        skipped = results.get("skipped", 0)
        duration = results.get("duration", "N/A")
        pass_rate = results.get("passRate", "N/A")
        test_result = results.get("testResult", "Unknown")

        # Handle in-progress execution
        if test_result == "In Progress":
            print_panel("Execution In Progress",
                        f"[bold yellow]⏳ Test execution [cyan]{execution}[/cyan] is still running.[/bold yellow]\n"
                        f"Select [bold]View test results[/bold] again in a moment.",
                        style="yellow")
            return

        # Summary panel
        result_color = "green" if test_result == "Succeeded" else "red"
        summary_lines = [
            f"[bold]Result:[/bold] [{result_color}]{test_result}[/{result_color}]",
            f"[bold]Total:[/bold] {total}  |  [green]Passed: {passed}[/green]  |  [red]Failed: {failed}[/red]  |  Skipped: {skipped}",
            f"[bold]Pass Rate:[/bold] {pass_rate}",
            f"[bold]Duration:[/bold] {duration}",
        ]
        print_panel(f"Test Results — {execution}", "\n".join(summary_lines),
                     style=result_color)

        # Show failures detail
        failures = results.get("failures", [])
        if failures:
            console.print()
            print_warning(f"{len(failures)} test(s) failed:")
            for f in failures:
                console.print(f"  [red]\u2718[/red] [bold]{f.get('testName', 'Unknown')}[/bold]")
                console.print(f"    Class: {f.get('class', 'N/A')}")
                console.print(f"    Error: {f.get('error', 'N/A')}")

        # Deployment Confidence Score — QA Intelligence WOW feature
        console.print()
        _show_confidence_score(results)

        record_action("test_results",
                      last_execution_id=execution,
                      last_crt_job_id=job_id,
                      last_test_result=test_result)
        print_suggestions(after_action="test_results")

    except Exception as e:
        print_error(f"Failed to get test results: {e}")
        raise typer.Exit(1)


def _show_confidence_score(results: dict) -> None:
    """
    Deployment Confidence Score — your QA differentiator.

    Combines test pass rate with simple heuristics to give a single
    go/no-go number that release engineers can act on.
    """
    total = results.get("totalTests", 0)
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)

    if total == 0:
        return

    # Score calculation (simple but effective for demo)
    test_score = (passed / total) * 60  # Tests are worth 60 points
    no_critical = 20 if failed == 0 else max(0, 20 - (failed * 5))  # Up to 20 for zero failures
    coverage_bonus = 20  # Placeholder — would come from metadata analysis in real impl

    confidence = min(100, int(test_score + no_critical + coverage_bonus))

    # Determine recommendation
    if confidence >= 85:
        rec = "[bold green]SAFE TO DEPLOY[/bold green]"
        risk = "[green]Low[/green]"
        bar_color = "green"
    elif confidence >= 60:
        rec = "[bold yellow]DEPLOY WITH CAUTION[/bold yellow]"
        risk = "[yellow]Medium[/yellow]"
        bar_color = "yellow"
    else:
        rec = "[bold red]DO NOT DEPLOY[/bold red]"
        risk = "[red]High[/red]"
        bar_color = "red"

    # Visual confidence bar
    filled = confidence // 5
    bar = f"[{bar_color}]{'█' * filled}[/{bar_color}]{'░' * (20 - filled)}"

    lines = [
        f"[bold]Score:[/bold] {bar} {confidence}/100",
        f"[bold]CRT Tests:[/bold] {passed}/{total} passed ({results.get('passRate', 'N/A')})",
        f"[bold]Risk Level:[/bold] {risk}",
        f"[bold]Recommendation:[/bold] {rec}",
    ]

    print_panel("Deployment Confidence Score", "\n".join(lines), style=bar_color)
