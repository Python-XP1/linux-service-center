from backends import systemctl_backend


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
