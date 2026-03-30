"""
tools/setup.py — MeetingTool v2.0
==================================
Interactive first-time setup. Verifies environment, installs dependencies,
creates folder structure, generates global mip.config.json.

Run via: mip setup
"""

import os
import sys
import json
import shutil
import subprocess
import platform
from pathlib import Path
from datetime import datetime


# ── Constants ────────────────────────────────────────────────────────────────

REQUIRED_PACKAGES = [
    "opencv-python",
    "python-docx",
    "click",
    "requests",
]

IMPORT_CHECK = {
    "opencv-python": "cv2",
    "python-docx":   "docx",
    "click":         "click",
    "requests":      "requests",
}

MIN_PYTHON = (3, 11)

PROVIDERS = {
    "1": "claude",
    "2": "chatgpt",
    "3": "gemini",
}

LANGUAGES = {
    "1": "english",
    "2": "spanish",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _print_step(n: int, title: str):
    print(f"\n{'─' * 56}")
    print(f"  Step {n}: {title}")
    print(f"{'─' * 56}")


def _ok(msg: str):
    print(f"  ✓  {msg}")


def _warn(msg: str):
    print(f"  ⚠  {msg}")


def _err(msg: str):
    print(f"  ✗  {msg}")


def _ask(prompt: str, default: str = "") -> str:
    if default:
        result = input(f"\n  {prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"\n  {prompt}: ").strip()


def _ask_choice(prompt: str, choices: dict, default_key: str) -> str:
    """Display numbered choices and return the value for the chosen key."""
    print(f"\n  {prompt}")
    for key, val in choices.items():
        marker = " (default)" if key == default_key else ""
        print(f"    [{key}] {val.title()}{marker}")
    raw = input(f"  Choice [{default_key}]: ").strip()
    key = raw if raw in choices else default_key
    return choices[key]


def _config_path() -> Path:
    """Return the path to the global mip.config.json."""
    script_dir = Path(__file__).parent.parent.resolve()
    return script_dir / "mip.config.json"


def _load_global_config() -> dict:
    cfg_path = _config_path()
    if cfg_path.exists():
        with open(cfg_path) as f:
            return json.load(f)
    return {}


def _write_global_config(config: dict):
    cfg_path = _config_path()
    with open(cfg_path, "w") as f:
        json.dump(config, f, indent=2)
    _ok(f"Config saved: {cfg_path}")


# ── Check steps ──────────────────────────────────────────────────────────────

def check_python() -> bool:
    ver = sys.version_info
    if ver >= MIN_PYTHON:
        _ok(f"Python {ver.major}.{ver.minor}.{ver.micro} — OK")
        return True
    else:
        _err(f"Python {ver.major}.{ver.minor} found — 3.11+ required")
        print("  Download from: https://python.org/downloads")
        return False


def check_ffmpeg() -> bool:
    path = shutil.which("ffmpeg")
    if path:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, text=True, timeout=5
            )
            first_line = result.stdout.splitlines()[0] if result.stdout else "unknown version"
            _ok(f"ffmpeg found: {first_line[:60]}")
            return True
        except Exception:
            pass
    _err("ffmpeg not found in PATH")
    _print_ffmpeg_install_guide()
    return False


def _print_ffmpeg_install_guide():
    system = platform.system()
    print("\n  ffmpeg installation guide:")
    if system == "Windows":
        print("    1. Go to: https://ffmpeg.org/download.html")
        print("    2. Click Windows → download the gyan.dev Release Full build")
        print("    3. Extract to C:\\ffmpeg\\")
        print("    4. Add C:\\ffmpeg\\bin to your system PATH:")
        print("       Win + X → System → Advanced system settings")
        print("       → Environment Variables → System Variables → Path → Edit")
        print("       → New → C:\\ffmpeg\\bin → OK")
        print("    5. Close and reopen your terminal, then run: ffmpeg -version")
    elif system == "Darwin":
        print("    Run: brew install ffmpeg")
        print("    (Requires Homebrew: https://brew.sh)")
    else:
        print("    Run: sudo apt install ffmpeg   (Ubuntu/Debian)")
        print("    Or:  sudo dnf install ffmpeg   (Fedora)")


def check_dependencies() -> bool:
    all_ok = True
    for pkg in REQUIRED_PACKAGES:
        import_name = IMPORT_CHECK[pkg]
        try:
            __import__(import_name)
            _ok(f"{pkg} — installed")
        except ImportError:
            _warn(f"{pkg} — not found, installing...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                _ok(f"{pkg} — installed successfully")
            else:
                _err(f"{pkg} — installation failed")
                print(f"    Try manually: pip install {pkg}")
                all_ok = False
    return all_ok


# ── Synthetic test video ──────────────────────────────────────────────────────

def generate_test_video(output_path: Path) -> bool:
    """Generate a synthetic ~2MB test video using ffmpeg."""
    if output_path.exists():
        _ok(f"Test video already exists: {output_path.name}")
        return True

    _warn("Generating synthetic test video (~2MB)...")

    # 3-minute video: alternating solid color slides every 20 seconds
    # Each "slide" is a different color with a slide number drawn on it
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
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            _ok(f"Test video generated: {output_path.name} ({size_mb:.1f} MB)")
            return True
        else:
            _err("Test video generation failed")
            if result.stderr:
                print(f"    ffmpeg error: {result.stderr[-200:]}")
            return False
    except subprocess.TimeoutExpired:
        _err("Test video generation timed out")
        return False
    except Exception as e:
        _err(f"Test video generation error: {e}")
        return False


# ── Folder structure ──────────────────────────────────────────────────────────

def create_folder_structure(mip_root: Path) -> bool:
    folders = [
        mip_root,
        mip_root / "tools",
        mip_root / "projects",
        mip_root / "prompt_pack" / "base" / "meeting_types",
        mip_root / "prompt_pack" / "base" / "two_pass",
        mip_root / "prompt_pack" / "claude",
        mip_root / "prompt_pack" / "chatgpt",
        mip_root / "prompt_pack" / "gemini",
    ]
    try:
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
        _ok(f"Folder structure created at: {mip_root}")
        return True
    except PermissionError as e:
        _err(f"Permission denied creating folders: {e}")
        return False


# ── Existing install detection ────────────────────────────────────────────────

def detect_existing_install() -> dict | None:
    cfg_path = _config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


# ── Main setup flow ───────────────────────────────────────────────────────────

def run_setup():
    print("\n" + "═" * 56)
    print("  MeetingTool v2.0 — Setup")
    print("═" * 56)

    # ── Check for existing install ──
    existing = detect_existing_install()
    if existing:
        print(f"\n  Existing MeetingTool installation detected.")
        print(f"  Installed: {existing.get('installed_at', 'unknown date')}")
        print(f"  Root:      {existing.get('mip_root', 'unknown')}")
        print(f"  Provider:  {existing.get('llm_provider', 'unknown')}")
        choice = _ask("Re-run setup? This will update your global config (y/n)", "n")
        if choice.lower() != "y":
            print("\n  Setup cancelled. Your existing config is unchanged.")
            print("  Run 'mip project new' to add a new project.")
            return

    # ── Step 1: Python ──
    _print_step(1, "Python version")
    python_ok = check_python()
    if not python_ok:
        print("\n  Setup cannot continue without Python 3.11+.")
        sys.exit(1)

    # ── Step 2: ffmpeg ──
    _print_step(2, "ffmpeg")
    ffmpeg_ok = check_ffmpeg()
    if not ffmpeg_ok:
        choice = _ask("Continue setup without ffmpeg? (y/n)", "n")
        if choice.lower() != "y":
            print("\n  Install ffmpeg and run 'mip setup' again.")
            sys.exit(1)
        _warn("Continuing without ffmpeg. Frame extraction will not work until ffmpeg is installed.")

    # ── Step 3: Python dependencies ──
    _print_step(3, "Python dependencies")
    deps_ok = check_dependencies()
    if not deps_ok:
        _warn("Some dependencies could not be installed automatically.")
        _warn("Run: pip install opencv-python python-docx click requests")

    # ── Step 4: Configuration ──
    _print_step(4, "Configuration")

    default_root = str(Path.home() / "Documents" / "MeetingTool")
    print(f"\n  Where should MeetingTool store projects and recordings?")
    mip_root_str = _ask("MeetingTool root folder", default_root)
    mip_root = Path(mip_root_str).expanduser().resolve()

    provider = _ask_choice(
        "LLM provider for report generation:",
        {"1": "claude", "2": "chatgpt", "3": "gemini"},
        default_key="1"
    )

    language = _ask_choice(
        "Default report language:",
        {"1": "english", "2": "spanish"},
        default_key="1"
    )

    # ── Step 5: Folder structure ──
    _print_step(5, "Folder structure")
    folders_ok = create_folder_structure(mip_root)
    if not folders_ok:
        print("\n  Setup failed. Check permissions and try again.")
        sys.exit(1)

    # ── Step 6: Test video ──
    _print_step(6, "Test video fixture")
    if ffmpeg_ok:
        test_video_path = mip_root / "tools" / "test_meeting.mp4"
        generate_test_video(test_video_path)
    else:
        _warn("Skipping test video (ffmpeg not available)")

    # ── Step 7: Write global config ──
    _print_step(7, "Global config")
    config = {
        "mip_version": "2.0",
        "mip_root": str(mip_root),
        "llm_provider": provider,
        "default_language": language,
        "installed_at": datetime.now().strftime("%Y-%m-%d"),
    }
    _write_global_config(config)

    # ── Done ──
    print("\n" + "═" * 56)
    print("  MeetingTool installed successfully.")
    print("═" * 56)
    print(f"\n  Root folder : {mip_root}")
    print(f"  Provider    : {provider.title()}")
    print(f"  Language    : {language.title()}")
    print(f"\n  You're ready to go!")
    print(f"\n  Next step — set up your first client project:")
    print(f"\n    Run this command:")
    print(f"\n       python mip.py project new")
    print(f"\n    MeetingTool will ask you for the client name, project name,")
    print(f"    and a few preferences. It takes about 2 minutes.")
    print()

    # ── Summary of issues ──
    issues = []
    if not ffmpeg_ok:
        issues.append("ffmpeg not installed — frame extraction disabled")
    if not deps_ok:
        issues.append("some Python packages missing — run pip install manually")
    if issues:
        print("  Warnings to resolve:")
        for issue in issues:
            _warn(issue)
        print()
