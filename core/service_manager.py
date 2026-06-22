from core.backend_selector import get_backend
from models.service_entry import ServiceEntry


def start_service(scope: str, service: str):
    backend = get_backend()

    return backend.start_service(scope, service)


def stop_service(scope: str, service: str):
    backend = get_backend()

    return backend.stop_service(scope, service)


def restart_service(scope: str, service: str):
    backend = get_backend()

    return backend.restart_service(scope, service)


def enable_service(scope: str, service: str):
    backend = get_backend()

    return backend.enable_service(scope, service)


def disable_service(scope: str, service: str):
    backend = get_backend()

    return backend.disable_service(scope, service)


def get_service_logs(scope: str, service: str, lines: int = 80):
    backend = get_backend()

    return backend.get_service_logs(scope, service, lines)


def normalize_scope(scope: str) -> str:
    scope = (scope or "system").lower().strip()

    return "user" if scope == "user" else "system"


def list_service_entries(scope: str = "system"):
    backend = get_backend()

    return backend.list_service_entries(scope)


def create_service_entry(
    name: str, service: str, scope: str = "system", **kwargs
) -> ServiceEntry:
    return ServiceEntry(
        name=name.strip(),
        service=service.strip(),
        scope=normalize_scope(scope),
        **kwargs
    )


def list_services(scope: str = "system"):
    backend = get_backend()

    return backend.list_services(scope)
