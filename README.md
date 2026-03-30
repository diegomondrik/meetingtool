# MeetingTool v2

Process Microsoft Teams recordings and generate structured executive reports.
Supports Claude, ChatGPT, and Gemini. Works on Windows, macOS, and Linux.

---

## Requirements

- Python 3.11+
- ffmpeg in PATH
- A paid Claude, ChatGPT, or Gemini account

---

## Installation

### Step 1 — Download MeetingTool

Choose a folder on your computer where you want MeetingTool to live permanently.
This is where the program files go — not your meetings or reports (those go somewhere else, and MeetingTool will ask you where during setup).

Open a terminal in that folder and run:

```bash
git clone https://github.com/diegomondrik/meetingtool.git
cd meetingtool
```

If you've never used `git clone` before: this command downloads MeetingTool into a new subfolder called `meetingtool` inside whichever folder your terminal is currently in. To control where it lands, navigate to your preferred folder first (e.g. `cd C:\Tools` on Windows or `cd ~/Applications` on Mac) before running the command.

### Step 2 — Run the installer

```bash
python mip.py setup
```

The installer will:
- Check that Python, ffmpeg, and required packages are installed (and help you fix anything missing)
- Ask where you want to store your projects and meeting recordings
- Ask which AI tool you use (Claude, ChatGPT, or Gemini)
- Ask your preferred report language (English or Spanish)
- Set everything up automatically

### Step 3 — Create your first project

```bash
python mip.py project new
```

MeetingTool will ask for the client name, project name, and a few preferences.
At the end it prints the instructions you need to configure your AI tool — follow those before analyzing your first meeting.

---

## Quick start

```bash
# Create a project for a new client engagement
python mip.py project new

# Process a meeting — Cowork workflow (Claude Desktop)
python mip.py run --path "~/Documents/MeetingTool/projects/Acme/Q2Analysis/KickoffMeeting_20260330"

# Process a meeting — Web workflow (Claude/ChatGPT/Gemini browser)
python mip.py run --path "..." --web

# Process a long meeting (45+ min) in two-pass web mode
python mip.py run --path "..." --web --two-pass

# Export the approved report to DOCX for client delivery
python mip.py export --path "..."
```

---

## Workflows

### Workflow A — Cowork (Claude Desktop)

For developers using Claude Desktop with the Cowork feature.

1. Place `MeetingName_YYYYMMDD.mp4` and `MeetingName_YYYYMMDD.docx` in the meeting folder
2. Run `mip run --path <folder>` from Cowork
3. Cowork extracts up to 150 frames intelligently, reads transcript + frames, generates `report_YYYYMMDD.md`
4. Review and iterate on the report in Cowork chat
5. Run `mip export --path <folder>` when ready for client delivery

### Workflow B — Web (Claude / ChatGPT / Gemini)

For developers using Claude web, ChatGPT, or Gemini without desktop access.

**Short meetings (< 45 min):**
1. Run `mip run --path <folder> --web`
2. Script selects the 20 best frames and prints an upload checklist
3. Upload transcript + frames to your LLM chat
4. Paste the prompt pack from the terminal output
5. Copy the generated report and save as `report_YYYYMMDD.md`
6. Export when ready: `mip export --path <folder>`

**Long meetings (45+ min) — two-pass mode:**
1. Run `mip run --path <folder> --web --two-pass`
2. **Chat 1:** upload first half transcript + 20 frames → paste Chat 1 prompt pack
3. LLM generates partial analysis + handoff JSON block
4. Run `mip handoff save --path <folder>` → paste the handoff JSON
5. **Chat 2:** upload handoff.json + second half transcript + 20 frames → paste Chat 2 prompt pack
6. LLM generates the complete merged report

---

## Intelligent frame selection

MeetingTool v2 uses a three-signal scoring algorithm instead of v1's brute global diff:

| Signal | Weight | What it detects |
|--------|--------|-----------------|
| Zone-based change | 40% | Localized changes (a number updating in one cell of a dashboard) |
| Edge map delta | 30% | Slide transitions, new text/annotations appearing |
| Temporal coverage | 30% | Guarantees representation from every part of the meeting |

Final score: `(zone × 0.4) + (edge × 0.3) + (temporal × 0.3)`

Frame budgets: 150 for Cowork, 20 per half for web mode.

---

## Report lifecycle

Reports live as `report_YYYYMMDD.md` during analysis and review.
Images are referenced by filename: `[frame_004_t00-14-32.jpg]`

The developer verifies images locally in `imagenes_reunion\` during review.
DOCX export (with embedded images) is generated only when the report is approved:

```bash
mip export --path <meeting_folder>
```

The system recommends DOCX when the report contains more than 3 image references.

---

## Language settings

Report language is configured per project. When the meeting transcript language
differs from the project default, MeetingTool prompts before generating:

```
Meeting transcript: English
Project default: Spanish

Generate the report in:
  [1] Spanish — project default
  [2] English — match the meeting
  [3] Both (two separate files)
```

---

## Folder structure

```
~/Documents/MeetingTool/
├── mip.config.json                    ← global config
├── tools/
│   └── test_meeting.mp4               ← synthetic test fixture
└── projects/
    └── {Client}/
        └── {Project}/
            ├── mip.config.json        ← project config
            └── {MeetingName}_{YYYYMMDD}/
                ├── {MeetingName}_{YYYYMMDD}.mp4
                ├── {MeetingName}_{YYYYMMDD}.docx
                ├── {MeetingName}_{YYYYMMDD}.txt   ← parsed transcript
                ├── report_{YYYYMMDD}.md            ← living report
                ├── report_{YYYYMMDD}.docx          ← on-demand export
                └── imagenes_reunion/
                    ├── frame_001_t00-03-12.jpg
                    └── ...
```

---

## Meeting types

Four base types always available:

| Type | CLI key | Additional report sections |
|------|---------|---------------------------|
| Discovery / Pre-sales | `discovery` | Sales signals, project fit |
| Kickoff / Project start | `kickoff` | Project definition, team structure |
| Status / Progress | `status` | Project status, delta since last meeting |
| Technical / Analysis | `technical` | Technical decisions, visual analysis, dependencies |

Custom types can be added per project in `mip.config.json`.

---

## Privacy

- Video and transcript **never leave your computer automatically**
- All LLM uploads are **manual and explicit** — you control what gets shared
- Each LLM provider has its own data retention policy — review before uploading client content:
  - Claude: https://www.anthropic.com/privacy
  - ChatGPT: https://openai.com/policies/privacy-policy
  - Gemini: https://policies.google.com/privacy
- SharePoint credentials stored in `.env` (never committed — see `.gitignore`)

---

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Tests require Python 3.11+, ffmpeg, opencv-python, and python-docx.

---

## LLM provider data policies

| Provider | Free tier | Paid tier |
|----------|-----------|-----------|
| Claude | May use for training | No training on Pro/Team/Enterprise |
| ChatGPT | May use for training | No training when opted out (Plus+) |
| Gemini | May use for training | Workspace: not used for training |

Always verify current policies before uploading confidential client content.
