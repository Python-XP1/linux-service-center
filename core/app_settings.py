import json
from pathlib import Path


SETTINGS_FILE = Path("settings.json")
DEFAULT_SETTINGS = {
    "mode": "normal",
    "skip_advanced_warning": False,
}


def load_settings():
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, json.JSONDecodeError):
        settings = DEFAULT_SETTINGS.copy()

    changed = False

    for key, value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = value
            changed = True

    if settings.get("mode") not in {"normal", "advanced"}:
        settings["mode"] = DEFAULT_SETTINGS["mode"]
        changed = True

    if changed:
        save_settings(settings)

    return settings


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)


def get_mode():
    return load_settings().get("mode", DEFAULT_SETTINGS["mode"])


def set_mode(mode):
    settings = load_settings()
    settings["mode"] = mode if mode in {"normal", "advanced"} else "normal"
    save_settings(settings)


def get_skip_advanced_warning():
    return bool(
        load_settings().get(
            "skip_advanced_warning",
            DEFAULT_SETTINGS["skip_advanced_warning"],
        )
    )


def set_skip_advanced_warning(value):
    settings = load_settings()
    settings["skip_advanced_warning"] = bool(value)
    save_settings(settings)
