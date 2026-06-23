from core.backend_selector import get_backend, get_backend_name


def get_backend_info() -> dict:
    backend = get_backend()
    backend_name = get_backend_name()

    if backend_name == "dbus":
        notes = "Using DBus backend for service listing. Actions currently fallback to systemctl."
    else:
        notes = "Using systemctl subprocess backend."

    return {
        "active_backend": backend_name,
        "module": backend.__name__,
        "supports_user_services": True,
        "supports_system_services": True,
        "supports_live_updates": False,
        "supports_events": False,
        "supports_dbus": backend_name == "dbus",
        "notes": notes,
    }


def print_backend_info() -> None:
    info = get_backend_info()

    print("Backend information")
    print("-------------------")

    for key, value in info.items():
        print(f"{key}: {value}")
