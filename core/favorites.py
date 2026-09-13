import json
from pathlib import Path


FAVORITES_FILE = Path("favorites.json")


def load_favorites() -> set[tuple[str, str]]:
    if not FAVORITES_FILE.exists():
        save_favorites(set())
        return set()

    try:
        with FAVORITES_FILE.open(encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return set()

    return {
        (item.get("scope", "system"), item.get("service", ""))
        for item in data
        if item.get("service", "")
    }


def save_favorites(favorites: set[tuple[str, str]]) -> None:
    data = [
        {"service": service, "scope": scope}
        for scope, service in sorted(favorites)
    ]
    with FAVORITES_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def toggle_favorite(
    favorites: set[tuple[str, str]],
    scope: str,
    service: str,
) -> tuple[set[tuple[str, str]], bool]:
    updated = set(favorites)
    key = (scope, service)
    if key in updated:
        updated.remove(key)
        return updated, False
    updated.add(key)
    return updated, True
