# cli/menu.py

import getpass
import time
import webbrowser

from core.admin_auth import verify_sudo_password
from core.config_loader import (
    add_service_to_config,
    load_services,
    remove_service_from_config,
)
from core.favorites import (
    load_favorites,
    save_favorites,
    toggle_favorite,
)
from core.service_catalog import (
    filter_services,
    find_service,
    load_service_catalog,
)
from core.service_manager import (
    list_service_entries,
    start_service as core_start_service,
    stop_service as core_stop_service,
    restart_service as core_restart_service,
    enable_service as core_enable_service,
    disable_service as core_disable_service,
    get_service_logs as core_get_service_logs,
)
from diagnostics.process_inspector_adapter import build_command_items
from diagnostics.process_inspector import analyze_query, group_results, print_group_result
from diagnostics.system_info import get_system_metrics


class CliMenu:
    def __init__(self):
        self.advanced_mode = False
        self.advanced_timeout_seconds = 300
        self.advanced_expires_at = None
        self.auto_refresh_interval_seconds = 10

    def run(self):
        while True:
            self._expire_advanced_mode_if_needed()
            print()
            print("=" * 40)
            print("Linux Service Center CLI")
            print("=" * 40)
            print(f"Mode: {'Advanced' if self.advanced_mode else 'Normal'}")
            print("1) Saved services")
            print("2) System services")
            print("3) Start service")
            print("4) Stop service")
            print("5) Restart service")
            print("6) Process Inspector")
            print("7) User services")
            print("8) Enable service")
            print("9) Disable service")
            print("10) Service logs")
            print("11) Enable Advanced Mode")
            print("12) Return to Normal Mode")
            print("13) All services")
            print("14) Search / filter services")
            print("15) Service details")
            print("16) Add saved service")
            print("17) Remove saved service")
            print("18) Toggle favorite")
            print("19) Favorite services")
            print("20) System metrics")
            print("21) Auto-refresh services")
            print("22) Open service URL")
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
            elif choice == "6":
                self.show_process_inspector()
            elif choice == "7":
                self.show_user_services()
            elif choice == "8":
                self.enable_service()
            elif choice == "9":
                self.disable_service()
            elif choice == "10":
                self.show_service_logs()
            elif choice == "11":
                self.enable_advanced_mode()
            elif choice == "12":
                self.disable_advanced_mode()
            elif choice == "13":
                self.show_all_services()
            elif choice == "14":
                self.search_services()
            elif choice == "15":
                self.show_service_details()
            elif choice == "16":
                self.add_saved_service()
            elif choice == "17":
                self.remove_saved_service()
            elif choice == "18":
                self.toggle_favorite_service()
            elif choice == "19":
                self.show_favorite_services()
            elif choice == "20":
                self.show_system_metrics()
            elif choice == "21":
                self.watch_services()
            elif choice == "22":
                self.open_service_url()
            elif choice == "0":
                print("Bye.")
                break
            else:
                print("Invalid selection.")

    def enable_advanced_mode(self):
        if self.is_advanced_mode():
            self._touch_advanced_mode()
            print("Advanced Mode is already active.")
            return

        print()
        print("Advanced Mode Warning")
        print("Service changes may affect your operating system or critical services.")
        answer = input("Continue to administrator authentication? [y/N]: ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            return

        password = getpass.getpass("Administrator password: ")
        if not verify_sudo_password(password):
            print("Permission denied: administrator authentication failed.")
            return

        self.advanced_mode = True
        self._touch_advanced_mode()
        print("Advanced Mode enabled for 5 minutes of inactivity.")

    def disable_advanced_mode(self, silent: bool = False):
        was_advanced = self.advanced_mode
        self.advanced_mode = False
        self.advanced_expires_at = None
        if not silent:
            print("Advanced Mode disabled." if was_advanced else "Normal Mode is already active.")

    def _expire_advanced_mode_if_needed(self):
        if (
            self.advanced_mode
            and self.advanced_expires_at is not None
            and time.monotonic() >= self.advanced_expires_at
        ):
            self.advanced_mode = False
            self.advanced_expires_at = None
            print("Advanced Mode expired due to inactivity.")

    def _touch_advanced_mode(self):
        if self.advanced_mode:
            self.advanced_expires_at = time.monotonic() + self.advanced_timeout_seconds

    def is_advanced_mode(self) -> bool:
        self._expire_advanced_mode_if_needed()
        return self.advanced_mode

    def require_advanced_mode(self) -> bool:
        if not self.is_advanced_mode():
            print("Advanced Mode required. Select option 11 first.")
            return False
        self._touch_advanced_mode()
        return True

    def _load_catalog(self):
        catalog = load_service_catalog()
        if not catalog.system_available:
            print(f"Warning: system services unavailable: {catalog.system_error}")
        if not catalog.user_available:
            print(f"Warning: user services unavailable: {catalog.user_error}")
        return catalog

    def _print_service_list(self, title, services):
        favorites = load_favorites()
        print()
        print(f"{title}: {len(services)}")
        for service in services:
            favorite = "★ " if (service.scope, service.service) in favorites else ""
            print(
                f"- {favorite}[{service.scope}] {service.service} | "
                f"{service.status} | {service.startup} | {service.name}"
            )

    def _ask_catalog_service(self):
        scope = self.ask_scope()
        service_name = self.ask_service_name()
        if not service_name:
            print("No service entered.")
            return None

        catalog = self._load_catalog()
        service = find_service(catalog.services, scope, service_name)
        if service is None:
            print(f"Service not found in catalog: [{scope}] {service_name}")
            return None
        return service

    def show_process_inspector(self):
        query = input("PID, process name, command fragment or service name: ").strip()
        if not query:
            print("No query entered.")
            return

        results = analyze_query(query)
        if not results:
            print("No matching processes found.")
            return

        print("Suggested commands are never executed automatically.")
        for group in group_results(results):
            items = build_command_items(group["primary"])
            primary = group["primary"].copy()
            for item in items:
                primary[item["source_key"]] = []
            print_group_result({**group, "primary": primary})
            for item in items:
                safety = "ADVANCED" if item["requires_advanced"] else "READ-ONLY"
                print(f"{item['label']}: [{safety}] {item['command']}")

    def show_saved_services(self):
        services = load_services()

        print()
        print(f"Saved services: {len(services)}")

        for service in services:
            print(f"- [{service.scope}] {service.name} -> {service.service}")

    def show_services(self, scope: str):
        ok, services = list_service_entries(scope)
        label = "User" if scope == "user" else "System"

        if not ok:
            print(f"Could not load {scope} services:")
            print(services)
            return

        print()
        print(f"{label} services: {len(services)}")

        for service in services:
            print(
                f"- {service.service} | {service.status} | {service.startup} | {service.name}"
            )

    def show_system_services(self):
        self.show_services("system")

    def show_user_services(self):
        self.show_services("user")

    def show_all_services(self):
        catalog = self._load_catalog()
        favorites = load_favorites()
        services = filter_services(catalog.services, favorites=favorites)
        self._print_service_list("All services", services)

    def search_services(self):
        query = input("Search text (blank = all): ").strip()
        scope = input("Scope [all/system/user] (default: all): ").strip().lower() or "all"
        status = input("Status [all/active/inactive] (default: all): ").strip().lower() or "all"
        if scope not in {"all", "system", "user"}:
            scope = "all"
        if status not in {"all", "active", "inactive"}:
            status = "all"

        catalog = self._load_catalog()
        favorites = load_favorites()
        services = filter_services(
            catalog.services,
            query=query,
            scope=scope,
            status=status,
            favorites=favorites,
        )
        self._print_service_list("Matching services", services)

    def show_service_details(self):
        service = self._ask_catalog_service()
        if service is None:
            return

        print()
        print("Service details")
        print("---------------")
        for label, value in (
            ("Scope", service.scope),
            ("Service", service.service),
            ("Name", service.name),
            ("Status", service.status),
            ("Startup", service.startup),
            ("Uptime", service.uptime),
            ("URL", service.url),
            ("Folder", service.folder),
            ("Working directory", service.working_directory),
            ("Virtualenv", service.venv_path),
            ("Python", service.python_executable),
            ("Start command", service.start_command),
        ):
            print(f"{label}: {value or '-'}")

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
        if not self.require_advanced_mode():
            return

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

    def enable_service(self):
        self.run_service_action("enable", core_enable_service)

    def disable_service(self):
        self.run_service_action("disable", core_disable_service)

    def show_service_logs(self):
        scope = self.ask_scope()
        service = self.ask_service_name()

        if not service:
            print("No service entered.")
            return

        ok, message = core_get_service_logs(scope, service)
        print("OK" if ok else "FAILED")
        if message:
            print(message)

    def add_saved_service(self):
        if not self.require_advanced_mode():
            return

        scope = self.ask_scope()
        service = self.ask_service_name()
        if not service:
            print("No service entered.")
            return

        if add_service_to_config(scope, service):
            print(f"Saved service added: [{scope}] {service}")
        else:
            print("Service is already saved.")

    def remove_saved_service(self):
        if not self.require_advanced_mode():
            return

        scope = self.ask_scope()
        service = self.ask_service_name()
        if not service:
            print("No service entered.")
            return

        answer = input(f"Remove [{scope}] {service} from saved services? [y/N]: ").strip().lower()
        if answer != "y":
            print("Cancelled.")
            return

        if remove_service_from_config(scope, service):
            print("Saved service removed. The real systemd service was not changed.")
        else:
            print("Service is not present in saved services.")

    def toggle_favorite_service(self):
        service = self._ask_catalog_service()
        if service is None:
            return

        favorites = load_favorites()
        favorites, added = toggle_favorite(favorites, service.scope, service.service)
        save_favorites(favorites)
        print("Added to favorites." if added else "Removed from favorites.")

    def show_favorite_services(self):
        favorites = load_favorites()
        catalog = self._load_catalog()
        services = [
            service
            for service in catalog.services
            if (service.scope, service.service) in favorites
        ]
        services.sort(key=lambda service: service.service.lower())
        self._print_service_list("Favorite services", services)

    def show_system_metrics(self):
        metrics = get_system_metrics()
        print()
        print("System metrics")
        print("--------------")
        print(f"Temperature: {metrics['temperature']}")
        print(f"Disk free:   {metrics['disk_free']}")
        print(f"RAM avail.:  {metrics['memory_available']}")
        print(f"CPU load:    {metrics['cpu_load']}")

    def watch_services(self):
        print("Auto-refresh active every 10 seconds. Press Ctrl+C to stop.")
        try:
            while True:
                catalog = self._load_catalog()
                favorites = load_favorites()
                services = filter_services(catalog.services, favorites=favorites)
                print("\033[2J\033[H", end="")
                self._print_service_list("All services", services)
                time.sleep(self.auto_refresh_interval_seconds)
        except KeyboardInterrupt:
            print("\nAuto-refresh stopped.")

    def open_service_url(self):
        service = self._ask_catalog_service()
        if service is None:
            return
        if not service.url:
            print("This service has no configured URL.")
            return

        opened = webbrowser.open(service.url)
        print(f"Opened: {service.url}" if opened else f"Could not open: {service.url}")
