"""
tools/project.py — MeetingTool v2.0
=====================================
Project creation and management.
Creates project folder structure and generates prompt pack for the configured provider.

Run via: mip project new
"""

import json
from pathlib import Path
from datetime import datetime

from tools.setup import _ok, _warn, _err, _ask, _ask_choice, _load_global_config
from tools.prompt_generator import generate_prompt_pack


# ── Helpers ──────────────────────────────────────────────────────────────────

def _global_config_exists() -> bool:
    from mip import __file__ as mip_file
    cfg = Path(mip_file).parent / "mip.config.json"
    return cfg.exists()


def _get_mip_root() -> Path | None:
    config = _load_global_config()
    if not config:
        return None
    return Path(config["mip_root"]).expanduser().resolve()


def _project_config_path(project_folder: Path) -> Path:
    return project_folder / "mip.config.json"


def _write_project_config(project_folder: Path, config: dict):
    path = _project_config_path(project_folder)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    _ok(f"Project config saved: {path}")


def _load_project_config(project_folder: Path) -> dict:
    path = _project_config_path(project_folder)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _merge_configs(global_cfg: dict, project_cfg: dict) -> dict:
    """Project config values override global config values."""
    merged = {**global_cfg, **project_cfg}
    return merged


# ── Provider reference names ──────────────────────────────────────────────────

PROVIDER_PROJECT_LABELS = {
    "claude":   "Claude Project name",
    "chatgpt":  "ChatGPT Custom GPT name (or leave blank for system prompt mode)",
    "gemini":   "Gemini project reference (or leave blank for system instruction mode)",
}

MEETING_TYPES_DEFAULT = ["discovery", "kickoff", "status", "technical"]


# ── Project creation ──────────────────────────────────────────────────────────

