"""
tools/runner.py — MeetingTool v2.5
====================================
Orchestrates the meeting analysis workflows:
  - Workflow A (automated): Cowork — extract_frames -> Gemini vision -> Claude report
  - Workflow A (legacy):    Cowork — full frame budget, prompt to clipboard
  - Workflow B standard:    web, < 45 min (20 frames, upload checklist)
  - Workflow B two-pass:    web, >= 45 min (20 frames per half, handoff JSON)

Returns structured AnalysisResult for both GUI and CLI.
"""

import json
import logging
from pathlib import Path
from datetime import date
from dataclasses import dataclass, field

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
from tools.gemini_client import extract_visual_evidence, GeminiUnavailableError
from tools.api_config import get_gemini_key, get_gemini_key_2, get_anthropic_key

try:
    # 'anthropic' is optional — only the automated pipeline (--auto) needs it.
    # Cowork/web workflows must be able to import this module without it installed.
    from tools.claude_client import generate_report, write_report
except ImportError:
    generate_report = write_report = None

log = logging.getLogger("runner")

TWO_PASS_THRESHOLD_MINUTES = 45
WEB_FRAME_BUDGET           = 20
COWORK_FRAME_BUDGET        = 150


# ── Structured result returned to GUI ────────────────────────────────────────

@dataclass
class AnalysisResult:
    """Everything the GUI needs to show next steps after extraction."""
    workflow: str                    # "cowork" | "web" | "two_pass"
    meeting_folder: Path
    frames_dir: Path
    n_frames: int
    transcript_txt: Path | None
    report_language: str
    prompt_chat1: str                # main prompt (or Chat 1 prompt for two-pass)
    prompt_chat2: str = ""           # Chat 2 prompt (two-pass only)
    frames_chat1: list = field(default_factory=list)
    frames_chat2: list = field(default_factory=list)
    handoff_path: Path | None = None
    provider: str = "claude"
    cowork_mode: bool = False
    report_path: Path | None = None          # set by automated pipeline
    visual_evidence_source: str = ""         # "gemini" | "ocr_fallback" | ""


# ── Config helpers ────────────────────────────────────────────────────────────

def _find_project_config(meeting_folder: Path) -> dict:
    """Walk up from meeting_folder to find the nearest mip.config.json."""
    current = meeting_folder
    for _ in range(5):
        cfg = current / "mip.config.json"
        if cfg.exists():
            with open(cfg) as f:
                data = json.load(f)
            if "client" in data:
                return data
        current = current.parent
    return {}


def _merged_config(meeting_folder: Path) -> dict:
    global_cfg  = _load_global_config()
    project_cfg = _find_project_config(meeting_folder)
    return {**global_cfg, **project_cfg}


# ── Language handling ─────────────────────────────────────────────────────────

def _resolve_language(meeting_lang: str, project_lang: str) -> str:
    """
    When meeting language differs from project default, auto-select project
    default and log the mismatch. The GUI has no console to prompt the user;
    the CLI user can override with project config or by editing the report.
    """
    if meeting_lang != project_lang:
        log.info(
            f"Language mismatch: meeting={meeting_lang}, project={project_lang}. "
            f"Using project default: {project_lang}"
        )
    return project_lang


# ── Transcript splitting ──────────────────────────────────────────────────────

def _split_transcript(txt_path: Path, output_folder: Path) -> tuple[Path, Path]:
    """Split transcript at midpoint on a natural speaker-boundary line."""
    text  = txt_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    mid   = len(lines) // 2

    split_idx = mid
    for i in range(mid, min(mid + 50, len(lines))):
        if lines[i].startswith("[") and "]" in lines[i]:
            split_idx = i
            break

    half1_path = output_folder / f"{txt_path.stem}_half1.txt"
    half2_path = output_folder / f"{txt_path.stem}_half2.txt"
    half1_path.write_text("\n".join(lines[:split_idx]), encoding="utf-8")
    half2_path.write_text("\n".join(lines[split_idx:]), encoding="utf-8")

    _ok(f"Transcript split: half1 ({split_idx} lines) / half2 ({len(lines) - split_idx} lines)")
    return half1_path, half2_path


