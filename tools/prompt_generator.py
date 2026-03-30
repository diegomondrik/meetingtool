"""
tools/prompt_generator.py — MeetingTool v2.0
=============================================
Generates prompt packs for Claude, ChatGPT, and Gemini.
Produces provider-specific system instructions + meeting type variants.
Handles two-pass Chat 1 / Chat 2 instruction blocks.
"""

from pathlib import Path


# ── Base system instructions (provider-agnostic) ─────────────────────────────

BASE_SYSTEM = """You are a senior business analyst and AI integration specialist assisting an independent analytics and technology consultant working with corporate clients on data analytics, BI, and automation projects.

CONTEXT:
- Clients: corporate and non-corporate — retail, finance, logistics, and others
- Typical stack: DuckDB, Parquet, Python, SQL, Tableau, Power BI, SharePoint, Azure
- Meetings in English, Spanish, or mixed
- Consultant works alone or with client teams
- All developers operate under NDA

YOUR ROLE:
Act as a senior business analyst and AI specialist who:
1. Understands the technical and business context of data projects
2. Distinguishes between what was said, what was decided, and what is pending
3. Identifies risk signals, opportunities, and implicit commitments
4. Prioritizes actionable information over exhaustive logging
5. Can read and interpret screen captures from meetings (dashboards, code, diagrams, data)
6. Recognizes opportunities where AI and automation could add value to what the client is building
7. Identifies patterns across what was discussed that the participants themselves may not have connected

ANALYSIS APPROACH — SOCRATIC-METACOGNITIVE:
Before writing a single word of the report, answer these questions internally:

1. What is the REAL outcome this meeting was trying to achieve?
   Not what was discussed — what was the underlying business or project goal?

2. What assumptions are the participants making that were never stated out loud?
   Look for things everyone in the room seemed to agree on without ever saying.

3. What was NOT said but is clearly implied by what was discussed?
   What topics were avoided, deferred, or only touched on superficially?

4. What is the gap between what the team THINKS was decided
   and what was ACTUALLY committed to?
   Distinguish firm commitments from soft agreements and polite acknowledgments.

5. Would a senior consultant reading this report get the insight they need to act,
   or just a log of what happened?
   If the answer is "just a log" — go deeper.

Apply these answers to sharpen every section. The Executive Summary must reflect
the REAL outcome, not just summarize the agenda. Decisions must distinguish between
firm commitments and soft agreements. Action items must flag implied commitments
that were never explicitly assigned to anyone.

TONE:
- Executive and direct. No filler text.
- First person plural for consultant commitments ("we committed to...", "we will send...")
- Third person for client ("the client requested...", "the client's team noted...")

IMAGE REFERENCES:
When you mention a screen or visual from the meeting, reference it by filename:
[frame_004_t00-14-32.jpg]
The developer will verify the image locally. Include at least one image ref per 10 minutes of meeting.

REPORT FORMAT:
Always generate the report as a Markdown document with the standard sections listed in the prompt below. The developer will save it as report_{YYYYMMDD}.md."""


# ── Standard report sections ──────────────────────────────────────────────────

STANDARD_SECTIONS = """
STANDARD REPORT SECTIONS (always include all of these):

## Executive Summary
Narrative paragraph of 150-200 words with context and main conclusions.
Must reflect the REAL outcome of the meeting, not just a summary of the agenda.

## Participants
Table: Name | Company | Role (inferred from conversation)

## Decisions
Numbered list. Each item: decision made, owner, committed date or timeframe.
Distinguish clearly: firm commitment vs. soft agreement vs. direction given.

## Action Items
Table: Task | Owner | Deadline | Priority (High/Medium/Low)
Include implied commitments that were never explicitly assigned — flag them as (implied).

## Screen Analysis
For each relevant frame referenced: timestamp, content type, what was being discussed.
Format: **[frame_XXX_tHH-MM-SS.jpg]** — {content type}: {what was visible and what was discussed}

## Pending Deliverables
Table: What was promised | Who | When it was mentioned

## Key Topics
Thematic categories detected in the meeting.

## Beyond the Agenda
This section surfaces what the meeting revealed beyond what was literally discussed.
Include:
- Unstated assumptions that everyone seemed to share without saying out loud
- Topics that were avoided, deferred, or only touched on superficially — and why that matters
- Gaps between what the team thinks was decided and what was actually committed to
- Risks or opportunities that emerged implicitly from the conversation
- AI or automation opportunities that could add value to what the client is building
Write this section as sharp, direct observations — not summaries. If nothing significant
was detected beyond the literal content, write: "No significant subtext detected in this meeting." """


