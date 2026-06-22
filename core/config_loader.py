import json
from pathlib import Path

from models.service_entry import ServiceEntry


CONFIG_FILE = Path("services.json")


def load_services() -> list[ServiceEntry]:
    if not CONFIG_FILE.exists():
        return []

    with open(CONFIG_FILE, encoding="utf-8") as f:
        data = json.load(f)

    services = []

    for item in data:
        services.append(
            ServiceEntry(
                name=item.get("name", ""),
                service=item.get("service", ""),
                scope=item.get("scope", "system"),
                folder=item.get("folder", ""),
                url=item.get("url", ""),
                working_directory=item.get("working_directory", ""),
                venv_path=item.get("venv_path", ""),
                python_executable=item.get("python_executable", ""),
                start_command=item.get("start_command", ""),
            )
        )

    return services


def add_service_to_config(scope: str, service: str):
    service = service.strip()
    scope = scope.strip()

    if not CONFIG_FILE.exists():
        data = []
    else:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)

    for item in data:
        if item.get("service", "") == service and item.get("scope", "system") == scope:
            return False

    data.append(
        {
            "scope": scope,
            "service": service,
        }
    )

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return True
