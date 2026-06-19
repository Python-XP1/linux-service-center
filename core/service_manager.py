from backends import systemctl_backend
from models.service_entry import ServiceEntry


def start_service(scope: str, service: str):
    return systemctl_backend.start_service(scope, service)


def stop_service(scope: str, service: str):
    return systemctl_backend.stop_service(scope, service)


def restart_service(scope: str, service: str):
    return systemctl_backend.restart_service(scope, service)


def enable_service(scope: str, service: str):
    return systemctl_backend.enable_service(scope, service)


def disable_service(scope: str, service: str):
    return systemctl_backend.disable_service(scope, service)

def normalize_scope(scope: str) -> str:
    scope = (scope or "system").lower().strip()
    return "user" if scope == "user" else "system"

def list_service_entries(scope: str = "system"):
    return systemctl_backend.list_service_entries(scope)

def create_service_entry(
    name: str,
    service: str,
    scope: str = "system",
    **kwargs
) -> ServiceEntry:
    return ServiceEntry(
        name=name.strip(),
        service=service.strip(),
        scope=normalize_scope(scope),
        **kwargs
    )

def list_services(scope: str = "system"):
    return systemctl_backend.list_services(scope)

