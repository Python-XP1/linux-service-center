import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from core.config_loader import load_services
from core.service_manager import list_service_entries
from ui.diagnostics_window import DiagnosticsWindow
from ui.main_window import MainWindow


class ApplicationWindow(MainWindow):
    """Main application window with diagnostics and complete service discovery."""

    def __init__(self):
        self.diagnostics_window = None
        super().__init__()
        self._install_application_menu()

    def _install_application_menu(self):
        menu_bar = tk.Menu(self.root)
        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(
            label="Diagnostics...",
            command=self.open_diagnostics_window,
            accelerator="Ctrl+D",
        )
        menu_bar.add_cascade(label="Tools", menu=tools_menu)
        self.root.configure(menu=menu_bar)
        self.root.bind("<Control-d>", self.open_diagnostics_window)

    def refresh_services(self):
        """Load saved, system and user services without duplicating entries."""
        services_by_key = {}

        def add_service(service):
            if (
                not service.service
                or service.service == "●"
                or service.service == "not-found"
            ):
                return

            key = (service.scope, service.service)
            services_by_key.setdefault(key, service)

        for service in load_services():
            add_service(service)

        ok, system_services = list_service_entries("system")
        if not ok:
            messagebox.showerror("Error", str(system_services))
            return

        for service in system_services:
            add_service(service)

        user_services_available, user_services = list_service_entries("user")
        if user_services_available:
            for service in user_services:
                add_service(service)

        self.services = list(services_by_key.values())
        self.render_services()

        current_time = datetime.now().strftime("%H:%M:%S")
        if user_services_available:
            self.refresh_status_var.set(f"Last refresh: {current_time}")
        else:
            self.refresh_status_var.set(
                f"Last refresh: {current_time} | User services unavailable"
            )

        self.update_system_metrics()

    def open_diagnostics_window(self, event=None):
        if self.diagnostics_window is not None and self.diagnostics_window.is_open():
            self.diagnostics_window.focus()
            return

        self.diagnostics_window = DiagnosticsWindow(
            self.root,
            is_advanced_mode=self.is_advanced_mode,
            on_close=self._clear_diagnostics_window,
        )

    def _clear_diagnostics_window(self):
        self.diagnostics_window = None