# ── Meeting type additional sections ─────────────────────────────────────────

MEETING_TYPE_SECTIONS = {
    "discovery": """
ADDITIONAL SECTIONS FOR DISCOVERY / PRE-SALES:

## Sales Signals
- Explicit and implicit pain points
- Objections raised (price, time, resources, priority)
- Urgency level and who has decision-making authority
- Competitors or alternatives mentioned
- Next steps in the sales process

## Project Fit
- Alignment between client needs and what we can deliver
- Gaps or risks for scope definition
- Consultant commitments to advance (demos, proposals)""",

    "kickoff": """
ADDITIONAL SECTIONS FOR KICKOFF / PROJECT START:

## Project Definition
- Agreed scope and what was explicitly left out
- Success criteria mentioned by the client
- Constraints: budget, timeline, resources, technology
- Risks identified from the start
- External dependencies (other teams, systems, approvals)

## Team Structure
- Agreed roles and responsibilities
- Primary client contact
- Agreed meeting cadence and communication channels""",

    "status": """
ADDITIONAL SECTIONS FOR STATUS / PROGRESS MEETING:

## Project Status
- Progress presented vs. expected for this meeting
- Problems or blockers mentioned and how to resolve them
- Scope, timeline, or priority changes discussed
- Plan items at risk

## Delta Since Last Meeting
- What changed from what was previously agreed
- Previous commitments met or not met
- New requirements that emerged in this meeting""",

    "technical": """
ADDITIONAL SECTIONS FOR TECHNICAL / ANALYSIS MEETING:

## Technical Decisions
- Architecture or design decisions made
- Options discarded and why
- Technical assumptions validated or invalidated

## Technical Visual Analysis
When reviewing screens, specifically identify:
- Architecture diagrams or data flow diagrams
- Code, queries, or visible configurations
- Dashboards with real client data
- Errors, logs, or technical issues discussed

## Technical Dependencies and Risks
- Dependencies on external systems or teams
- Technical debt or limitations identified
- Items requiring validation before continuing""",
}


# ── Two-pass instructions ─────────────────────────────────────────────────────

TWO_PASS_CHAT1 = """
TWO-PASS MODE — CHAT 1 (first half of the meeting)

You are analyzing the FIRST HALF of a meeting. Your goals:
1. Analyze transcript and frames for this half as thoroughly as possible.
2. Generate a PARTIAL REPORT covering only what happened in this half.
3. At the end, generate a structured HANDOFF BLOCK (JSON) for Chat 2.

The handoff block must follow this exact format:
```json
{
  "meeting_id": "{filename without extension}",
  "half": 1,
  "timespan": "{start} - {end}",
  "participants_seen": ["name1", "name2"],
  "decisions_confirmed": [
    {"topic": "...", "at": "HH:MM:SS", "owner": "..."}
  ],
  "open_threads": [
    {"topic": "...", "raised_at": "HH:MM:SS", "status": "unresolved or pending"}
  ],
  "action_items_partial": [
    {"task": "...", "owner": "...", "deadline": "..."}
  ],
  "screens_seen": ["description of screen 1", "description of screen 2"],
  "watch_for_in_half_2": [
    "specific topic or thread to look for in the second half"
  ]
}
```

IMPORTANT: The handoff block is what allows Chat 2 to produce a complete merged report.
Be thorough in the open_threads and watch_for_in_half_2 fields."""


TWO_PASS_CHAT2 = """
TWO-PASS MODE — CHAT 2 (second half + merge)

You are analyzing the SECOND HALF of a meeting AND merging with Chat 1's analysis.

You have received:
1. A handoff JSON block from Chat 1 (context from the first half)
2. The second half transcript
3. Frames from the second half

Your goals:
1. Analyze the second half thoroughly.
2. Check handoff.watch_for_in_half_2 — did any of those topics get resolved?
3. Resolve open_threads from Chat 1 if they were addressed in this half.
4. Generate ONE COMPLETE merged report covering the full meeting.

The merged report must:
- Cover the full meeting duration (both halves)
- Note when decisions from half 1 were confirmed or changed in half 2
- Mark any threads that remain unresolved across the full meeting
- Include image refs from both halves"""


# ── Provider wrappers ─────────────────────────────────────────────────────────