# ── CLI upload checklist ──────────────────────────────────────────────────────

def _print_upload_checklist(
    transcript_path: Path,
    frame_paths: list,
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
    transcript_path: Path | None,
    config: dict,
    max_frames_override: int | None,
) -> AnalysisResult:
    budget     = max_frames_override or COWORK_FRAME_BUDGET
    frames_dir = frames_output_dir(meeting_folder)

    log.info(f"Workflow A — Cowork  |  budget: {budget} frames")
    log.info(f"Video: {video_path.name}")

    n_frames = extract_frames(video_path=video_path, output_dir=frames_dir, budget=budget)

    txt_path = None
    if transcript_path:
        txt_path = parse_transcript_docx(transcript_path, meeting_folder)
        log.info(f"Transcript parsed: {txt_path.name}")

    project_lang = config.get("report_language", "english")
    report_lang  = project_lang
    if txt_path:
        report_lang = _resolve_language(detect_language(txt_path), project_lang)

    prompt = generate_meeting_prompt(config, report_lang)

    log.info(f"Frames extracted: {n_frames}")
    log.info(f"Report language: {report_lang}")

    _ok(f"Frames: {n_frames} → {frames_dir.name}")
    if txt_path:
        _ok(f"Transcript: {txt_path.name}")
    _ok(f"Language: {report_lang}")

    return AnalysisResult(
        workflow       = "cowork",
        meeting_folder = meeting_folder,
        frames_dir     = frames_dir,
        n_frames       = n_frames,
        transcript_txt = txt_path,
        report_language= report_lang,
        prompt_chat1   = prompt,
        provider       = config.get("llm_provider", "claude"),
        cowork_mode    = config.get("cowork_mode", False),
    )


# ── Workflow B standard ───────────────────────────────────────────────────────

def _run_web_standard(
    meeting_folder: Path,
    video_path: Path,
    transcript_path: Path | None,
    config: dict,
    max_frames_override: int | None,
) -> AnalysisResult:
    budget     = max_frames_override or WEB_FRAME_BUDGET
    frames_dir = frames_output_dir(meeting_folder)

    log.info(f"Workflow B — Web standard  |  budget: {budget} frames")

    n_frames = extract_frames(video_path=video_path, output_dir=frames_dir, budget=budget)

    txt_path = None
    if transcript_path:
        txt_path = parse_transcript_docx(transcript_path, meeting_folder)

    project_lang = config.get("report_language", "english")
    report_lang  = project_lang
    if txt_path:
        report_lang = _resolve_language(detect_language(txt_path), project_lang)

    frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
    prompt = generate_meeting_prompt(config, report_lang)

    log.info(f"Frames extracted: {n_frames}")

    if txt_path:
        _print_upload_checklist(txt_path, frame_paths)
        print(f"\n  ─── Prompt pack ─────────────────────────────────────")
        generate_meeting_prompt(config, report_lang, print_to_console=True)
        _ok("Done. Upload the files above and paste the prompt pack into your LLM chat.")

    return AnalysisResult(
        workflow       = "web",
        meeting_folder = meeting_folder,
        frames_dir     = frames_dir,
        n_frames       = n_frames,
        transcript_txt = txt_path,
        report_language= report_lang,
        prompt_chat1   = prompt,
        frames_chat1   = frame_paths,
        provider       = config.get("llm_provider", "claude"),
        cowork_mode    = False,
    )


# ── Workflow B two-pass ───────────────────────────────────────────────────────

