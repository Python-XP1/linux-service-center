from dataclasses import dataclass

from core.config_loader import load_services
from core.service_manager import list_service_entries
from models.service_entry import ServiceEntry


@dataclass
class ServiceCatalog:
    services: list[ServiceEntry]
    system_available: bool
    system_error: str = ""
    user_available: bool = True
    user_error: str = ""


def is_valid_service(service: ServiceEntry) -> bool:
    return bool(
        service.service
        and service.service != "●"
        and service.service != "not-found"
    )


def load_service_catalog() -> ServiceCatalog:
    """Load saved, system and user services once and deduplicate by scope/unit."""
    services_by_key: dict[tuple[str, str], ServiceEntry] = {}

    def add(service: ServiceEntry) -> None:
        if not is_valid_service(service):
            return
        key = (service.scope, service.service)
        services_by_key.setdefault(key, service)

    for service in load_services():
        add(service)

    system_available, system_result = list_service_entries("system")
    system_error = ""
    if system_available:
        for service in system_result:
            add(service)
    else:
        system_error = str(system_result)

    user_available, user_result = list_service_entries("user")
    user_error = ""
    if user_available:
        for service in user_result:
            add(service)
    else:
        user_error = str(user_result)

    return ServiceCatalog(
        services=list(services_by_key.values()),
        system_available=system_available,
        system_error=system_error,
        user_available=user_available,
        user_error=user_error,
    )


def filter_services(
    services: list[ServiceEntry],
    query: str = "",
    scope: str = "all",
    status: str = "all",
    favorites: set[tuple[str, str]] | None = None,
) -> list[ServiceEntry]:
    query = (query or "").lower().strip()
    scope = (scope or "all").lower().strip()
    status = (status or "all").lower().strip()
    favorites = favorites or set()

    filtered = []
    for service in services:
        searchable = " ".join(
            [
                service.scope,
                service.service,
                service.status,
                service.startup,
                service.name,
            ]
        ).lower()

        if query and query not in searchable:
            continue
        if scope in {"system", "user"} and service.scope != scope:
            continue
        if status in {"active", "inactive"} and service.status != status:
            continue
        filtered.append(service)

    filtered.sort(
        key=lambda service: (
            (service.scope, service.service) not in favorites,
            service.service.lower(),
        )
    )
    return filtered


def find_service(
    services: list[ServiceEntry],
    scope: str,
    service_name: str,
) -> ServiceEntry | None:
    normalized_scope = "user" if scope == "user" else "system"
    normalized_name = service_name.strip()
    if normalized_name and not normalized_name.endswith(".service"):
        normalized_name += ".service"

    for service in services:
        if service.scope == normalized_scope and service.service == normalized_name:
            return service
    return None
