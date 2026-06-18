"""
tools/api_config.py — MeetingTool v2.5
=======================================
Centralized API key loading for Anthropic and Google Gemini.

In normal use (dev machine): reads from Windows Credential Manager
via the shared G7 infra/secrets_helper.py.

In frozen binary (PyInstaller): infra/ path is unavailable, so falls
back to keyring directly using the same service name.
"""

import sys
import logging

log = logging.getLogger("api_config")

SERVICE_NAME = "G7_Automatizaciones"
_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
_GEMINI_KEY    = "GEMINI_API_KEY"


def _load_via_infra(key: str) -> str | None:
    """Load key through shared infra/secrets_helper (dev environment)."""
    try:
        from pathlib import Path
        # Resolve infra/ relative to this file's location: tools/ → meetingtool/ → project/ → Cowork/
        cowork_root = Path(__file__).resolve().parents[3]
        infra_path = str(cowork_root)
        if infra_path not in sys.path:
            sys.path.insert(0, infra_path)
        from infra.secrets_helper import get_secret
        return get_secret(key)
    except Exception:
        return None


def _load_via_keyring(key: str) -> str | None:
    """Load key directly from keyring (frozen binary fallback)."""
    try:
        import keyring
        return keyring.get_password(SERVICE_NAME, key) or None
    except Exception:
        return None


def _load_key(key: str) -> str:
    """
    Load a credential by name. Tries infra helper first, then keyring directly.
    Raises RuntimeError with actionable message if not found.
    """
    value = _load_via_infra(key) or _load_via_keyring(key)
    if value:
        return value
    raise RuntimeError(
        f"\n[api_config] '{key}' not found in Windows Credential Manager.\n"
        f"Run: python C:\\Users\\diego\\Documents\\Cowork\\infra\\secrets_manager.py\n"
        f"Then choose option 3 and enter the value for '{key}'.\n"
    )


def get_anthropic_key() -> str:
    return _load_key(_ANTHROPIC_KEY)


def get_gemini_key() -> str:
    return _load_key(_GEMINI_KEY)


def validate_keys() -> dict:
    """
    Check both keys are present. Returns status dict — does not raise.
    Used by the GUI to show key status in settings.
    """
    results = {}
    for name, loader in [("ANTHROPIC_API_KEY", get_anthropic_key),
                         ("GEMINI_API_KEY",    get_gemini_key)]:
        try:
            loader()
            results[name] = True
        except RuntimeError:
            results[name] = False
    return results