def _run_web_two_pass(
    meeting_folder: Path,
    video_path: Path,
    transcript_path: Path | None,
    config: dict,
    max_frames_override: int | None,
) -> AnalysisResult:
    budget_per_half = max_frames_override or WEB_FRAME_BUDGET
    frames_dir      = frames_output_dir(meeting_folder)

    log.info(f"Workflow B — Two-pass  |  {budget_per_half} frames per half")

    n_frames = extract_frames(
        video_path=video_path, output_dir=frames_dir, budget=budget_per_half * 2
    )

    txt_path = None
    half1_txt = half2_txt = None
    if transcript_path:
        txt_path = parse_transcript_docx(transcript_path, meeting_folder)
        half1_txt, half2_txt = _split_transcript(txt_path, meeting_folder)

    project_lang = config.get("report_language", "english")
    report_lang  = project_lang
    if txt_path:
        report_lang = _resolve_language(detect_language(txt_path), project_lang)

    all_frames = sorted(frames_dir.glob("frame_*.jpg"))
    mid        = len(all_frames) // 2
    frames_h1  = all_frames[:mid]
    frames_h2  = all_frames[mid:]

    prompt_chat1 = generate_meeting_prompt(config, report_lang, two_pass_half=1)
    prompt_chat2 = generate_meeting_prompt(config, report_lang, two_pass_half=2)

    today_str    = date.today().strftime("%Y%m%d")
    handoff_path = meeting_folder / f"handoff_{today_str}.json"

    log.info(f"Frames extracted: {n_frames} ({len(frames_h1)} / {len(frames_h2)})")
    log.info(f"Transcript split into two halves")

    if half1_txt and half2_txt:
        print(f"\n  ═══ CHAT 1 ═══════════════════════════════════════════")
        _print_upload_checklist(half1_txt, frames_h1, half=1)
        print(f"\n  ─── Chat 1 prompt pack ──────────────────────────────")
        generate_meeting_prompt(config, report_lang, print_to_console=True, two_pass_half=1)
        print(f"\n  After Chat 1: copy the handoff JSON, then run: mip handoff save --path \"{meeting_folder}\"")

        print(f"\n  ═══ CHAT 2 ═══════════════════════════════════════════")
        _print_upload_checklist(half2_txt, frames_h2, half=2)
        print(f"\n  ─── Chat 2 prompt pack ──────────────────────────────")
        generate_meeting_prompt(config, report_lang, print_to_console=True, two_pass_half=2)
        _ok("Two-pass setup complete. Follow Chat 1 → save handoff → Chat 2.")

    return AnalysisResult(
        workflow       = "two_pass",
        meeting_folder = meeting_folder,
        frames_dir     = frames_dir,
        n_frames       = n_frames,
        transcript_txt = txt_path,
        report_language= report_lang,
        prompt_chat1   = prompt_chat1,
        prompt_chat2   = prompt_chat2,
        frames_chat1   = frames_h1,
        frames_chat2   = frames_h2,
        handoff_path   = handoff_path,
        provider       = config.get("llm_provider", "claude"),
        cowork_mode    = False,
    )


# ── Handoff save (CLI only) ───────────────────────────────────────────────────

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


# ── v3.0: Transcript segments for Gemini context ─────────────────────────────

_FRAME_TS_RE = __import__('re').compile(r't(\d{2})-(\d{2})-(\d{2})')
_TS_BLOCK_RE = __import__('re').compile(r'^\[(\d{1,2}):(\d{2}):(\d{2})\]', __import__('re').MULTILINE)


def _build_transcript_segments(txt_path: Path, frame_paths: list,
                                window: float = 45) -> dict:
    """
    Build {frame_global_index (1-based): transcript_snippet} for all frames.
    Timestamps parsed from frame filenames (frame_NNN_tHH-MM-SS.jpg).
    Snippet is the transcript text within ±window seconds of the frame, capped at 500 chars.
    """
    try:
        transcript_text = txt_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    entries = []
    for m in _TS_BLOCK_RE.finditer(transcript_text):
        ts_secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        entries.append((ts_secs, m.start()))

    if not entries:
        return {}

    result = {}
    for i, frame_path in enumerate(frame_paths):
        m = _FRAME_TS_RE.search(frame_path.name)
        if not m:
            continue
        frame_secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        lo, hi = frame_secs - window, frame_secs + window

        snippets = []
        for j, (ts_secs, pos) in enumerate(entries):
            if lo <= ts_secs <= hi:
                end_pos = entries[j + 1][1] if j + 1 < len(entries) else len(transcript_text)
                block = transcript_text[pos:end_pos].strip()
                if block:
                    snippets.append(block)

        if snippets:
            combined = " ".join(snippets)
            if len(combined) > 500:
                combined = combined[:497] + "..."
            result[i + 1] = combined

    return result


