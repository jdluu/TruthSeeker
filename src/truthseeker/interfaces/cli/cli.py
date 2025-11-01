"""Command-line interface for TruthSeeker fact-checking."""

import asyncio
import json
import os
import sys
from typing import Optional

# Set UTF-8 encoding for Windows compatibility
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ...application.fact_checker import FactCheckerService
from ...config.settings import get_settings
from ...domain.models import AnalysisResult, Verdict
from ...infrastructure.http.client import get_async_client
from ...infrastructure.llm.client import LLMClient
from ...infrastructure.llm.parser import LLMResponseParser
from ...infrastructure.search.brave_client import BraveSearchClient

# Configure console for beautiful output
console = Console(force_terminal=True, legacy_windows=False)


def _create_fact_checker_service() -> FactCheckerService:
    """Create and configure fact-checker service with dependency injection."""
    settings = get_settings()
    http_client = get_async_client(settings.http_timeout_seconds)

    search_client = BraveSearchClient(
        api_key=settings.brave_api_key,
        http_client=http_client,
        cache_ttl=settings.search_cache_ttl,
    )

    llm_client = LLMClient(
        api_key=settings.deepseek_api_key,
        model=settings.llm_model,
    )

    response_parser = LLMResponseParser()

    return FactCheckerService(
        search_client=search_client,
        llm_client=llm_client,
        response_parser=response_parser,
    )


def _get_verdict_style(verdict: Verdict) -> tuple[str, str]:
    """Get color and icon for verdict.

    Args:
        verdict: The verdict enum value.

    Returns:
        Tuple of (color, icon/symbol).
    """
    styles = {
        Verdict.TRUE: ("green", "[OK]"),
        Verdict.MOSTLY_TRUE: ("bright_green", "[~]"),
        Verdict.PARTIALLY_TRUE: ("yellow", "[=]"),
        Verdict.MOSTLY_FALSE: ("bright_red", "[~]"),
        Verdict.FALSE: ("red", "[X]"),
        Verdict.UNVERIFIABLE: ("dim white", "[?]"),
    }
    return styles.get(verdict, ("white", "[?]"))


