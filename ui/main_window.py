# ui/main_window.py

import tkinter as tk
from tkinter import ttk, messagebox

from core.config_loader import load_services
from core.service_manager import (
    list_service_entries,
    start_service,
    stop_service,
    restart_service,
)
from assistant.backend_assistant import get_backend_info


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Linux Service Center")
        self.root.geometry("1100x650")

        self.services = []

        self.build_ui()
        self.refresh_services()

    def build_ui(self):
        backend = get_backend_info()

        header = ttk.Frame(self.root, padding=10)
        header.pack(fill="x")

        ttk.Label(
            header,
            text="Linux Service Center",
            font=("Arial", 18, "bold")
        ).pack(side="left")

        ttk.Label(
            header,
            text=f"Backend: {backend['active_backend']}",
            font=("Arial", 10)
        ).pack(side="right")

        self.tree = ttk.Treeview(
            self.root,
            columns=("scope", "service", "status", "startup"),
            show="headings"
        )

        self.tree.heading("scope", text="Scope")
        self.tree.heading("service", text="Service")
        self.tree.heading("status", text="Status")
        self.tree.heading("startup", text="Startup")

        self.tree.column("scope", width=100)
        self.tree.column("service", width=350)
        self.tree.column("status", width=120)
        self.tree.column("startup", width=120)

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        buttons = ttk.Frame(self.root, padding=10)
        buttons.pack(fill="x")

        ttk.Button(buttons, text="Refresh", command=self.refresh_services).pack(side="left", padx=5)
        ttk.Button(buttons, text="Start", command=self.start_selected).pack(side="left", padx=5)
        ttk.Button(buttons, text="Stop", command=self.stop_selected).pack(side="left", padx=5)
        ttk.Button(buttons, text="Restart", command=self.restart_selected).pack(side="left", padx=5)

    def refresh_services(self):
        self.tree.delete(*self.tree.get_children())
        self.services = []

        saved_services = load_services()

        for service in saved_services:
            self.services.append(service)
            self.tree.insert(
                "",
                "end",
                values=(
                    service.scope,
                    service.service,
                    service.status,
                    service.startup
                )
            )

        ok, system_services = list_service_entries("system")

        if ok:
            for service in system_services[:100]:
                self.services.append(service)
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        service.scope,
                        service.service,
                        service.status,
                        service.startup
                    )
                )
        else:
            messagebox.showerror("Error", str(system_services))

    def get_selected_service(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning("No selection", "Please select a service first.")
            return None

        index = self.tree.index(selected[0])

        if index >= len(self.services):
            return None

        return self.services[index]

    def start_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        ok, message = start_service(service.scope, service.service)
        messagebox.showinfo("Start service", message or str(ok))
        self.refresh_services()

    def stop_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        ok, message = stop_service(service.scope, service.service)
        messagebox.showinfo("Stop service", message or str(ok))
        self.refresh_services()

    def restart_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        ok, message = restart_service(service.scope, service.service)
        messagebox.showinfo("Restart service", message or str(ok))
        self.refresh_services()

    def run(self):
        self.root.mainloop()