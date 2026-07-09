"""
tools/api_config.py — MeetingTool
===================================
Centralized API key loading for Anthropic and Google Gemini.

Keys are stored in the system keychain (Windows Credential Manager, macOS
Keychain, or the platform-appropriate secret store) via the `keyring` library.
They are saved during `mip setup` and never hardcoded or shared.

Each user must set up their own keys. Keys are not shared across machines.
To add or update a key: run `python mip.py setup` and follow the prompts.
"""

import logging

log = logging.getLogger("api_config")

# Keys are looked up in G7_Automatizaciones first (developer machine),
# then in MeetingTool (end-user install). This lets the developer manage
# all credentials from secrets_manager.py without duplicating keys,
# while packaged installs for other users remain self-contained.
_G7_SERVICE      = "G7_Automatizaciones"
SERVICE_NAME     = "MeetingTool"
_ANTHROPIC_KEY   = "ANTHROPIC_API_KEY"
_GEMINI_KEY      = "GEMINI_API_KEY"
_GEMINI_KEY_2    = "GEMINI_API_KEY_2"


def _load_key(key: str) -> str:
    try:
        import keyring
        value = keyring.get_password(_G7_SERVICE, key) or keyring.get_password(SERVICE_NAME, key)
        if value:
            return value
    except Exception as e:
        log.debug(f"keyring error for {key}: {e}")

    raise RuntimeError(
        f"\n[api_config] '{key}' not found in your system keychain.\n"
        f"Run setup to add it:\n\n"
        f"    python mip.py setup\n\n"
        f"You will be prompted to enter your API keys during setup.\n"
        f"Get your keys at:\n"
        f"  Anthropic : https://console.anthropic.com/settings/keys\n"
        f"  Gemini    : https://aistudio.google.com/apikey\n"
    )


def save_key(key: str, value: str) -> None:
    """Save an API key to the MeetingTool keychain entry. Called by mip setup."""
    import keyring
    keyring.set_password(SERVICE_NAME, key, value)
    log.info(f"Key saved to keychain: {key}")


def get_anthropic_key() -> str:
    return _load_key(_ANTHROPIC_KEY)


def get_gemini_key(config: dict | None = None) -> str:
    """
    Return the Gemini API key.

    Checks the project's mip.config.json first ("gemini_api_key" — a team key
    shared across everyone working on that project), then falls back to the
    personal system keychain. Anthropic keys are never looked up this way —
    they stay strictly per-person via the keychain.
    """
    if config and config.get("gemini_api_key"):
        return config["gemini_api_key"]
    return _load_key(_GEMINI_KEY)


def get_gemini_key_2(config: dict | None = None) -> str | None:
    """Return the backup Gemini key (project config first, then keychain), or None."""
    if config and config.get("gemini_api_key_2"):
        return config["gemini_api_key_2"]
    try:
        import keyring
        value = (keyring.get_password(_G7_SERVICE, _GEMINI_KEY_2)
                 or keyring.get_password(SERVICE_NAME, _GEMINI_KEY_2))
        return value if value else None
    except Exception as e:
        log.debug(f"keyring error for {_GEMINI_KEY_2}: {e}")
        return None


def validate_keys() -> dict:
    """
    Check keys are present. Returns status dict — does not raise.
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
    results["GEMINI_API_KEY_2"] = get_gemini_key_2() is not None
    return results
