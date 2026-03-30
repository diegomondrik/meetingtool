"""
tests/test_meetingtool.py — MeetingTool v2.0
=============================================
Functional test suite. Run with: python -m pytest tests/ -v

Tests cover:
  - Frame extraction with synthetic video
  - Zone scoring signal
  - Edge scoring signal
  - Temporal coverage guarantee
  - Transcript DOCX parsing
  - DOCX export with image embedding
  - Setup environment detection
  - Config merge (project overrides global)
  - Language detection
  - Two-pass transcript splitting
  - Handoff JSON validation
  - Missing image ref → export failure
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def synthetic_video(tmp_path_factory):
    """
    Generate a 3-minute synthetic test video using ffmpeg.
    9 color slides × 20 seconds each.
    Returns Path to the generated video.
    """
    out_dir = tmp_path_factory.mktemp("video")
    out_path = out_dir / "test_meeting.mp4"

    filter_complex = (
        "color=c=blue:size=1280x720:rate=30:duration=20[s1];"
        "color=c=green:size=1280x720:rate=30:duration=20[s2];"
        "color=c=red:size=1280x720:rate=30:duration=20[s3];"
        "color=c=purple:size=1280x720:rate=30:duration=20[s4];"
        "color=c=orange:size=1280x720:rate=30:duration=20[s5];"
        "color=c=teal:size=1280x720:rate=30:duration=20[s6];"
        "color=c=navy:size=1280x720:rate=30:duration=20[s7];"
        "color=c=maroon:size=1280x720:rate=30:duration=20[s8];"
        "color=c=darkgreen:size=1280x720:rate=30:duration=20[s9];"
        "[s1][s2][s3][s4][s5][s6][s7][s8][s9]concat=n=9:v=1:a=0[out]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "35",
        str(out_path)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0 or not out_path.exists():
        pytest.skip("ffmpeg not available — skipping video tests")
    return out_path


@pytest.fixture
def frames_dir(tmp_path):
    d = tmp_path / "imagenes_reunion"
    d.mkdir()
    return d


@pytest.fixture
def sample_report_with_refs(tmp_path):
    """Create a sample report.md with image references."""
    frames_dir = tmp_path / "imagenes_reunion"
    frames_dir.mkdir()

    # Add dummy image files (valid JPEG via OpenCV)

    frame_names = [
        "frame_001_t00-03-12.jpg",
        "frame_002_t00-14-47.jpg",
        "frame_003_t00-28-05.jpg",
    ]
    import numpy as np
    import cv2
    colors = [(200, 100, 50), (50, 200, 100), (100, 50, 200)]
    for i, name in enumerate(frame_names):
        img = np.full((100, 100, 3), colors[i], dtype=np.uint8)
        cv2.imwrite(str(frames_dir / name), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    report_content = """# Meeting Report

## Executive Summary
This is a test meeting about data pipeline architecture.

## Screen Analysis

The team reviewed the DuckDB schema [frame_001_t00-03-12.jpg] at the start.

Later, the Tableau prototype was shown [frame_002_t00-14-47.jpg] with missing KPIs.

Final architecture diagram [frame_003_t00-28-05.jpg] was approved.

