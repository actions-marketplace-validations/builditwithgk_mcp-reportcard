"""Command-line interface: `mcp-reportcard check`, `mcp-reportcard dump`, `mcp-reportcard rules`."""

from __future__ import annotations

import enum
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import anyio
import typer
from rich.console import Console

try:  # built in from Python 3.11
    BaseExceptionGroup  # noqa: B018
except NameError:  # pragma: no cover
    from exceptiongroup import BaseExceptionGroup  # installed with anyio on 3.10

from mcp_reportcard import __version__, report as render
from mcp_reportcard.analyze import analyze
from mcp_reportcard.loader import LoadError, load_tools_file
from mcp_reportcard.rules import RULES

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="A health check for MCP servers. By Scaleup Solutions (https://scaleup-solutions.in/).",
)
err = Console(stderr=True)

SOURCE_HELP = (
    "What to check: a saved tools/list JSON file, an http(s) URL (Streamable HTTP), "
    'or a command that starts a stdio server, e.g. "python server.py".'
)


class Format(str, enum.Enum):
    terminal = "terminal"
    markdown = "markdown"
    json = "json"


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def _root_cause(exc: BaseException) -> str:
    """Dig through ExceptionGroups and chained errors to the most specific message."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    seen = set()
    while exc.__cause__ is not None and id(exc) not in seen:
        seen.add(id(exc))
        exc = exc.__cause__
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
    msg = str(exc) or type(exc).__name__
    if msg == "Connection closed":
        msg += " (the server exited during startup; rerun with --server-logs to see its output)"
    return f"{type(exc).__name__}: {msg}"


def _is_file(source: str) -> bool:
    try:
        return Path(source).is_file()
    except OSError:
        return False


def _load(source: str) -> tuple[str, list[dict[str, Any]]]:
    if _is_file(source):
        return Path(source).name, load_tools_file(source)
    from mcp_reportcard.connect import fetch_tools

    return anyio.run(fetch_tools, source)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"mcp-reportcard {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True,
                                          help="Show the version and exit.")] = False,
) -> None:
    _utf8_stdout()


@app.command()
def check(
    source: Annotated[str, typer.Argument(help=SOURCE_HELP)],
    fuzz: Annotated[bool, typer.Option("--fuzz", help="Call tools with bad input to test error handling.")] = False,
    allow_unsafe: Annotated[bool, typer.Option(
        "--allow-unsafe",
        help="With --fuzz, also call tools NOT marked read-only. Only use on a test instance.")] = False,
    timeout: Annotated[float, typer.Option(help="Seconds to wait for each fuzz call.")] = 10.0,
    fmt: Annotated[Format, typer.Option("--format", "-f", help="Output format.")] = Format.terminal,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write the report to a file.")] = None,
    fail_under: Annotated[int | None, typer.Option(
        "--fail-under", min=0, max=100, help="Exit with code 1 if the score is below this (for CI).")] = None,
    server_logs: Annotated[bool, typer.Option(
        "--server-logs", help="Show a stdio server's own stderr output (hidden by default).")] = False,
    json_out: Annotated[Path | None, typer.Option(
        "--json-out", help="Also write the JSON report to this file (e.g. for CI alongside Markdown).")] = None,
) -> None:
    """Lint a server's tools, estimate token cost, optionally fuzz, and print a report card."""
    if server_logs:
        from mcp_reportcard.connect import show_server_logs

        show_server_logs(True)
    try:
        name, tools = _load(source)
    except LoadError as e:
        err.print(f"[red]Could not read tools:[/] {e}")
        raise typer.Exit(2) from e
    except Exception as e:
        err.print(f"[red]Could not connect to the server:[/] {_root_cause(e)}")
        raise typer.Exit(2) from e

    outcomes, skipped = [], []
    if fuzz:
        if _is_file(source):
            err.print("[yellow]--fuzz needs a live server; skipping it for a JSON file.[/]")
        else:
            from mcp_reportcard.fuzz import run_fuzz

            if allow_unsafe:
                err.print("[bold yellow]--allow-unsafe: calling tools that may change data.[/]")
            outcomes, skipped = anyio.run(
                lambda: run_fuzz(source, tools, allow_unsafe=allow_unsafe, timeout=timeout))

    result = analyze(tools, server=name, fuzz_outcomes=outcomes, fuzz_skipped=skipped)

    if fmt is Format.terminal and output is None:
        render.print_terminal(result)
    else:
        text = render.to_json(result) if fmt is Format.json else render.to_markdown(result)
        if fmt is Format.terminal:  # terminal format written to a file -> use Markdown
            text = render.to_markdown(result)
        if output:
            output.write_text(text, encoding="utf-8")
            err.print(f"Report written to {output} (grade {result.grade}, score {result.score}).")
        else:
            typer.echo(text)

    if json_out:
        json_out.write_text(render.to_json(result), encoding="utf-8")

    if fail_under is not None and result.score < fail_under:
        err.print(f"[red]Score {result.score} is below --fail-under {fail_under}.[/]")
        raise typer.Exit(1)


@app.command()
def dump(
    source: Annotated[str, typer.Argument(help="URL or stdio command of a live server.")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="File to write.")] = None,
) -> None:
    """Save a live server's tools/list as JSON (to check offline or paste into the web demo)."""
    from mcp_reportcard.connect import fetch_tools

    try:
        _, tools = anyio.run(fetch_tools, source)
    except Exception as e:
        err.print(f"[red]Could not connect to the server:[/] {_root_cause(e)}")
        raise typer.Exit(2) from e
    text = json.dumps({"tools": tools}, indent=2, ensure_ascii=False)
    if output:
        output.write_text(text, encoding="utf-8")
        err.print(f"Wrote {len(tools)} tools to {output}.")
    else:
        typer.echo(text)


@app.command("rules")
def list_rules() -> None:
    """List every check with its ID and severity."""
    from rich.table import Table

    table = Table(title="mcp-reportcard rules")
    table.add_column("ID")
    table.add_column("Severity")
    table.add_column("Check")
    for rid, (sev, title) in RULES.items():
        table.add_row(rid, f"[{render.SEV_STYLE[sev]}]{sev.value}[/]", title)
    Console().print(table)


if __name__ == "__main__":
    app()