def _print_header(statement: str) -> None:
    """Print a beautiful header for the fact-check.

    Args:
        statement: The statement being fact-checked.
    """
    header = Panel(
        Text(statement, style="bold bright_white"),
        title="[bold cyan]Fact-Checking Statement[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(header)
    console.print()


def _print_result(result: AnalysisResult, json_output: bool = False) -> None:
    """Print fact-checking result to console with beautiful formatting.

    Args:
        result: AnalysisResult to print.
        json_output: If True, output as JSON. Otherwise, print formatted text.
    """
    if json_output:
        output = {
            "verdict": result.verdict.value,
            "explanation": result.explanation,
            "context": result.context,
            "references": [
                {"title": ref.title, "url": str(ref.url)}
                for ref in result.references
            ],
            "search_time": result.search_time,
            "analysis_time": result.analysis_time,
            "total_time": result.search_time + result.analysis_time,
        }
        console.print_json(json.dumps(output, indent=2))
        return

    # Get verdict styling
    color, icon = _get_verdict_style(result.verdict)

    # Verdict Panel
    verdict_text = Text()
    verdict_text.append(f"{icon} ", style=f"bold {color}")
    verdict_text.append(
        result.verdict.value.replace("_", " ").title(), style=f"bold {color}"
    )

    verdict_panel = Panel(
        verdict_text,
        border_style=color,
        padding=(0, 2),
    )
    console.print(verdict_panel)
    console.print()

    # Explanation Panel
    if result.explanation:
        explanation_panel = Panel(
            Markdown(result.explanation),
            title="[bold]Explanation[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
        console.print(explanation_panel)
        console.print()

    # Context Panel (if available)
    if result.context:
        context_panel = Panel(
            Markdown(result.context),
            title="[bold]Additional Context[/bold]",
            border_style="dim blue",
            padding=(1, 2),
        )
        console.print(context_panel)
        console.print()

    # References Table
    if result.references:
        ref_table = Table(
            title="[bold]References[/bold]",
            show_header=True,
            header_style="bold magenta",
            border_style="magenta",
            padding=(0, 1),
        )
        ref_table.add_column("#", style="dim", width=3, justify="right")
        ref_table.add_column("Title", style="cyan", no_wrap=False)
        ref_table.add_column("URL", style="dim blue", overflow="fold")

        for i, ref in enumerate(result.references, 1):
            ref_table.add_row(
                str(i),
                ref.title,
                str(ref.url),
            )

        console.print(ref_table)
        console.print()

    # Timings Table
    total_time = result.search_time + result.analysis_time
    timing_table = Table(
        title="[bold]Performance Metrics[/bold]",
        show_header=True,
        header_style="bold yellow",
        border_style="yellow",
        padding=(0, 1),
        box=None,
    )
    timing_table.add_column("Metric", style="bright_white")
    timing_table.add_column("Time", style="bright_cyan", justify="right")

    timing_table.add_row("Search", f"{result.search_time:.2f}s")
    timing_table.add_row("Analysis", f"{result.analysis_time:.2f}s")
    timing_table.add_row("[bold]Total[/bold]", f"[bold]{total_time:.2f}s[/bold]")

    console.print(timing_table)


async def _fact_check_statement(statement: str, json_output: bool = False) -> int:
    """Fact-check a statement and print results.

    Args:
        statement: Statement to fact-check.
        json_output: If True, output as JSON.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        service = _create_fact_checker_service()

        if not json_output:
            _print_header(statement)
            
            # Use streaming for better UX
            from rich.live import Live
            from rich.status import Status
            
            status_message = "[cyan]Initializing...[/cyan]"
            with Live(Status(status_message, spinner="dots"), console=console, refresh_per_second=4) as live:
                def status_callback(msg: str) -> None:
                    """Update status during fact-checking."""
                    nonlocal status_message
                    status_map = {
                        "Analyzing...": "[yellow]Analyzing statement...[/yellow]",
                        "Searching for evidence...": "[cyan]Searching the web for evidence...[/cyan]",
                    }
                    status_message = status_map.get(msg, f"[cyan]{msg}[/cyan]")
                    live.update(Status(status_message, spinner="dots"))
                
                result = await service.fact_check(statement, stream_callback=status_callback)
        else:
            console.print(f"[dim]Fact-checking: {statement}[/dim]")
            console.print("[dim]Searching and analyzing...[/dim]")
            result = await service.fact_check(statement)

        _print_result(result, json_output=json_output)

        return 0
    except Exception as e:
        error_panel = Panel(
            f"[red]Error:[/red] {str(e)}",
            title="[bold red]Error[/bold red]",
            border_style="red",
        )
        console.print(error_panel)
        if json_output:
            console.print_json(json.dumps({"error": str(e)}, indent=2))
        return 1


async def _run_test() -> int:
    """Run a test fact-check with a predefined statement.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    test_statement = "The Earth is approximately 4.5 billion years old."
    test_panel = Panel(
        Text(test_statement, style="bold bright_white"),
        title="[bold bright_green]Test Mode[/bold bright_green]",
        border_style="bright_green",
        padding=(1, 2),
    )
    console.print(test_panel)
    console.print()
    return await _fact_check_statement(test_statement, json_output=False)


def _print_help() -> None:
    """Print beautiful help message."""
    help_content = Text()
    help_content.append("TruthSeeker CLI", style="bold cyan")
    help_content.append(" - AI-Powered Fact Checker\n\n", style="white")

    help_content.append("Usage:\n", style="bold")
    help_content.append("  ", style="dim")
    help_content.append("truthseeker", style="cyan")
    help_content.append(" <statement>", style="yellow")
    help_content.append("          Fact-check a statement\n", style="dim")
    help_content.append("  ", style="dim")
    help_content.append("truthseeker", style="cyan")
    help_content.append(" --test", style="yellow")
    help_content.append("               Run a test fact-check\n", style="dim")
    help_content.append("  ", style="dim")
    help_content.append("truthseeker", style="cyan")
    help_content.append(" --json <statement>", style="yellow")
    help_content.append("   Output results as JSON\n\n", style="dim")

    help_content.append("Examples:\n", style="bold")
    help_content.append('  truthseeker "The capital of France is Paris"\n', style="dim")
    help_content.append("  truthseeker --test\n", style="dim")
    help_content.append('  truthseeker --json "Python was created in 1991"\n\n', style="dim")

    help_content.append("Environment Variables:\n", style="bold")
    help_content.append("  DEEPSEEK_API_KEY", style="yellow")
    help_content.append("    DeepSeek API key (required)\n", style="dim")
    help_content.append("  BRAVE_API_KEY", style="yellow")
    help_content.append("       Brave Search API key (required)\n", style="dim")

    help_panel = Panel(
        help_content,
        title="[bold bright_blue]Help[/bold bright_blue]",
        border_style="bright_blue",
        padding=(1, 2),
    )
    console.print(help_panel)


def main() -> int:
    """Main CLI entry point.

    Usage:
        truthseeker <statement>     # Fact-check a statement
        truthseeker --test          # Run test fact-check
        truthseeker --json <stmt>   # Output as JSON
        truthseeker --help          # Show help

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        _print_help()
        return 0

    if args[0] == "--test":
        return asyncio.run(_run_test())

    json_output = False
    if args[0] == "--json":
        json_output = True
        if len(args) < 2:
            error_panel = Panel(
                "[red]Error:[/red] --json requires a statement",
                title="[bold red]Error[/bold red]",
                border_style="red",
            )
            console.print(error_panel)
            return 1
        statement = " ".join(args[1:])
    else:
        statement = " ".join(args)

    if not statement.strip():
        error_panel = Panel(
            "[red]Error:[/red] Statement cannot be empty",
            title="[bold red]Error[/bold red]",
            border_style="red",
        )
        console.print(error_panel)
        return 1

    return asyncio.run(_fact_check_statement(statement, json_output=json_output))


if __name__ == "__main__":
    sys.exit(main())
