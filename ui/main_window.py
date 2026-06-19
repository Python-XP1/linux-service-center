from core.config_loader import load_services
from core.service_manager import list_service_entries
from assistant.backend_assistant import get_backend_info


def print_main_window_data():
    print("Linux Service Center - UI Layer")
    print("--------------------------------")

    backend = get_backend_info()

    print(f"Backend: {backend['active_backend']}")
    print(f"Module:  {backend['module']}")
    print()

    saved_services = load_services()

    print(f"Saved services: {len(saved_services)}")

    for service in saved_services:
        print(f"- [{service.scope}] {service.name} -> {service.service}")

    print()

    ok, system_services = list_service_entries("system")

    if not ok:
        print("Could not load system services:")
        print(system_services)
        return

    print(f"Detected system services: {len(system_services)}")

    for service in system_services[:10]:
        print(f"- {service.service} | {service.status} | {service.name}")


if __name__ == "__main__":
    print_main_window_data()