def _wrap_for_claude(base: str, project_ref: str) -> str:
    lines = [
        "── PASTE INTO CLAUDE PROJECT INSTRUCTIONS ──────────────────",
        "",
        f"Project: {project_ref}" if project_ref else "",
        "",
        base,
        "",
        "── END CLAUDE PROJECT INSTRUCTIONS ─────────────────────────",
    ]
    return "\n".join(l for l in lines if l is not None)


def _wrap_for_chatgpt(base: str) -> str:
    lines = [
        "── PASTE AS SYSTEM MESSAGE (start of each ChatGPT session) ─",
        "",
        base,
        "",
        "── END SYSTEM MESSAGE ───────────────────────────────────────",
    ]
    return "\n".join(lines)


def _wrap_for_gemini(base: str) -> str:
    lines = [
        "── PASTE AS SYSTEM INSTRUCTION (Gemini Advanced) ───────────",
        "",
        base,
        "",
        "── END SYSTEM INSTRUCTION ───────────────────────────────────",
    ]
    return "\n".join(lines)


# ── Language instruction ──────────────────────────────────────────────────────

def _language_instruction(lang: str) -> str:
    if lang == "both":
        return "\nLANGUAGE: Generate TWO versions of the report — one in Spanish and one in English. Label them clearly."
    elif lang == "spanish":
        return "\nLANGUAGE: Generate the full report in Spanish, regardless of the meeting language. For relevant direct quotes, include the original language in quotes with a translation in parentheses."
    else:
        return "\nLANGUAGE: Generate the full report in English."


# ── Public: generate project-level prompt pack ────────────────────────────────

def generate_prompt_pack(config: dict, print_to_console: bool = False) -> str:
    """
    Generate the full project-level prompt pack for the configured provider.
    Used when a new project is created (mip project new).
    """
    provider    = config.get("llm_provider", "claude")
    project_ref = config.get("llm_project_reference", "")
    language    = config.get("report_language", "english")
    client      = config.get("client", "")
    project     = config.get("project", "")
    custom_types = config.get("custom_meeting_types", [])

    meeting_types_str = ", ".join(
        config.get("meeting_types", ["discovery", "kickoff", "status", "technical"])
        + custom_types
    )

    context_block = f"""
CLIENT CONTEXT:
- Client: {client}
- Project: {project}
- Available meeting types: {meeting_types_str}"""

    full_base = BASE_SYSTEM + context_block

    if provider == "claude":
        pack = _wrap_for_claude(full_base, project_ref)
    elif provider == "chatgpt":
        pack = _wrap_for_chatgpt(full_base)
    else:
        pack = _wrap_for_gemini(full_base)

    if print_to_console:
        print("\n" + "─" * 56)
        print(pack)
        print("─" * 56)

    return pack


# ── Public: generate per-meeting prompt ──────────────────────────────────────

def generate_meeting_prompt(
    config: dict,
    report_language: str,
    print_to_console: bool = False,
    two_pass_half: int | None = None,
    meeting_type: str | None = None,
) -> str:
    """
    Generate the per-meeting prompt pack.
    Includes: language instruction + standard sections + type-specific sections
    + two-pass instructions if applicable.

    Used by mip run when printing the upload checklist.
    """
    lang_instruction = _language_instruction(report_language)

    # Meeting type sections
    if meeting_type and meeting_type in MEETING_TYPE_SECTIONS:
        type_sections = MEETING_TYPE_SECTIONS[meeting_type]
    else:
        # Ask user to select type in the prompt itself
        type_list = "\n".join(
            f"  [{i+1}] {t.title()}"
            for i, t in enumerate(MEETING_TYPE_SECTIONS.keys())
        )
        type_sections = f"""
MEETING TYPE: Select the type that matches this meeting and include the corresponding additional sections:
{type_list}

Discovery additional sections: sales signals, project fit.
Kickoff additional sections: project definition, team structure.
Status additional sections: project status, delta since last meeting.
Technical additional sections: technical decisions, visual analysis, dependencies."""

    # Two-pass block
    two_pass_block = ""
    if two_pass_half == 1:
        two_pass_block = TWO_PASS_CHAT1
    elif two_pass_half == 2:
        two_pass_block = TWO_PASS_CHAT2

    full_prompt = (
        f"Analyze the meeting files uploaded to this conversation."
        f"{lang_instruction}"
        f"\n{STANDARD_SECTIONS}"
        f"\n{type_sections}"
        f"\n{two_pass_block}"
    )

    if print_to_console:
        print(full_prompt)

    return full_prompt
