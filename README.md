# MeetingTool v3.0

Process Microsoft Teams recordings and generate structured executive reports.
Supports three workflows: automated pipeline (Gemini + Claude API), Cowork
(Claude Desktop), and web (any LLM browser). Works on Windows, macOS, and Linux.

**Documentation:**
- [Installation Guide](docs/installation.html) — step-by-step setup for new machines
- [User Guide](docs/user-guide.html) — workflows, commands, and folder structure reference

---

## Requirements

- Python 3.11+
- ffmpeg in PATH
- For automated pipeline: Anthropic API key + Gemini API key (both have free tiers)

---

## Installation

### Step 1 — Install Python 3.11+

Download from: https://python.org/downloads

> **Windows:** during installation, check **"Add Python to PATH"** before clicking Install.

Verify it worked:
```bash
python --version
```

### Step 2 — Install ffmpeg

ffmpeg is required for video frame extraction. Install it once and MeetingTool will find it automatically.

**Windows:**
1. Go to: https://ffmpeg.org/download.html → Windows → gyan.dev → download the **Release Full** build
2. Extract to `C:\ffmpeg\`
3. Add `C:\ffmpeg\bin` to your system PATH:
   Win + X → System → Advanced system settings → Environment Variables → System Variables → Path → Edit → New → `C:\ffmpeg\bin` → OK
4. Close and reopen your terminal, then verify: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

### Step 3 — Download MeetingTool

Choose a folder on your computer where you want MeetingTool to live permanently.
This is where the program files go — not your meetings or reports (those go somewhere else, and MeetingTool will ask you where during setup).

Open a terminal in that folder and run:

```bash
git clone https://github.com/diegomondrik/meetingtool.git
cd meetingtool
```

If you've never used `git clone` before: this command downloads MeetingTool into a new subfolder called `meetingtool` inside whichever folder your terminal is currently in. To control where it lands, navigate to your preferred folder first (e.g. `cd C:\Tools` on Windows or `cd ~/Applications` on Mac) before running the command.

### Step 4 — Run the installer

```bash
python mip.py setup
```

The installer will:
- Check that Python, ffmpeg, and required packages are installed (and help you fix anything missing)
- Ask where you want to store your projects and meeting recordings
- Ask which AI tool you use (Claude, ChatGPT, or Gemini)
- Ask your preferred report language (English or Spanish)
- Set everything up automatically

### Step 5 — Create your first project

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

# Automated pipeline — Gemini extracts frames, Claude writes the report
python mip.py run --path "<meeting_folder>" --auto

# Cowork workflow — Claude Desktop reads frames + transcript directly
python mip.py run --path "<meeting_folder>"

# Web workflow — uploads checklist for any LLM browser
python mip.py run --path "<meeting_folder>" --web

# Long meeting (45+ min) — two-pass web mode
python mip.py run --path "<meeting_folder>" --web --two-pass

# Export the approved report to DOCX for client delivery
python mip.py export --path "<meeting_folder>"
```

---

## Workflows

### Workflow A — Automated pipeline

Fully hands-off: Gemini extracts visual content from frames, Claude writes the report.

1. Place `MeetingName_YYYYMMDD.mp4` and `MeetingName_YYYYMMDD.docx` in the meeting folder
2. Run: `python mip.py run --path <folder> --auto`
3. MeetingTool extracts frames, sends them to Gemini (vision), calls Claude, writes `report_YYYYMMDD.md`
4. Review the report, iterate if needed
5. Export: `python mip.py export --path <folder>`

**API keys required:** Anthropic + Gemini (both have free tiers).
Get them at [console.anthropic.com](https://console.anthropic.com/settings/keys) and [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
The installer saves them to your system keychain during `mip setup`.

**Gemini free tier limits:** 1,500 requests/day, 40,000 tokens/minute.
For high-volume use, configure a backup key from a separate Google Cloud project:
run `mip setup` again — it will ask for a second Gemini key (optional).
When the primary key hits quota, the backup activates automatically.

**Gemini unavailable?** MeetingTool activates an OCR fallback and continues —
Claude generates the report from transcript only. Report quality is lower without
visual evidence but the pipeline never blocks.

---

### Workflow B — Cowork (Claude Desktop)

For users running Claude Desktop with the Cowork feature.

1. Place `MeetingName_YYYYMMDD.mp4` and `MeetingName_YYYYMMDD.docx` in the meeting folder
2. Run `mip run --path <folder>` from Cowork
3. Cowork extracts up to 150 frames intelligently, reads transcript + frames, generates `report_YYYYMMDD.md`
4. Review and iterate on the report in Cowork chat
5. Run `mip export --path <folder>` when ready for client delivery

### Workflow C — Web (Claude / ChatGPT / Gemini)

For users running Claude web, ChatGPT, or Gemini without desktop access.

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

Five base types always available:

| Type | CLI key | Additional report sections |
|------|---------|---------------------------|
| Discovery / Pre-sales | `discovery` | Sales signals, project fit |
| Kickoff / Project start | `kickoff` | Project definition, team structure |
| Status / Progress | `status` | Project status, delta since last meeting |
| Technical / Analysis | `technical` | Technical decisions, visual analysis, dependencies |
| Training / Enablement | `training` | Training context, comprehension assessment, gaps & follow-up, adoption next steps |

Custom types can be added per project in `mip.config.json`.

---

## Privacy

**Automated pipeline (`--auto`):** frames are sent to Google Gemini and the full transcript is sent to Anthropic Claude. Both happen automatically without manual confirmation. Review their data policies before processing confidential client content.

**Cowork and web workflows:** video and transcript never leave your computer automatically — all LLM uploads are manual and explicit.

Data retention policies:
- Anthropic (Claude): [anthropic.com/privacy](https://www.anthropic.com/privacy)
- Google (Gemini): [policies.google.com/privacy](https://policies.google.com/privacy)
- OpenAI (ChatGPT): [openai.com/policies/privacy-policy](https://openai.com/policies/privacy-policy)

API keys are stored in your system keychain (Windows Credential Manager / macOS Keychain) — never in plain text files.

---

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Tests require Python 3.11+, ffmpeg, scikit-image, pillow, and python-docx.

---

## Building the executable

MeetingTool can be packaged into a standalone Windows executable so it runs on
machines without a Python install.

```powershell
pip install -r requirements.txt
.\build.ps1
```

Output: `dist\MeetingTool\MeetingTool.exe` (onedir bundle — distribute the whole
`dist\MeetingTool\` folder).

**Notes:**
- Verified on **Python 3.13, Windows ARM64, PyInstaller 6.21.0**.
- **ffmpeg is not bundled** — it stays a system dependency. The app detects it
  on PATH and guides installation if missing. Install it on the target machine
  (the first-run setup screen explains how).
- The automated API pipeline (`anthropic`) is **excluded** from the binary; the
  packaged app uses the Cowork / web subscription flow only.
- Config (`mip.config.json`) is written next to `MeetingTool.exe`, so the bundle
  is portable — copy the folder anywhere.

---

## LLM provider data policies

| Provider | Free tier | Paid tier |
|----------|-----------|-----------|
| Claude | May use for training | No training on Pro/Team/Enterprise |
| ChatGPT | May use for training | No training when opted out (Plus+) |
| Gemini | May use for training | Workspace: not used for training |

Always verify current policies before uploading confidential client content.
