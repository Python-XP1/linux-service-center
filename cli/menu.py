# cli/menu.py

from core.config_loader import load_services
from core.service_manager import (
    list_service_entries,
    start_service as core_start_service,
    stop_service as core_stop_service,
    restart_service as core_restart_service,
)


class CliMenu:
    def run(self):
        while True:
            print()
            print("=" * 40)
            print("Linux Service Center CLI")
            print("=" * 40)
            print("1) Saved services")
            print("2) System services")
            print("3) Start service")
            print("4) Stop service")
            print("5) Restart service")
            print("0) Exit")
            print()

            choice = input("Select: ").strip()

            if choice == "1":
                self.show_saved_services()
            elif choice == "2":
                self.show_system_services()
            elif choice == "3":
                self.start_service()
            elif choice == "4":
                self.stop_service()
            elif choice == "5":
                self.restart_service()
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

    def ask_scope(self):
        scope = input("Scope [system/user] (default: system): ").strip().lower()

        if scope == "user":
            return "user"

        return "system"

    def ask_service_name(self):
        service = input("Service name: ").strip()

        if service and not service.endswith(".service"):
            service += ".service"

        return service

    def confirm_system_action(self, action, service):
        print()
        print(f"You are about to {action} a SYSTEM service:")
        print(f"  {service}")
        print("This may affect your operating system or critical services.")

        answer = input("Continue? [y/N]: ").strip().lower()

        return answer == "y"

    def run_service_action(self, action_name, action_func):
        scope = self.ask_scope()
        service = self.ask_service_name()

        if not service:
            print("No service entered.")
            return

        if scope == "system" and not self.confirm_system_action(action_name, service):
            print("Cancelled.")
            return

        ok, message = action_func(scope, service)

        if ok:
            print("OK")
        else:
            print("FAILED")

        if message:
            print(message)

    def start_service(self):
        self.run_service_action("start", core_start_service)

    def stop_service(self):
        self.run_service_action("stop", core_stop_service)

    def restart_service(self):
        self.run_service_action("restart", core_restart_service)
