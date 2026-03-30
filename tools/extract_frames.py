"""
tools/extract_frames.py — MeetingTool v2.0
==========================================
Intelligent frame selection using three-signal scoring algorithm:
  Signal 1 — Zone-based structural change (weight: 0.4)
  Signal 2 — Edge map delta (weight: 0.3)
  Signal 3 — Temporal coverage (weight: 0.3)

Replaces v1's brute global-mean-diff approach.
Works for both Workflow A (Cowork, budget=150) and Workflow B (web, budget=20).

Also handles transcript DOCX → .txt parsing (carried over from v1, cleaned up).
"""

import re
import logging
from pathlib import Path
from datetime import timedelta

log = logging.getLogger("extract_frames")


# ── Timestamp utilities ───────────────────────────────────────────────────────

def seconds_to_filename_ts(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h  = int(td.total_seconds()) // 3600
    m  = (int(td.total_seconds()) % 3600) // 60
    s  = int(td.total_seconds()) % 60
    return f"t{h:02d}-{m:02d}-{s:02d}"


def seconds_to_display_ts(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h  = int(td.total_seconds()) // 3600
    m  = (int(td.total_seconds()) % 3600) // 60
    s  = int(td.total_seconds()) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── Frame output directory ────────────────────────────────────────────────────

def frames_output_dir(meeting_folder: Path) -> Path:
    out = meeting_folder / "imagenes_reunion"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ── Signal 1: Zone-based structural change ────────────────────────────────────

def zone_score(prev_gray, curr_gray, grid_rows: int = 3, grid_cols: int = 4,
               local_threshold: float = 8.0) -> float:
    """
    Divide frame into grid_rows x grid_cols zones.
    Score = fraction of zones with mean pixel diff > local_threshold.
    Detects localized changes (a number changing in one cell of a dashboard)
    that global mean diff would score near zero.
    """
    import numpy as np
    h, w = prev_gray.shape
    zone_h = h // grid_rows
    zone_w = w // grid_cols
    changed_zones = 0
    total_zones = grid_rows * grid_cols

    for r in range(grid_rows):
        for c in range(grid_cols):
            y0, y1 = r * zone_h, (r + 1) * zone_h
            x0, x1 = c * zone_w, (c + 1) * zone_w
            prev_zone = prev_gray[y0:y1, x0:x1]
            curr_zone = curr_gray[y0:y1, x0:x1]
            mean_diff = float(np.abs(
                prev_zone.astype(np.float32) - curr_zone.astype(np.float32)
            ).mean())
            if mean_diff > local_threshold:
                changed_zones += 1

    return changed_zones / total_zones


# ── Signal 2: Edge map delta ──────────────────────────────────────────────────

def edge_score(prev_gray, curr_gray,
               canny_low: int = 50, canny_high: int = 150) -> float:
    """
    Canny edge detection on both frames.
    Score = normalized absolute difference in edge density.
    High score = new text appeared, slide transition, annotation added.
    More stable than pixel diff for content-heavy screens.
    """
    import cv2
    import numpy as np

    prev_edges = cv2.Canny(prev_gray, canny_low, canny_high)
    curr_edges = cv2.Canny(curr_gray, canny_low, canny_high)

    prev_density = float(np.mean(prev_edges > 0))
    curr_density = float(np.mean(curr_edges > 0))

    # Normalized absolute change in edge density
    max_density = max(prev_density, curr_density, 0.001)
    return abs(curr_density - prev_density) / max_density


# ── Signal 3: Temporal coverage ───────────────────────────────────────────────

def temporal_score(timestamp: float, duration: float, budget: int,
                   existing_timestamps: list[float]) -> float:
    """
    Reward frames in under-represented time segments.
    Penalize frames in over-represented segments.
    Guarantees coverage across the full meeting duration.
    """
    if duration <= 0 or budget <= 0:
        return 0.5

    segment_duration = duration / budget
    segment_idx = int(timestamp / segment_duration)

    # Count how many existing frames fall in the same segment
    same_segment_count = sum(
        1 for t in existing_timestamps
        if int(t / segment_duration) == segment_idx
    )

    # Score decreases as the segment becomes more represented
    if same_segment_count == 0:
        return 1.0
    elif same_segment_count == 1:
        return 0.6
    elif same_segment_count == 2:
        return 0.3
    else:
        return 0.1


# ── Composite scoring ─────────────────────────────────────────────────────────

def composite_score(
    prev_gray,
    curr_gray,
    timestamp: float,
    duration: float,
    budget: int,
    existing_timestamps: list[float],
    w_zone: float = 0.4,
    w_edge: float = 0.3,
    w_temporal: float = 0.3,
) -> float:
    """
    Compute the composite informational value score for a candidate frame.
    score = (zone_score × 0.4) + (edge_score × 0.3) + (temporal_score × 0.3)
    """
    import numpy as np

    z = zone_score(prev_gray, curr_gray)
    e = min(edge_score(prev_gray, curr_gray), 1.0)
    t = temporal_score(timestamp, duration, budget, existing_timestamps)

    return (z * w_zone) + (e * w_edge) + (t * w_temporal)


# ── Main extraction function ──────────────────────────────────────────────────

def extract_frames(
    video_path: Path,
    output_dir: Path,
    budget: int = 150,
    fps_analyze: float = 2.0,
    roi_top: float = 0.15,
    min_gap: float = 3.0,
    min_composite_score: float = 0.15,
) -> int:
    """
    Extract frames using the three-signal composite scoring algorithm.

    Args:
        video_path:           Path to the MP4 file
        output_dir:           Where to save extracted frames
        budget:               Maximum number of frames to save
                              (150 for Cowork, 20 for web mode)
        fps_analyze:          Frames per second to analyze (2 is sufficient)
        roi_top:              Fraction of frame height to ignore at top
                              (Teams camera strip, default 15%)
        min_gap:              Minimum seconds between saved frames
        min_composite_score:  Minimum score to consider a frame as candidate

    Returns:
        Number of frames saved.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        log.error("Missing dependency: pip install opencv-python")
        raise

    import sys

    log.info(f"Opening video: {video_path.name}")
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        log.error(f"Cannot open video: {video_path}")
        raise RuntimeError(f"Cannot open video: {video_path}")

    total_fps      = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames_v = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_secs  = total_frames_v / total_fps if total_fps > 0 else 0

    log.info(
        f"Video: {total_frames_v} frames @ {total_fps:.1f} fps — "
        f"duration: {seconds_to_display_ts(duration_secs)}"
    )
    log.info(f"Frame budget: {budget} | fps_analyze: {fps_analyze} | roi_top: {roi_top}")

    # Clean previous frames
    for old in output_dir.glob("frame_*.jpg"):
        old.unlink()

    step = max(1, int(total_fps / fps_analyze))

    prev_gray           = None
    candidates          = []   # list of (timestamp, score, frame_bgr)
    saved_timestamps    = []   # timestamps already selected (for temporal scoring)
    last_saved_t        = -min_gap - 1
    frame_idx           = 0
    read_count          = 0

    log.info(f"Analyzing at {fps_analyze} fps (step={step} frames)...")

    while True:
        ret = cap.grab()
        if not ret:
            break

        if frame_idx % step != 0:
            frame_idx += 1
            continue

        ret, frame_bgr = cap.retrieve()
        if not ret:
            frame_idx += 1
            continue

        read_count += 1
        timestamp = frame_idx / total_fps

        # Apply ROI: strip Teams camera bar from top
        h, w = frame_bgr.shape[:2]
        roi_y      = int(h * roi_top)
        frame_roi  = frame_bgr[roi_y:, :]
        curr_gray  = cv2.cvtColor(frame_roi, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None and (timestamp - last_saved_t) >= min_gap:
            score = composite_score(
                prev_gray         = prev_gray,
                curr_gray         = curr_gray,
                timestamp         = timestamp,
                duration          = duration_secs,
                budget            = budget,
                existing_timestamps = saved_timestamps,
            )

            if score >= min_composite_score:
                candidates.append((timestamp, score, frame_bgr.copy()))
                saved_timestamps.append(timestamp)
                last_saved_t = timestamp

        prev_gray  = curr_gray
        frame_idx += 1

        # Progress every 5 minutes
        if frame_idx % (int(total_fps) * 300) == 0:
            log.info(
                f"  Progress: {seconds_to_display_ts(timestamp)} / "
                f"{seconds_to_display_ts(duration_secs)} — "
                f"{len(candidates)} candidates"
            )

    cap.release()
    log.info(f"Analyzed {read_count} frames. Candidates: {len(candidates)}")

    # Apply budget: keep top-N by composite score, then re-sort chronologically
    if len(candidates) > budget:
        log.info(f"Applying budget: {len(candidates)} → {budget} frames (highest composite score)")
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = candidates[:budget]
        candidates.sort(key=lambda x: x[0])

    # Save frames
    saved = 0
    for i, (ts, score, frame_bgr) in enumerate(candidates, start=1):
        ts_str   = seconds_to_filename_ts(ts)
        filename = f"frame_{i:03d}_{ts_str}.jpg"
        out_path = output_dir / filename
        cv2.imwrite(str(out_path), frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        saved += 1
        log.info(f"  [{i:03d}] {filename}  (score={score:.3f})")

    log.info(f"✓ {saved} frames saved to: {output_dir}")
    return saved


# ── Transcript parsing ────────────────────────────────────────────────────────

_TS_PATTERN  = re.compile(r"\[?\d{1,2}:\d{2}:\d{2}\]?")
_SPEAKER_TS  = re.compile(r"^(.+?)\s{2,}(\d{1,2}:\d{2}:\d{2})\s*$")

TEAMS_BOILERPLATE = [
    "microsoft teams meeting",
    "teams.microsoft.com",
    "join microsoft teams meeting",
    "meeting id:",
    "passcode:",
]


def parse_transcript_docx(docx_path: Path, output_folder: Path) -> Path:
    """
    Parse a Teams transcript DOCX to clean .txt.
    Preserves timestamps and speaker names. Removes Teams UI boilerplate.
    """
    try:
        from docx import Document
    except ImportError:
        log.error("Missing dependency: pip install python-docx")
        raise

    log.info(f"Parsing transcript: {docx_path.name}")
    doc   = Document(str(docx_path))
    lines = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Speaker + timestamp line
        m = _SPEAKER_TS.match(text)
        if m:
            speaker, ts = m.group(1).strip(), m.group(2)
            lines.append(f"\n[{ts}] {speaker}:")
            continue

        # Standalone timestamp — skip
        if _TS_PATTERN.fullmatch(text.strip("[]")):
            continue

        # Teams boilerplate — skip
        if any(bp in text.lower() for bp in TEAMS_BOILERPLATE):
            continue

        lines.append(text)

    # Collapse multiple blank lines
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    out_name = docx_path.stem + ".txt"
    out_path = output_folder / out_name

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))

    log.info(f"✓ Transcript saved: {out_path.name} ({len(cleaned)} lines)")
    return out_path


# ── Auto-detect meeting files ─────────────────────────────────────────────────

def find_video_and_transcript(folder: Path):
    """
    Auto-detect MP4 and DOCX in a meeting folder by matching filename stems.
    Falls back to first available file of each type if no stem match found.
    """
    mp4_files  = list(folder.glob("*.mp4")) + list(folder.glob("*.MP4"))
    docx_files = [f for f in folder.glob("*.docx") if "_summary_" not in f.name
                  and "report_" not in f.name]

    video_path      = None
    transcript_path = None

    for mp4 in mp4_files:
        matching_docx = folder / f"{mp4.stem}.docx"
        if matching_docx.exists():
            video_path      = mp4
            transcript_path = matching_docx
            break

    if video_path is None and mp4_files:
        video_path = mp4_files[0]
        log.warning(f"No DOCX with same stem as {video_path.name}. Using first MP4.")

    if transcript_path is None and docx_files:
        transcript_path = docx_files[0]
        log.warning(f"Transcript DOCX without exact match. Using: {transcript_path.name}")

    return video_path, transcript_path


# ── Duration detection ────────────────────────────────────────────────────────

def get_video_duration(video_path: Path) -> float:
    """Return video duration in seconds using ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ],
            capture_output=True, text=True, timeout=15
        )
        return float(result.stdout.strip())
    except Exception:
        # Fallback: use OpenCV
        try:
            import cv2
            cap = cv2.VideoCapture(str(video_path))
            fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            return frames / fps
        except Exception:
            return 0.0


# ── Transcript language detection ─────────────────────────────────────────────

def detect_language(txt_path: Path) -> str:
    """
    Detect whether a transcript is primarily English or Spanish
    using character frequency analysis. No external libraries required.
    Returns 'english' or 'spanish'.
    """
    try:
        text = txt_path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return "english"

    # Spanish-specific characters and common words
    spanish_chars   = set("áéíóúüñ¿¡")
    spanish_markers = ["que", "por", "con", "para", "una", "los", "las", "del", "está", "son"]
    english_markers = ["the", "and", "that", "this", "with", "from", "have", "will", "are", "for"]

    spanish_score = sum(1 for c in text if c in spanish_chars)
    spanish_score += sum(f" {w} " in text for w in spanish_markers) * 3
    english_score  = sum(f" {w} " in text for w in english_markers) * 3

    return "spanish" if spanish_score > english_score else "english"