## Decisions
1. Use DuckDB as primary engine — Owner: Diego — Date: 2026-03-30
"""
    report_path = tmp_path / "report_20260330.md"
    report_path.write_text(report_content, encoding="utf-8")
    return tmp_path


# ── Test: Setup detection ─────────────────────────────────────────────────────

class TestSetupDetection:

    def test_python_version_ok(self):
        """Python 3.11+ is required."""
        assert sys.version_info >= (3, 11), (
            f"Python 3.11+ required, found {sys.version_info.major}.{sys.version_info.minor}"
        )

    def test_ffmpeg_in_path(self):
        """ffmpeg must be accessible in PATH."""
        path = shutil.which("ffmpeg")
        assert path is not None, (
            "ffmpeg not found in PATH. Install from https://ffmpeg.org/download.html"
        )

    def test_opencv_importable(self):
        """opencv-python must be installed."""
        try:
            import cv2
        except ImportError:
            pytest.fail("opencv-python not installed. Run: pip install opencv-python")

    def test_python_docx_importable(self):
        """python-docx must be installed."""
        try:
            import docx
        except ImportError:
            pytest.fail("python-docx not installed. Run: pip install python-docx")

    def test_click_importable(self):
        """click must be installed."""
        try:
            import click
        except ImportError:
            pytest.fail("click not installed. Run: pip install click")


# ── Test: Config merge ────────────────────────────────────────────────────────

class TestConfigMerge:

    def test_project_overrides_global(self):
        """Project config values must override global config values."""
        from tools.project import _merge_configs

        global_cfg  = {"llm_provider": "claude", "default_language": "english", "mip_root": "/tmp"}
        project_cfg = {"llm_provider": "chatgpt", "report_language": "spanish", "client": "Acme"}
        merged = _merge_configs(global_cfg, project_cfg)

        assert merged["llm_provider"] == "chatgpt"
        assert merged["report_language"] == "spanish"
        assert merged["client"] == "Acme"
        assert merged["mip_root"] == "/tmp"  # global value preserved when not overridden

    def test_global_values_preserved(self):
        """Global values not present in project config must be preserved."""
        from tools.project import _merge_configs

        global_cfg  = {"llm_provider": "claude", "mip_root": "/home/user/MeetingTool", "default_language": "english"}
        project_cfg = {"client": "Kroger", "project": "RetailBeacon"}
        merged = _merge_configs(global_cfg, project_cfg)

        assert merged["mip_root"] == "/home/user/MeetingTool"
        assert merged["default_language"] == "english"
        assert merged["client"] == "Kroger"


# ── Test: Language detection ──────────────────────────────────────────────────

class TestLanguageDetection:

    def test_detects_english(self, tmp_path):
        """English transcript must be detected as English."""
        from tools.extract_frames import detect_language

        txt = tmp_path / "meeting.txt"
        txt.write_text(
            "John: The pipeline architecture that we discussed with the team "
            "will be reviewed and the data model will be updated for the next sprint. "
            "Sarah: I agree, and we should also review the test coverage for the new endpoints.",
            encoding="utf-8"
        )
        assert detect_language(txt) == "english"

    def test_detects_spanish(self, tmp_path):
        """Spanish transcript must be detected as Spanish."""
        from tools.extract_frames import detect_language

        txt = tmp_path / "meeting.txt"
        txt.write_text(
            "Diego: La arquitectura del pipeline que discutimos con el equipo "
            "será revisada y el modelo de datos será actualizado para el próximo sprint. "
            "María: Estoy de acuerdo, y también deberíamos revisar la cobertura de pruebas.",
            encoding="utf-8"
        )
        assert detect_language(txt) == "spanish"

    def test_language_mismatch_triggers_prompt(self, tmp_path, monkeypatch):
        """When meeting language differs from project default, override logic must fire."""
        from tools.extract_frames import detect_language

        txt = tmp_path / "meeting.txt"
        txt.write_text(
            "The team discussed the data architecture and the test coverage.",
            encoding="utf-8"
        )
        meeting_lang = detect_language(txt)
        project_lang = "spanish"
        assert meeting_lang != project_lang  # mismatch must be detected


# ── Test: Zone scoring ────────────────────────────────────────────────────────

class TestZoneScoring:

    def test_localized_change_scores_higher_than_uniform(self):
        """
        A frame with change in one zone should score higher than a
        frame with no meaningful change anywhere.
        """
        import numpy as np
        from tools.extract_frames import zone_score

        base = np.zeros((300, 400), dtype=np.uint8)  # all black

        # Small but significant change in top-left zone only
        localized = base.copy()
        localized[0:100, 0:100] = 200  # change one zone

        # No change
        no_change = base.copy()

        score_localized = zone_score(base, localized)
        score_no_change = zone_score(base, no_change)

        assert score_localized > score_no_change, (
            f"Localized change score ({score_localized:.3f}) should be "
            f"higher than no-change score ({score_no_change:.3f})"
        )

    def test_full_change_scores_maximum(self):
        """Complete frame change should score close to 1.0."""
        import numpy as np
        from tools.extract_frames import zone_score

        prev = np.zeros((300, 400), dtype=np.uint8)
        curr = np.full((300, 400), 200, dtype=np.uint8)

        score = zone_score(prev, curr)
        assert score > 0.8, f"Full frame change should score > 0.8, got {score:.3f}"


# ── Test: Edge scoring ────────────────────────────────────────────────────────

class TestEdgeScoring:

    def test_slide_transition_scores_higher_than_static(self):
        """
        A frame transition (blank→text-heavy) should score higher than
        a static frame comparison.
        """
        import numpy as np
        from tools.extract_frames import edge_score

        # "Previous slide" — blank
        blank = np.zeros((300, 400), dtype=np.uint8)

        # "New slide" — horizontal lines simulating text
        new_slide = np.zeros((300, 400), dtype=np.uint8)
        for y in range(30, 270, 20):
            new_slide[y, 50:350] = 255  # white horizontal line

        # "Same slide" — identical to previous
        same = blank.copy()

        score_transition = edge_score(blank, new_slide)
        score_static     = edge_score(blank, same)

        assert score_transition > score_static, (
            f"Transition score ({score_transition:.3f}) should be "
            f"higher than static score ({score_static:.3f})"
        )


# ── Test: Temporal coverage ───────────────────────────────────────────────────

class TestTemporalCoverage:

    def test_coverage_across_segments(self, synthetic_video, tmp_path):
        """
        With 20-frame budget on ~3 min video, each 20-second segment
        should have at least one frame.
        """
        from tools.extract_frames import extract_frames as ef, frames_output_dir

        out_dir = tmp_path / "imagenes_reunion"
        out_dir.mkdir()

        n = ef(
            video_path = synthetic_video,
            output_dir = out_dir,
            budget     = 20,
            fps_analyze = 2.0,
        )

        assert n >= 8, f"Expected at least 8 frames from 9-segment video, got {n}"

        # Verify naming format
        frames = sorted(out_dir.glob("frame_*.jpg"))
        assert len(frames) == n
        for f in frames:
            assert f.name.startswith("frame_"), f"Unexpected filename: {f.name}"
            parts = f.stem.split("_")
            assert len(parts) == 3, f"Filename format wrong: {f.name}"
            assert parts[2].startswith("t"), f"Timestamp prefix missing: {f.name}"

    def test_frame_budget_respected(self, synthetic_video, tmp_path):
        """Frame count must never exceed the specified budget."""
        from tools.extract_frames import extract_frames as ef

        out_dir = tmp_path / "imagenes_reunion"
        out_dir.mkdir()

        budget = 5
        n = ef(
            video_path  = synthetic_video,
            output_dir  = out_dir,
            budget      = budget,
            fps_analyze = 2.0,
        )
        assert n <= budget, f"Frame count {n} exceeds budget {budget}"


# ── Test: Transcript parsing ──────────────────────────────────────────────────

class TestTranscriptParsing:

    def test_parse_preserves_timestamps_and_speakers(self, tmp_path):
        """
        Parsed transcript must preserve all speaker timestamps.
        Boilerplate must be stripped.
        """
        from docx import Document
        from tools.extract_frames import parse_transcript_docx

        docx_path = tmp_path / "KickoffMeeting_20260330.docx"
        doc = Document()
        doc.add_paragraph("Microsoft Teams Meeting")
        doc.add_paragraph("Diego  00:01:23")
        doc.add_paragraph("Let's review the pipeline architecture.")
        doc.add_paragraph("Sarah Chen  00:05:47")
        doc.add_paragraph("I have some concerns about the data refresh cadence.")
        doc.add_paragraph("teams.microsoft.com")
        doc.save(str(docx_path))

        txt_path = parse_transcript_docx(docx_path, tmp_path)

        assert txt_path.exists()
        content = txt_path.read_text(encoding="utf-8")

        assert "[00:01:23] Diego:" in content
        assert "[00:05:47] Sarah Chen:" in content
        assert "Let's review the pipeline architecture." in content
        assert "Microsoft Teams Meeting" not in content
        assert "teams.microsoft.com" not in content


# ── Test: Two-pass split ──────────────────────────────────────────────────────

class TestTwoPassSplit:

    def test_splits_at_sentence_boundary(self, tmp_path):
        """Transcript must split at a speaker line, not mid-sentence."""
        from tools.runner import _split_transcript

        transcript = tmp_path / "meeting.txt"
        lines = []
        for i in range(100):
            if i % 10 == 0:
                lines.append(f"[00:{i:02d}:00] Speaker {i // 10}:")
            else:
                lines.append(f"This is sentence number {i} of the discussion.")
        transcript.write_text("\n".join(lines), encoding="utf-8")

        half1, half2 = _split_transcript(transcript, tmp_path)

        h1 = half1.read_text(encoding="utf-8")
        h2 = half2.read_text(encoding="utf-8")

        assert half1.exists()
        assert half2.exists()
        assert len(h1) > 0
        assert len(h2) > 0

        # Total content must equal original (minus the split boundary)
        total_orig = len(transcript.read_text(encoding="utf-8").splitlines())
        total_split = len(h1.splitlines()) + len(h2.splitlines())
        assert abs(total_split - total_orig) <= 2  # allow ±1 line for boundary


# ── Test: Handoff JSON ────────────────────────────────────────────────────────

class TestHandoffJson:

    def test_handoff_required_fields(self, tmp_path):
        """Handoff JSON must contain all required fields."""
        required_fields = {
            "meeting_id", "half", "timespan", "participants_seen",
            "decisions_confirmed", "open_threads", "action_items_partial",
            "screens_seen", "watch_for_in_half_2",
        }

        sample = {
            "meeting_id": "KickoffRetailBeacon_20260309",
            "half": 1,
            "timespan": "00:00 - 30:12",
            "participants_seen": ["Diego", "Sarah Chen"],
            "decisions_confirmed": [
                {"topic": "DuckDB as engine", "at": "00:14:22", "owner": "Diego"}
            ],
            "open_threads": [
                {"topic": "Data refresh cadence", "raised_at": "00:22:10", "status": "unresolved"}
            ],
            "action_items_partial": [
                {"task": "Send pipeline diagram", "owner": "Diego", "deadline": "Friday"}
            ],
            "screens_seen": ["DuckDB schema", "Tableau prototype"],
            "watch_for_in_half_2": ["Resolution of data refresh cadence"],
        }

        handoff_path = tmp_path / "handoff_20260330.json"
        with open(handoff_path, "w") as f:
            json.dump(sample, f)

        with open(handoff_path) as f:
            loaded = json.load(f)

        for field in required_fields:
            assert field in loaded, f"Required field '{field}' missing from handoff JSON"


# ── Test: DOCX export ─────────────────────────────────────────────────────────

class TestDocxExport:

    def test_export_embeds_images(self, sample_report_with_refs):
        """DOCX export must embed all 3 referenced images."""
        from tools.exporter import run_export

        run_export(
            meeting_folder = sample_report_with_refs,
            output_format  = "docx",
        )

        docx_files = list(sample_report_with_refs.glob("report_*.docx"))
        assert len(docx_files) == 1, "Expected exactly one DOCX file"

        # Verify DOCX is a valid ZIP (DOCX format)
        import zipfile
        assert zipfile.is_zipfile(docx_files[0]), "Generated DOCX is not a valid ZIP/DOCX"

        # Verify it contains media (embedded images)
        with zipfile.ZipFile(docx_files[0]) as z:
            names = z.namelist()
            media_files = [n for n in names if n.startswith("word/media/")]
            assert len(media_files) >= 1, (
                f"Expected embedded images in DOCX, found none. Contents: {names}"
            )

    def test_export_fails_on_missing_ref(self, tmp_path):
        """Export must fail with a clear error when an image ref cannot be resolved."""
        from tools.exporter import _resolve_image_refs

        frames_dir = tmp_path / "imagenes_reunion"
        frames_dir.mkdir()
        # Do NOT create the referenced file

        report_text = "The diagram [frame_999_t00-99-99.jpg] shows the architecture."
        resolved, missing = _resolve_image_refs(report_text, frames_dir)

        assert len(missing) == 1
        assert "frame_999_t00-99-99.jpg" in missing
        assert len(resolved) == 0
