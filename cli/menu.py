from core.config_loader import load_services
from core.service_manager import list_service_entries


class CliMenu:
    def run(self):
        while True:
            print()
            print("=" * 40)
            print("Linux Service Center CLI")
            print("=" * 40)
            print("1) Saved services")
            print("2) System services")
            print("0) Exit")
            print()

            choice = input("Select: ").strip()

            if choice == "1":
                self.show_saved_services()
            elif choice == "2":
                self.show_system_services()
            elif choice == "0":
                print("Bye.")
                break
            else:
                print("Invalid selection.")

    def show_saved_services(self):
        services = load_services()

        print()
        print(f"Saved services: {len(services)}")

        for service in services:
            print(f"- [{service.scope}] {service.name} -> {service.service}")

    def show_system_services(self):
        ok, services = list_service_entries("system")

        if not ok:
            print("Could not load system services:")
            print(services)
            return

        print()
        print(f"System services: {len(services)}")

        for service in services[:20]:
            print(f"- {service.service} | {service.status} | {service.name}")
