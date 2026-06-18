"""
tools/claude_client.py — MeetingTool v2.5
==========================================
Calls Claude 3.5 Sonnet to generate the meeting report.

Takes the transcript text and Gemini's visual_evidence as a text-only prompt.
Applies prompt caching (cache_control ephemeral) on the BASE_SYSTEM block
to reduce cost on consecutive runs within the same session.

Cost model:
  - Cached system prompt tokens: ~$0.30/M (vs $3.00/M uncached)
  - No vision tokens — all images were processed by Gemini upstream
"""

import logging
from pathlib import Path

import anthropic

from tools.prompt_generator import BASE_SYSTEM, STANDARD_SECTIONS, MEETING_TYPE_SECTIONS
from tools.api_config import get_anthropic_key

log = logging.getLogger("claude_client")

CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


def generate_report(
    transcript_text: str,
    visual_evidence: str,
    config: dict,
    meeting_type: str | None = None,
    report_language: str = "english",
    api_key: str | None = None,
    _client=None,
) -> str:
    """
    Call Claude 3.5 Sonnet to produce the meeting report markdown.

    Args:
        transcript_text:  Full transcript as plain text.
        visual_evidence:  Structured text output from Gemini vision stage.
        config:           Project config dict (client, project, etc.).
        meeting_type:     One of: discovery, kickoff, status, technical, training, or None.
        report_language:  'english' or 'spanish'.
        api_key:          Anthropic API key. If None, loaded from api_config.

    Returns:
        Report content as a Markdown string.
    """
    if _client is not None:
        client = _client
    else:
        if api_key is None:
            api_key = get_anthropic_key()
        client = anthropic.Anthropic(api_key=api_key)

    # ── System prompt (cached) ────────────────────────────────────────────────
    # BASE_SYSTEM + STANDARD_SECTIONS form the stable, cacheable block.
    # Meeting-type sections and language instructions are appended but still
    # included in the cache — they change rarely within a project.

    type_section = MEETING_TYPE_SECTIONS.get(meeting_type or "", "")
    language_instruction = (
        "Generate the entire report in Spanish."
        if report_language == "spanish"
        else "Generate the entire report in English."
    )

    system_content = "\n\n".join(filter(None, [
        BASE_SYSTEM.strip(),
        STANDARD_SECTIONS.strip(),
        type_section.strip() if type_section else "",
        language_instruction,
    ]))

    # ── User message ──────────────────────────────────────────────────────────

    client_name  = config.get("client", "")
    project_name = config.get("project", "")
    context_line = f"Client: {client_name} | Project: {project_name}" if client_name else ""

    visual_block = (
        f"## VISUAL EVIDENCE (extracted by Gemini from meeting frames)\n\n{visual_evidence}"
        if visual_evidence.strip()
        else "## VISUAL EVIDENCE\n\nNo visual evidence available for this meeting."
    )

    user_content = "\n\n".join(filter(None, [
        context_line,
        "## MEETING TRANSCRIPT\n\n" + transcript_text.strip(),
        visual_block,
        "Generate the complete meeting report now.",
    ]))

    log.info(
        f"Calling Claude {CLAUDE_MODEL} — "
        f"system: {len(system_content)} chars, user: {len(user_content)} chars"
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": system_content,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": user_content}
        ],
    )

    report_md = response.content[0].text

    usage = response.usage
    log.info(
        f"Claude response: {len(report_md)} chars — "
        f"input {usage.input_tokens} tokens "
        f"(cache_read: {getattr(usage, 'cache_read_input_tokens', 0)}, "
        f"cache_write: {getattr(usage, 'cache_creation_input_tokens', 0)})"
    )

    return report_md


def write_report(report_md: str, meeting_folder: Path, date_str: str) -> Path:
    """Write the report markdown to the meeting folder. Returns the file path."""
    out_path = meeting_folder / f"report_{date_str}.md"
    out_path.write_text(report_md, encoding="utf-8")
    log.info(f"Report written: {out_path.name} ({len(report_md)} chars)")
    return out_path
