"""
tools/runner.py — MeetingTool v2.0
====================================
Orchestrates the meeting analysis workflows:
  - Workflow A: Cowork (full frame budget, direct analysis)
  - Workflow B standard: web, < 45 min (20 frames, upload checklist)
  - Workflow B two-pass: web, >= 45 min (20 frames per half, handoff JSON)

Handles language detection and override prompt.
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime, date

from tools.installer import _ok, _warn, _err, _load_global_config
from tools.extract_frames import (
    extract_frames,
    parse_transcript_docx,
    find_video_and_transcript,
    frames_output_dir,
    get_video_duration,
    detect_language,
    seconds_to_display_ts,
)
from tools.prompt_generator import generate_meeting_prompt

log = logging.getLogger("runner")

TWO_PASS_THRESHOLD_MINUTES = 45
WEB_FRAME_BUDGET           = 20
COWORK_FRAME_BUDGET        = 150


# ── Config helpers ────────────────────────────────────────────────────────────

def _find_project_config(meeting_folder: Path) -> dict:
    """Walk up from meeting_folder to find the nearest mip.config.json."""
    current = meeting_folder
    for _ in range(5):
        cfg = current / "mip.config.json"
        if cfg.exists():
            with open(cfg) as f:
                data = json.load(f)
            if "client" in data:   # project-level config
                return data
        current = current.parent
    return {}


def _merged_config(meeting_folder: Path) -> dict:
    global_cfg  = _load_global_config()
    project_cfg = _find_project_config(meeting_folder)
    return {**global_cfg, **project_cfg}


# ── Language override prompt ──────────────────────────────────────────────────

def _language_override_prompt(meeting_lang: str, project_lang: str) -> str:
    """
    Ask user which language to use when meeting and project language differ.
    Returns the selected language string.
    """
    print(f"\n  ┌─ Language detected ───────────────────────────────┐")
    print(f"  │  Meeting transcript : {meeting_lang.title():<30}│")
    print(f"  │  Project default    : {project_lang.title():<30}│")
    print(f"  └───────────────────────────────────────────────────┘")
    print(f"\n  Generate the report in:")
    print(f"    [1] {project_lang.title()} — project default")
    print(f"    [2] {meeting_lang.title()} — match the meeting")
    print(f"    [3] Both (two separate files)")
    raw = input("  Choice [1]: ").strip()
    choices = {
        "1": project_lang,
        "2": meeting_lang,
        "3": "both",
    }
    return choices.get(raw, project_lang)


# ── Transcript splitting for two-pass ────────────────────────────────────────

def _split_transcript(txt_path: Path, output_folder: Path) -> tuple[Path, Path]:
    """
    Split transcript at midpoint on a natural sentence/speaker boundary.
    Returns (half1_path, half2_path).
    """
    text = txt_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    mid = len(lines) // 2

    # Walk forward from mid to find a speaker line (starts with \n[HH:MM:SS])
    split_idx = mid
    for i in range(mid, min(mid + 50, len(lines))):
        if lines[i].startswith("[") and "]" in lines[i]:
            split_idx = i
            break

    half1_lines = lines[:split_idx]
    half2_lines = lines[split_idx:]

    half1_path = output_folder / f"{txt_path.stem}_half1.txt"
    half2_path = output_folder / f"{txt_path.stem}_half2.txt"

    half1_path.write_text("\n".join(half1_lines), encoding="utf-8")
    half2_path.write_text("\n".join(half2_lines), encoding="utf-8")

    _ok(f"Transcript split: half1 ({len(half1_lines)} lines) / half2 ({len(half2_lines)} lines)")
    return half1_path, half2_path


# ── Upload checklist printer ──────────────────────────────────────────────────

def _print_upload_checklist(
    transcript_path: Path,
    frame_paths: list[Path],
    half: int | None = None,
):
    half_label = f" (Chat {half})" if half else ""
    print(f"\n  ┌─ Upload checklist{half_label} {'─' * (36 - len(half_label))}┐")
    txt_size = transcript_path.stat().st_size / 1024
    print(f"  │  1. {transcript_path.name:<40} {txt_size:.0f} KB  │")
    print(f"  │                                                   │")
    print(f"  │  Images ({len(frame_paths)} frames):              │")
    for fp in frame_paths:
        print(f"  │     {fp.name:<46}│")
    print(f"  └───────────────────────────────────────────────────┘")
    print(f"\n  Upload these files to your LLM chat, then paste the prompt pack below.")


# ── Workflow A — Cowork ───────────────────────────────────────────────────────

def _run_cowork(
    meeting_folder: Path,
    video_path: Path,
    transcript_path: Path,
    config: dict,
    max_frames_override: int | None,
):
    budget = max_frames_override or COWORK_FRAME_BUDGET
    frames_dir = frames_output_dir(meeting_folder)

    print(f"\n  Workflow A — Cowork")
    print(f"  Frame budget : {budget}")
    print(f"  Video        : {video_path.name}")
    print(f"  Transcript   : {transcript_path.name}")

    # Extract frames
    n_frames = extract_frames(
        video_path  = video_path,
        output_dir  = frames_dir,
        budget      = budget,
    )

    # Parse transcript
    txt_path = parse_transcript_docx(transcript_path, meeting_folder)

    # Language check
    project_lang = config.get("report_language", "english")
    meeting_lang = detect_language(txt_path)
    report_lang  = project_lang

    if meeting_lang != project_lang:
        report_lang = _language_override_prompt(meeting_lang, project_lang)

    _ok(f"Frames: {n_frames} → {frames_dir}")
    _ok(f"Transcript: {txt_path.name}")
    _ok(f"Report language: {report_lang}")

    print(f"\n  ─── Cowork instructions ────────────────────────────")
    print(f"  In Cowork, run the following command:")
    print(f"\n    mip run --path \"{meeting_folder}\"")
    print(f"\n  Or paste the meeting folder path directly in Cowork chat.")
    print(f"  Cowork will read: {txt_path.name} + {n_frames} frames")
    print(f"  Report will be generated as: report_{date.today().strftime('%Y%m%d')}.md")

    if report_lang == "both":
        print(f"  Two reports will be generated: ES and EN versions.")


# ── Workflow B standard — web, < 45 min ──────────────────────────────────────

def _run_web_standard(
    meeting_folder: Path,
    video_path: Path,
    transcript_path: Path,
    config: dict,
    max_frames_override: int | None,
):
    budget     = max_frames_override or WEB_FRAME_BUDGET
    frames_dir = frames_output_dir(meeting_folder)

    print(f"\n  Workflow B — Web (standard)")
    print(f"  Frame budget : {budget}")

    # Extract frames
    n_frames = extract_frames(
        video_path = video_path,
        output_dir = frames_dir,
        budget     = budget,
    )

    # Parse transcript
    txt_path = parse_transcript_docx(transcript_path, meeting_folder)

    # Language check
    project_lang = config.get("report_language", "english")
    meeting_lang = detect_language(txt_path)
    report_lang  = project_lang

    if meeting_lang != project_lang:
        report_lang = _language_override_prompt(meeting_lang, project_lang)

    # Get saved frame paths in order
    frame_paths = sorted(frames_dir.glob("frame_*.jpg"))

    # Print upload checklist
    _print_upload_checklist(txt_path, frame_paths)

    # Print prompt pack
    print(f"\n  ─── Prompt pack ─────────────────────────────────────")
    generate_meeting_prompt(config, report_lang, print_to_console=True)

    _ok(f"Done. Upload the files above and paste the prompt pack into your LLM chat.")


# ── Workflow B two-pass — web, >= 45 min ─────────────────────────────────────

def _run_web_two_pass(
    meeting_folder: Path,
    video_path: Path,
    transcript_path: Path,
    config: dict,
    max_frames_override: int | None,
):
    budget_per_half = max_frames_override or WEB_FRAME_BUDGET
    frames_dir      = frames_output_dir(meeting_folder)

    print(f"\n  Workflow B — Web two-pass")
    print(f"  Frame budget : {budget_per_half} per half ({budget_per_half * 2} total)")

    # Extract ALL frames with double budget, then split by timestamp midpoint
    total_budget = budget_per_half * 2
    n_frames = extract_frames(
        video_path = video_path,
        output_dir = frames_dir,
        budget     = total_budget,
    )

    # Parse transcript and split into halves
    txt_path          = parse_transcript_docx(transcript_path, meeting_folder)
    half1_txt, half2_txt = _split_transcript(txt_path, meeting_folder)

    # Language check
    project_lang = config.get("report_language", "english")
    meeting_lang = detect_language(txt_path)
    report_lang  = project_lang

    if meeting_lang != project_lang:
        report_lang = _language_override_prompt(meeting_lang, project_lang)

    # Split frames into two halves by index
    all_frames = sorted(frames_dir.glob("frame_*.jpg"))
    mid_frame  = len(all_frames) // 2
    frames_h1  = all_frames[:mid_frame]
    frames_h2  = all_frames[mid_frame:]

    # Print Chat 1 instructions
    print(f"\n  ═══ CHAT 1 ═══════════════════════════════════════════")
    _print_upload_checklist(half1_txt, frames_h1, half=1)
    print(f"\n  ─── Chat 1 prompt pack ──────────────────────────────")
    generate_meeting_prompt(config, report_lang, print_to_console=True, two_pass_half=1)

    print(f"\n  After Chat 1 is complete:")
    print(f"    Copy the handoff JSON block from the LLM response.")
    print(f"    Run: mip handoff save --path \"{meeting_folder}\"")
    print(f"    Paste the JSON when prompted.")

    # Print Chat 2 instructions
    print(f"\n  ═══ CHAT 2 ═══════════════════════════════════════════")
    today_str  = date.today().strftime("%Y%m%d")
    handoff_path = meeting_folder / f"handoff_{today_str}.json"
    print(f"  Upload to a NEW conversation:")
    print(f"    1. {handoff_path.name}  (saved by 'mip handoff save')")
    print(f"    2. {half2_txt.name}")
    print(f"    And these {len(frames_h2)} frames:")
    for fp in frames_h2:
        print(f"       {fp.name}")
    print(f"\n  ─── Chat 2 prompt pack ──────────────────────────────")
    generate_meeting_prompt(config, report_lang, print_to_console=True, two_pass_half=2)

    _ok(f"Two-pass setup complete. Follow Chat 1 → save handoff → Chat 2.")


# ── Handoff save ──────────────────────────────────────────────────────────────

def save_handoff(meeting_folder: Path):
    """Prompt user to paste the handoff JSON from Chat 1 and save it."""
    print(f"\n  Paste the handoff JSON block from Chat 1.")
    print(f"  Press Enter twice when done.\n")

    lines = []
    empty_count = 0
    while True:
        line = input()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0
        lines.append(line)

    raw = "\n".join(lines).strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _err(f"Invalid JSON: {e}")
        print("  Make sure you copied the complete JSON block from Chat 1.")
        return

    today_str    = date.today().strftime("%Y%m%d")
    handoff_path = meeting_folder / f"handoff_{today_str}.json"

    with open(handoff_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    _ok(f"Handoff saved: {handoff_path}")
    print(f"\n  You can now start Chat 2.")
    print(f"  Upload: {handoff_path.name} + transcript_half2.txt + frames 21-40")


# ── Main entry point ──────────────────────────────────────────────────────────

def run_meeting(
    meeting_folder: Path,
    web_mode: bool,
    two_pass: bool,
    single_pass: bool,
    max_frames_override: int | None,
):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    print("\n" + "═" * 56)
    print("  MeetingTool v2.0 — Process Meeting")
    print("═" * 56)
    print(f"  Folder: {meeting_folder}")

    # Validate folder
    if not meeting_folder.exists():
        _err(f"Meeting folder not found: {meeting_folder}")
        sys.exit(1)

    # Load config
    config = _merged_config(meeting_folder)
    if not config:
        _warn("No mip.config.json found. Using defaults.")
        config = {"llm_provider": "claude", "report_language": "english"}

    # Find video and transcript
    video_path, transcript_path = find_video_and_transcript(meeting_folder)

    if video_path is None:
        _err("No MP4 file found in this folder.")
        print("  Expected: {MeetingName}_{YYYYMMDD}.mp4")
        sys.exit(1)

    if transcript_path is None:
        _warn("No transcript DOCX found. Frame extraction only.")

    # Detect duration for two-pass recommendation
    if web_mode and not single_pass:
        duration = get_video_duration(video_path)
        duration_min = duration / 60

        if duration_min >= TWO_PASS_THRESHOLD_MINUTES and not two_pass:
            print(f"\n  Meeting duration: {seconds_to_display_ts(duration)}")
            print(f"  This meeting is {duration_min:.0f} min — two-pass mode recommended.")
            print(f"  [1] Two-pass mode (recommended) — 20 frames per half, structured handoff")
            print(f"  [2] Single-pass — 20 frames total (may miss content in long meetings)")
            choice = input("  Choice [1]: ").strip()
            if choice != "2":
                two_pass = True

    # Route to workflow
    if not web_mode:
        _run_cowork(meeting_folder, video_path, transcript_path, config, max_frames_override)
    elif two_pass and not single_pass:
        _run_web_two_pass(meeting_folder, video_path, transcript_path, config, max_frames_override)
    else:
        _run_web_standard(meeting_folder, video_path, transcript_path, config, max_frames_override)

    print()