def run_project_new():
    print("\n" + "═" * 56)
    print("  MeetingTool v2.0 — New Project")
    print("═" * 56)

    # ── Load global config ──
    global_config = _load_global_config()
    if not global_config:
        _err("MeetingTool is not set up yet.")
        print("  Run 'mip setup' first.")
        return

    mip_root = Path(global_config["mip_root"]).expanduser().resolve()
    default_provider = global_config.get("llm_provider", "claude")
    default_language = global_config.get("default_language", "english")

    # ── Gather project info ──
    print()
    client = _ask("Client name (e.g. Kroger, Acme Corp)")
    if not client:
        _err("Client name cannot be empty.")
        return

    project_name = _ask("Project name (e.g. RetailBeacon, Q2Analysis)")
    if not project_name:
        _err("Project name cannot be empty.")
        return

    # Sanitize for folder name
    client_folder   = client.replace(" ", "_").replace("/", "-")
    project_folder_name = project_name.replace(" ", "_").replace("/", "-")

    default_project_path = str(mip_root / "projects" / client_folder / project_folder_name)

    print(f"\n  Default project folder: {default_project_path}")
    custom_path = _ask("Project folder path (press Enter to use default)", default_project_path)
    project_path = Path(custom_path).expanduser().resolve()

    # ── Provider ──
    provider_choice = _ask_choice(
        "LLM provider for this project:",
        {"1": "claude", "2": "chatgpt", "3": "gemini"},
        default_key={"claude": "1", "chatgpt": "2", "gemini": "3"}.get(default_provider, "1")
    )

    # ── Provider project reference ──
    label = PROVIDER_PROJECT_LABELS.get(provider_choice, "Project reference")
    provider_ref = _ask(label, "")

    # ── Language ──
    lang_default_key = "1" if default_language == "english" else "2"
    language = _ask_choice(
        "Report language for this project:",
        {"1": "english", "2": "spanish"},
        default_key=lang_default_key
    )

    # ── Custom meeting types ──
    print(f"\n  Base meeting types: {', '.join(MEETING_TYPES_DEFAULT)}")
    custom_raw = _ask(
        "Add custom meeting types? (comma-separated, or press Enter to skip)",
        ""
    )
    custom_types = []
    if custom_raw:
        custom_types = [t.strip().lower().replace(" ", "_") for t in custom_raw.split(",") if t.strip()]
        if custom_types:
            _ok(f"Custom types added: {', '.join(custom_types)}")

    # ── Create folder structure ──
    print()
    try:
        project_path.mkdir(parents=True, exist_ok=True)
        _ok(f"Project folder created: {project_path}")
    except PermissionError as e:
        _err(f"Cannot create project folder: {e}")
        return

    # ── Write project config ──
    project_config = {
        "client": client,
        "project": project_name,
        "llm_provider": provider_choice,
        "llm_project_reference": provider_ref,
        "project_folder": str(project_path),
        "report_language": language,
        "meeting_types": MEETING_TYPES_DEFAULT,
        "custom_meeting_types": custom_types,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
    }
    _write_project_config(project_path, project_config)

    # ── Determine prompt pack file path ──
    provider_folder = {"claude": "claude", "chatgpt": "chatgpt", "gemini": "gemini"}.get(provider_choice, "claude")
    mip_install_dir = Path(__file__).parent.parent
    prompt_file = mip_install_dir / "prompt_pack" / provider_folder / "project_instructions.md"

    # ── Save prompt pack to file ──
    from tools.prompt_generator import generate_prompt_pack as _gen
    pack_content = _gen(_merge_configs(global_config, project_config))
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(pack_content, encoding="utf-8")

    # ── Done ──
    print("\n" + "═" * 56)
    print(f"  Project ready: {client} — {project_name}")
    print("═" * 56)
    print(f"\n  Folder  : {project_path}")
    print(f"  Provider: {provider_choice.title()}")
    print(f"  Language: {language.title()}")

    # ── Next steps — provider-specific ──
    print(f"\n  ─── Next steps ──────────────────────────────────────")

    if provider_choice == "claude":
        print(f"\n  Step 1 — Set up your Claude Project:")
        print(f"    a. Go to claude.ai → Projects → New Project")
        print(f"    b. Name it: {provider_ref or f'{client} — {project_name}'}")
        print(f"    c. Open Project Instructions")
        print(f"    d. Copy everything from this file and paste it there:")
        print(f"\n       {prompt_file}")
        print(f"\n    This only needs to be done once per project.")
    elif provider_choice == "chatgpt":
        print(f"\n  Step 1 — Set up your ChatGPT session:")
        print(f"    At the start of each analysis session, copy everything")
        print(f"    from this file and paste it as the first message:")
        print(f"\n       {prompt_file}")
    else:
        print(f"\n  Step 1 — Set up your Gemini session:")
        print(f"    At the start of each analysis session, copy everything")
        print(f"    from this file and paste it as the System Instruction:")
        print(f"\n       {prompt_file}")

    print(f"\n  Step 2 — Add a meeting to analyze:")
    print(f"    Create a folder for your meeting inside the project folder.")
    print(f"    Name it: MeetingName_YYYYMMDD  (example: Kickoff_20260401)")
    print(f"    Place the Teams recording (.mp4) and transcript (.docx) inside.")
    print(f"\n    Your project folder is:")
    print(f"       {project_path}")

    print(f"\n  Step 3 — Process the meeting:")
    print(f"    Run this command (replace the date and meeting name):")
    print(f"\n       python mip.py run --path \"{project_path / 'MeetingName_YYYYMMDD'}\"")
    print(f"\n    Or for web mode (Claude/ChatGPT/Gemini browser):")
    print(f"\n       python mip.py run --path \"{project_path / 'MeetingName_YYYYMMDD'}\" --web")
    print()


# ── Project list ──────────────────────────────────────────────────────────────

def run_project_list():
    global_config = _load_global_config()
    if not global_config:
        _err("MeetingTool is not set up. Run 'mip setup' first.")
        return

    mip_root = Path(global_config["mip_root"]).expanduser().resolve()
    projects_root = mip_root / "projects"

    if not projects_root.exists():
        print("  No projects found.")
        return

    projects = []
    for client_dir in sorted(projects_root.iterdir()):
        if not client_dir.is_dir():
            continue
        for project_dir in sorted(client_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            cfg_path = project_dir / "mip.config.json"
            if cfg_path.exists():
                try:
                    with open(cfg_path) as f:
                        cfg = json.load(f)
                    projects.append(cfg)
                except Exception:
                    pass

    if not projects:
        print("  No projects found.")
        return

    print(f"\n  {'Client':<20} {'Project':<20} {'Provider':<12} {'Language':<10} {'Created'}")
    print(f"  {'─'*20} {'─'*20} {'─'*12} {'─'*10} {'─'*10}")
    for p in projects:
        print(
            f"  {p.get('client',''):<20} "
            f"{p.get('project',''):<20} "
            f"{p.get('llm_provider',''):<12} "
            f"{p.get('report_language',''):<10} "
            f"{p.get('created_at','')}"
        )
    print()
