from core.backend_selector import ACTIVE_BACKEND, get_backend


def get_backend_info() -> dict:
    backend = get_backend()

    return {
        "active_backend": ACTIVE_BACKEND,
        "module": backend.__name__,
        "supports_user_services": True,
        "supports_system_services": True,
        "supports_live_updates": False,
        "supports_events": False,
        "supports_dbus": False,
        "notes": "Using systemctl subprocess backend."
    }


def print_backend_info() -> None:
    info = get_backend_info()

    print("Backend information")
    print("-------------------")

    for key, value in info.items():
        print(f"{key}: {value}")