# ── v2.5: OCR fallback ───────────────────────────────────────────────────────

def _ocr_fallback(frame_paths: list[Path]) -> str:
    """
    Run Tesseract OCR on each frame. Called only when Gemini is unavailable.
    Returns concatenated per-frame text, or empty string when pytesseract or
    Tesseract is not installed (degrade gracefully per §6 fallback rule).
    """
    try:
        import pytesseract
        from PIL import Image as _PIL_Image
    except ImportError:
        log.warning("pytesseract not installed — OCR fallback skipped")
        return ""

    results = []
    for i, path in enumerate(frame_paths):
        try:
            text = pytesseract.image_to_string(_PIL_Image.open(path)).strip()
            if text:
                results.append(f"[FRAME {i + 1}]\n{text}")
        except Exception as exc:
            log.warning(f"OCR skipped {path.name}: {exc}")

    if not results:
        log.warning("OCR fallback produced no extractable text")
        return ""

    combined = "\n\n".join(results)
    log.info(f"OCR fallback: {len(results)} frame(s) produced text ({len(combined)} chars)")
    return combined


# ── Context staleness check ───────────────────────────────────────────────────

def _check_context_staleness(config: dict, staleness_days: int = 90) -> bool:
    updated_str = config.get("client_context_updated", "")
    client_context = config.get("client_context", "")
    if not client_context or not updated_str:
        return False
    try:
        updated = date.fromisoformat(updated_str)
    except ValueError:
        return False
    age = (date.today() - updated).days
    if age < staleness_days:
        return False
    print(f"\n  ⚠  Client context was last updated {age} days ago.")
    answer = input("  Is it still accurate? (y/n) [y]: ").strip().lower()
    return answer == "n"


# ── v2.5: Workflow A (automated) ─────────────────────────────────────────────

