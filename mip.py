"""
mip.py — MeetingTool v2.0
=========================
CLI entry point. All commands registered here.

Usage:
    python mip.py setup
    python mip.py project new
    python mip.py run --path <meeting_folder>
    python mip.py run --path <meeting_folder> --web
    python mip.py run --path <meeting_folder> --web --two-pass
    python mip.py export --path <meeting_folder>
    python mip.py handoff save --path <meeting_folder>
"""

import sys
import click
from pathlib import Path

# Verify Python version at import time
if sys.version_info < (3, 11):
    print(f"ERROR: MeetingTool requires Python 3.11+. Found: {sys.version}")
    print("Download Python 3.11+ from https://python.org")
    sys.exit(1)


@click.group()
@click.version_option(version="2.0.0", prog_name="MeetingTool")
def cli():
    """MeetingTool v2 — Meeting Intelligence Platform

    Process Teams recordings and generate executive reports.
    Supports Claude, ChatGPT, and Gemini web interfaces.

    \b
    Quick start:
        mip setup              — first-time setup (run once per machine)
        mip project new        — create a new client project
        mip run --path <dir>   — process a meeting (Cowork workflow)
        mip run --path <dir> --web  — process a meeting (web workflow)
        mip export --path <dir>     — export report to DOCX
    """
    pass


# ── Setup ────────────────────────────────────────────────────────────────────

@cli.command()
def setup():
    """First-time setup. Run once per machine."""
    from tools.installer import run_setup
    run_setup()


# ── Project management ───────────────────────────────────────────────────────

@cli.group()
def project():
    """Manage client projects."""
    pass


@project.command("new")
def project_new():
    """Create a new project for a client engagement."""
    from tools.project import run_project_new
    run_project_new()


@project.command("list")
def project_list():
    """List all existing projects."""
    from tools.project import run_project_list
    run_project_list()


# ── Meeting analysis ─────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--path", "meeting_folder",
    required=True,
    type=click.Path(file_okay=False),
    help="Meeting folder containing MP4 and DOCX transcript.",
)
@click.option(
    "--web",
    is_flag=True,
    default=False,
    help="Web workflow mode. Selects top 20 frames and prints upload checklist.",
)
@click.option(
    "--two-pass",
    is_flag=True,
    default=False,
    help="Two-pass web mode for meetings >= 45 min. Splits transcript and frames.",
)
@click.option(
    "--single-pass",
    is_flag=True,
    default=False,
    help="Force single-pass even for long meetings (overrides two-pass recommendation).",
)
@click.option(
    "--max-frames",
    default=None,
    type=int,
    help="Override default frame budget (150 for Cowork, 20 for web).",
)
def run(meeting_folder, web, two_pass, single_pass, max_frames):
    """Process a meeting — extract frames and prepare for LLM analysis."""
    from tools.runner import run_meeting
    run_meeting(
        meeting_folder=Path(meeting_folder),
        web_mode=web,
        two_pass=two_pass,
        single_pass=single_pass,
        max_frames_override=max_frames,
    )


# ── Export ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--path", "meeting_folder",
    required=True,
    type=click.Path(file_okay=False),
    help="Meeting folder containing report.md and imagenes_reunion\\.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["docx", "md", "both"], case_sensitive=False),
    default=None,
    help="Output format. If not specified, system will recommend based on content.",
)
def export(meeting_folder, output_format):
    """Export report.md to DOCX with embedded images."""
    from tools.exporter import run_export
    run_export(
        meeting_folder=Path(meeting_folder),
        output_format=output_format,
    )


# ── Handoff (two-pass) ───────────────────────────────────────────────────────

@cli.group()
def handoff():
    """Manage two-pass handoff blocks."""
    pass


@handoff.command("save")
@click.option(
    "--path", "meeting_folder",
    required=True,
    type=click.Path(file_okay=False),
    help="Meeting folder where handoff JSON will be saved.",
)
def handoff_save(meeting_folder):
    """Save a handoff JSON block from Chat 1 (paste when prompted)."""
    from tools.runner import save_handoff
    save_handoff(meeting_folder=Path(meeting_folder))


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