def _run_cowork_automated(
    meeting_folder: Path,
    video_path: Path,
    transcript_path: Path | None,
    config: dict,
    max_frames_override: int | None,
) -> AnalysisResult:
    """
    Full automated pipeline: extract_frames -> Gemini vision -> Claude report.
    Falls back to pytesseract OCR if Gemini is unavailable (GeminiUnavailableError).
    """
    if generate_report is None:
        raise RuntimeError(
            "The 'anthropic' package is not installed. The automated pipeline "
            "(--auto) needs it — run: pip install anthropic"
        )

    budget     = max_frames_override or COWORK_FRAME_BUDGET
    frames_dir = frames_output_dir(meeting_folder)

    log.info(f"Workflow A (automated) | budget: {budget} frames")
    log.info(f"Video: {video_path.name}")

    # ── Transcript first — needed for boost during frame extraction ───────────
    txt_path        = None
    transcript_text = ""
    if transcript_path:
        txt_path        = parse_transcript_docx(transcript_path, meeting_folder)
        transcript_text = txt_path.read_text(encoding="utf-8")
        log.info(f"Transcript: {txt_path.name} ({len(transcript_text)} chars)")

    n_frames    = extract_frames(
        video_path      = video_path,
        output_dir      = frames_dir,
        budget          = budget,
        transcript_text = transcript_text,
    )
    frame_paths = sorted(frames_dir.glob("frame_*.jpg"))

    project_lang = config.get("report_language", "english")
    report_lang  = project_lang
    if txt_path:
        report_lang = _resolve_language(detect_language(txt_path), project_lang)

    # ── Visual extraction: Gemini -> OCR fallback ─────────────────────────────
    visual_evidence = ""
    visual_source   = "gemini"

    transcript_segs = {}
    if txt_path:
        transcript_segs = _build_transcript_segments(txt_path, frame_paths)
        log.info(f"Transcript segments built: {len(transcript_segs)} frames with context")

    try:
        gemini_key      = get_gemini_key(config)
        gemini_key_2    = get_gemini_key_2(config)
        visual_evidence = extract_visual_evidence(
            frame_paths, gemini_key,
            transcript_segments=transcript_segs or None,
            api_key_2=gemini_key_2,
        )
        _ok(f"Gemini: {len(visual_evidence)} chars of visual evidence")

    except GeminiUnavailableError as exc:
        log.warning(f"Gemini unavailable — activating OCR fallback: {exc}")
        _warn("Gemini unavailable — running local OCR fallback")
        visual_evidence = _ocr_fallback(frame_paths)
        visual_source   = "ocr_fallback"
        if visual_evidence:
            _ok(f"OCR fallback: {len(visual_evidence)} chars")
        else:
            _warn("OCR fallback produced no text — Claude will proceed without visual evidence")

    # ── Report generation (Claude) ────────────────────────────────────────────
    report_md = generate_report(
        transcript_text = transcript_text,
        visual_evidence = visual_evidence,
        config          = config,
        meeting_type    = config.get("meeting_type"),
        report_language = report_lang,
    )
    _ok(f"Report generated: {len(report_md)} chars")

    date_str    = date.today().strftime("%Y%m%d")
    report_path = write_report(report_md, meeting_folder, date_str)
    _ok(f"Report written: {report_path.name}")

    log.info(
        f"Automated pipeline complete — frames={n_frames}, "
        f"source={visual_source}, report={report_path.name}"
    )

    return AnalysisResult(
        workflow               = "cowork",
        meeting_folder         = meeting_folder,
        frames_dir             = frames_dir,
        n_frames               = n_frames,
        transcript_txt         = txt_path,
        report_language        = report_lang,
        prompt_chat1           = "",
        provider               = "claude",
        cowork_mode            = True,
        report_path            = report_path,
        visual_evidence_source = visual_source,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def run_meeting(
    meeting_folder: Path,
    web_mode: bool,
    two_pass: bool,
    single_pass: bool,
    max_frames_override: int | None,
    manual_transcript: Path | None = None,
    automated_pipeline: bool = False,
) -> AnalysisResult:

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("=" * 56)
    log.info("MeetingTool v2.0 — Processing meeting")
    log.info("=" * 56)
    log.info(f"Folder: {meeting_folder}")

    if not meeting_folder.exists():
        _err(f"Meeting folder not found: {meeting_folder}")
        raise RuntimeError(f"Meeting folder not found: {meeting_folder}")

    config = _merged_config(meeting_folder)
    if not config:
        _warn("No mip.config.json found. Using defaults.")
        config = {"llm_provider": "claude", "report_language": "english"}

    _check_context_staleness(config)

    video_path, transcript_path = find_video_and_transcript(meeting_folder)

    if manual_transcript and manual_transcript.exists():
        transcript_path = manual_transcript
        log.info(f"Using manually selected transcript: {transcript_path.name}")

    if video_path is None:
        _err("No MP4 file found in this folder.")
        raise RuntimeError("No MP4 file found in this folder")

    if transcript_path is None:
        _warn("No transcript DOCX found. Proceeding with frame extraction only.")

    # Auto-enable two-pass for long meetings in web mode
    if web_mode and not single_pass and not two_pass:
        duration     = get_video_duration(video_path)
        duration_min = duration / 60
        if duration_min >= TWO_PASS_THRESHOLD_MINUTES:
            log.info(
                f"Meeting duration: {seconds_to_display_ts(duration)} — "
                f"auto-enabling two-pass mode"
            )
            two_pass = True

    if not web_mode:
        if automated_pipeline:
            return _run_cowork_automated(
                meeting_folder, video_path, transcript_path, config, max_frames_override
            )
        return _run_cowork(meeting_folder, video_path, transcript_path, config, max_frames_override)
    elif two_pass and not single_pass:
        return _run_web_two_pass(meeting_folder, video_path, transcript_path, config, max_frames_override)
    else:
        return _run_web_standard(meeting_folder, video_path, transcript_path, config, max_frames_override)
