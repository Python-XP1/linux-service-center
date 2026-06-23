# ui/main_window.py

import json
import subprocess
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox

from diagnostics.system_info import get_system_metrics
from core.config_loader import (
    add_service_to_config,
    load_services,
    remove_service_from_config,
)
from core.service_manager import (
    list_service_entries,
    start_service,
    stop_service,
    restart_service,
    enable_service,
    disable_service,
    get_service_logs,
)
from assistant.backend_assistant import get_backend_info


FAVORITES_FILE = Path("favorites.json")


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Linux Service Center")
        self.root.geometry("1100x650")

        self.services = []
        self.visible_services = []
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="all")
        self.auto_refresh_enabled = tk.BooleanVar(value=True)
        self.auto_refresh_interval_ms = 10000
        self.refresh_status_var = tk.StringVar(value="Last refresh: never")
        self.metrics_var = tk.StringVar(value="🌡️ n/a   💾 n/a   🧠 n/a   ⚙️ n/a")
        self.favorites = self.load_favorites()

        self.build_ui()
        self.refresh_services()
        self.schedule_auto_refresh()

    def build_ui(self):
        backend = get_backend_info()

        self.root.configure(bg="#0f1724")

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background="#121c2b",
            foreground="white",
            fieldbackground="#121c2b",
            rowheight=28,
            bordercolor="#1f2a3a",
            borderwidth=0,
        )

        style.configure(
            "Treeview.Heading",
            background="#1f2a3a",
            foreground="white",
            font=("Arial", 10, "bold"),
        )

        style.map(
            "Treeview",
            background=[("selected", "#2563eb")],
            foreground=[("selected", "white")],
        )

        header = tk.Frame(self.root, bg="#0f1724", padx=18, pady=14)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Linux Service Center",
            bg="#0f1724",
            fg="white",
            font=("Arial", 26, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text=f"Backend: {backend['active_backend']}",
            bg="#0f1724",
            fg="#38bdf8",
            font=("Arial", 11, "bold"),
        ).pack(side="right")

        self.metrics_label = tk.Label(
            self.root,
            textvariable=self.metrics_var,
            bg="#121c2b",
            fg="#e5e7eb",
            font=("Arial", 11, "bold"),
            anchor="w",
            padx=18,
            pady=8,
        )
        self.metrics_label.pack(fill="x", padx=18, pady=(0, 6))

        search_frame = tk.Frame(self.root, bg="#0f1724", padx=18, pady=6)
        search_frame.pack(fill="x")

        tk.Label(
            search_frame,
            text="Search service",
            bg="#0f1724",
            fg="#cbd5e1",
            font=("Arial", 10, "bold"),
        ).pack(side="left", padx=(0, 10))

        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg="#121c2b",
            fg="white",
            insertbackground="white",
            relief="flat",
            font=("Arial", 11),
        )
        search_entry.pack(side="left", fill="x", expand=True)

        filter_frame = tk.Frame(self.root, bg="#0f1724", padx=18, pady=6)
        filter_frame.pack(fill="x")

        for label, value in [
            ("All", "all"),
            ("Active", "active"),
            ("Inactive", "inactive"),
            ("System", "system"),
            ("User", "user"),
        ]:
            tk.Radiobutton(
                filter_frame,
                text=label,
                value=value,
                variable=self.filter_var,
                command=self.render_services,
                bg="#0f1724",
                fg="white",
                selectcolor="#121c2b",
                activebackground="#0f1724",
                activeforeground="white",
                font=("Arial", 10, "bold"),
            ).pack(side="left", padx=6)

        self.search_var.trace_add("write", lambda *_: self.render_services())

        self.tree = ttk.Treeview(
            self.root,
            columns=("scope", "service", "status", "startup"),
            show="headings",
        )

        for col, text, width in [
            ("scope", "Scope", 100),
            ("service", "Service", 390),
            ("status", "Status", 140),
            ("startup", "Startup", 140),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)

        self.tree.tag_configure("active", background="#12351f", foreground="#4ade80")
        self.tree.tag_configure("inactive", background="#3a1717", foreground="#f87171")
        self.tree.tag_configure("unknown", background="#1e293b", foreground="#cbd5e1")

        self.tree.pack(fill="both", expand=True, padx=18, pady=10)

        buttons = tk.Frame(self.root, bg="#0f1724", padx=18, pady=14)
        buttons.pack(fill="x")

        self.make_button(buttons, "Refresh", self.refresh_services, "#334155").pack(
            side="left", padx=6
        )
        self.make_button(
            buttons,
            "Details",
            self.show_service_details,
            "#475569",
        ).pack(side="left", padx=6)
        self.make_button(
            buttons,
            "Favorite",
            self.toggle_selected_favorite,
            "#f59e0b",
        ).pack(side="left", padx=6)
        self.make_button(
            buttons,
            "Add",
            self.add_service_dialog,
            "#0ea5e9",
        ).pack(side="left", padx=6)
        self.make_button(
            buttons,
            "Remove",
            self.remove_selected_service,
            "#be123c",
        ).pack(side="left", padx=6)
        self.make_button(buttons, "Start", self.start_selected, "#15803d").pack(
            side="left", padx=6
        )
        self.make_button(buttons, "Stop", self.stop_selected, "#b91c1c").pack(
            side="left", padx=6
        )
        self.make_button(buttons, "Restart", self.restart_selected, "#c2410c").pack(
            side="left", padx=6
        )
        self.make_button(buttons, "Enable", self.enable_selected, "#2563eb").pack(
            side="left", padx=6
        )
        self.make_button(buttons, "Disable", self.disable_selected, "#64748b").pack(
            side="left", padx=6
        )
        self.make_button(buttons, "Logs", self.show_logs_selected, "#7c3aed").pack(
            side="left", padx=6
        )
        auto_refresh_check = tk.Checkbutton(
            buttons,
            text="Auto refresh",
            variable=self.auto_refresh_enabled,
            bg="#0f1724",
            fg="white",
            selectcolor="#121c2b",
            activebackground="#0f1724",
            activeforeground="white",
            font=("Arial", 10, "bold"),
        )
        auto_refresh_check.pack(side="left", padx=12)
        tk.Label(
            buttons,
            textvariable=self.refresh_status_var,
            bg="#0f1724",
            fg="#94a3b8",
            font=("Arial", 10),
        ).pack(side="left", padx=12)

    def load_favorites(self):
        if not FAVORITES_FILE.exists():
            self.save_favorites(set())
            return set()

        try:
            with open(FAVORITES_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return set()

        return {
            (item.get("scope", "system"), item.get("service", ""))
            for item in data
            if item.get("service", "")
        }

    def save_favorites(self, favorites):
        data = [
            {
                "service": service,
                "scope": scope,
            }
            for scope, service in sorted(favorites)
        ]

        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def favorite_key(self, service):
        return (service.scope, service.service)

    def is_favorite(self, service):
        return self.favorite_key(service) in self.favorites

    def toggle_selected_favorite(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning(
                "No service selected",
                "No service selected.",
            )
            return

        index = self.tree.index(selected[0])

        if index >= len(self.visible_services):
            messagebox.showwarning(
                "No service selected",
                "No service selected.",
            )
            return

        service = self.visible_services[index]
        favorite = self.favorite_key(service)

        if favorite in self.favorites:
            self.favorites.remove(favorite)
        else:
            self.favorites.add(favorite)

        self.save_favorites(self.favorites)
        self.render_services()

    def add_service_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Service")
        dialog.geometry("420x240")
        dialog.configure(bg="#0f1724")

        scope_var = tk.StringVar(value="system")
        service_var = tk.StringVar()

        tk.Label(
            dialog,
            text="Service",
            bg="#0f1724",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 6))

        service_entry = tk.Entry(
            dialog,
            textvariable=service_var,
            bg="#121c2b",
            fg="white",
            insertbackground="white",
            relief="flat",
            font=("Arial", 11),
        )
        service_entry.pack(fill="x", padx=18)
        service_entry.focus_set()

        tk.Label(
            dialog,
            text="Scope",
            bg="#0f1724",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=18, pady=(16, 6))

        scope_frame = tk.Frame(dialog, bg="#0f1724")
        scope_frame.pack(fill="x", padx=18)

        for scope in ["system", "user"]:
            tk.Radiobutton(
                scope_frame,
                text=scope,
                value=scope,
                variable=scope_var,
                bg="#0f1724",
                fg="white",
                selectcolor="#121c2b",
                activebackground="#0f1724",
                activeforeground="white",
                font=("Arial", 10, "bold"),
            ).pack(side="left", padx=(0, 12))

        def save_service():
            service = service_var.get().strip()

            if not service:
                messagebox.showwarning(
                    "Missing service",
                    "Please enter a service name.",
                    parent=dialog,
                )
                return

            was_added = add_service_to_config(scope_var.get(), service)

            if not was_added:
                messagebox.showwarning(
                    "Service already exists",
                    "This service is already saved.",
                    parent=dialog,
                )
                return

            dialog.destroy()
            self.refresh_services()
            messagebox.showinfo("Service added", "Service saved successfully.")

        self.make_button(dialog, "Save", save_service, "#0ea5e9").pack(
            anchor="e",
            padx=18,
            pady=18,
        )

    def remove_selected_service(self):
        service = self.get_selected_service()
        if not service:
            return

        confirm = messagebox.askyesno(
            "Remove service",
            f"Remove this saved service from config?\n\n{service.service}\n\n"
            "This does not stop, disable or delete the real systemd service.",
        )

        if not confirm:
            return

        was_removed = remove_service_from_config(service.scope, service.service)

        if not was_removed:
            messagebox.showwarning(
                "Service not removed",
                "This service is not saved in services.json.",
            )
            return

        self.refresh_services()
        messagebox.showinfo("Service removed", "Service removed from config.")

    def make_button(self, parent, text, command, color):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            relief="flat",
            padx=20,
            pady=8,
            font=("Arial", 10, "bold"),
        )

    def get_tag(self, status):
        if status == "active":
            return "active"
        if status == "inactive":
            return "inactive"
        return "unknown"

    def refresh_services(self):
        self.services = []

        def add_service(service):
            if (
                not service.service
                or service.service == "●"
                or service.service == "not-found"
            ):
                return

            self.services.append(service)

        saved_services = load_services()

        for service in saved_services:
            add_service(service)

        ok, system_services = list_service_entries("system")

        if not ok:
            messagebox.showerror("Error", str(system_services))
            return

        for service in system_services:
            add_service(service)

        self.render_services()
        current_time = datetime.now().strftime("%H:%M:%S")
        self.refresh_status_var.set(f"Last refresh: {current_time}")
        self.update_system_metrics()

    def update_system_metrics(self):
        metrics = get_system_metrics()

        self.metrics_var.set(
            f"🌡️ {metrics['temperature']}   "
            f"💾 Free: {metrics['disk_free']}   "
            f"🧠 RAM: {metrics['memory_available']}   "
            f"⚙️ CPU: {metrics['cpu_load']}"
        )

    def schedule_auto_refresh(self):
        if self.auto_refresh_enabled.get():
            self.refresh_services()

        self.root.after(
            self.auto_refresh_interval_ms,
            self.schedule_auto_refresh,
        )

    def render_services(self):
        self.tree.delete(*self.tree.get_children())
        self.visible_services = []

        query = self.search_var.get().lower().strip()
        active_filter = self.filter_var.get()
        filtered_services = []

        for service in self.services:
            searchable_text = " ".join(
                [
                    service.scope,
                    service.service,
                    service.status,
                    service.startup,
                    service.name,
                ]
            ).lower()

            if query and query not in searchable_text:
                continue

            if active_filter == "active" and service.status != "active":
                continue

            if active_filter == "inactive" and service.status != "inactive":
                continue

            if active_filter == "system" and service.scope != "system":
                continue

            if active_filter == "user" and service.scope != "user":
                continue

            filtered_services.append(service)

        filtered_services.sort(
            key=lambda service: (
                not self.is_favorite(service),
                service.service.lower(),
            )
        )

        for service in filtered_services:
            self.visible_services.append(service)

            tag = self.get_tag(service.status)
            service_name = service.service

            if self.is_favorite(service):
                service_name = f"★ {service_name}"

            self.tree.insert(
                "",
                "end",
                values=(
                    service.scope,
                    service_name,
                    service.status,
                    service.startup,
                ),
                tags=(tag,),
            )

    def get_selected_service(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning(
                "No selection",
                "Please select a service first.",
            )
            return None

        index = self.tree.index(selected[0])

        if index >= len(self.visible_services):
            return None

        return self.visible_services[index]

    def confirm_system_action(self, action, service):
        if service.scope != "system":
            return True

        return messagebox.askyesno(
            "Confirm system action",
            f"You are about to {action} a SYSTEM service:\n\n"
            f"{service.service}\n\n"
            "This may affect your operating system or critical services.\n\n"
            "Continue?",
        )

    def start_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        if not self.confirm_system_action("start", service):
            return

        ok, message = start_service(service.scope, service.service)
        messagebox.showinfo("Start service", message or str(ok))
        self.refresh_services()

    def stop_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        if not self.confirm_system_action("stop", service):
            return

        ok, message = stop_service(service.scope, service.service)
        messagebox.showinfo("Stop service", message or str(ok))
        self.refresh_services()

    def restart_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        if not self.confirm_system_action("restart", service):
            return

        ok, message = restart_service(service.scope, service.service)
        messagebox.showinfo("Restart service", message or str(ok))
        self.refresh_services()

    def enable_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        if not self.confirm_system_action("enable", service):
            return

        ok, message = enable_service(service.scope, service.service)
        messagebox.showinfo("Enable service", message or str(ok))
        self.refresh_services()

    def disable_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        if not self.confirm_system_action("disable", service):
            return

        ok, message = disable_service(service.scope, service.service)
        messagebox.showinfo("Disable service", message or str(ok))
        self.refresh_services()

    def show_logs_selected(self):
        service = self.get_selected_service()
        if not service:
            return

        ok, logs = get_service_logs(service.scope, service.service, lines=80)

        if not logs:
            logs = "No logs available."

        log_window = tk.Toplevel(self.root)
        log_window.title(f"Logs - {service.service}")
        log_window.geometry("900x520")
        log_window.configure(bg="#0f1724")

        text = tk.Text(
            log_window,
            bg="#020617",
            fg="#e5e7eb",
            insertbackground="white",
            relief="flat",
            wrap="word",
            font=("Courier New", 10),
        )
        text.pack(fill="both", expand=True, padx=12, pady=12)

        text.insert("1.0", logs)
        text.configure(state="disabled")

        if not ok:
            messagebox.showwarning(
                "Logs warning",
                "Logs could not be loaded completely. See log window for details.",
            )

    def show_service_details(self):
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning(
                "No service selected",
                "No service selected.",
            )
            return

        index = self.tree.index(selected[0])

        if index >= len(self.visible_services):
            messagebox.showwarning(
                "No service selected",
                "No service selected.",
            )
            return

        service = self.visible_services[index]

        if service.scope == "user":
            cmd = ["systemctl", "--user", "show", service.service]
        else:
            cmd = ["systemctl", "show", service.service]

        fields = [
            "Id",
            "Description",
            "LoadState",
            "ActiveState",
            "UnitFileState",
            "MainPID",
            "ExecMainStartTimestamp",
            "FragmentPath",
        ]

        try:
            result = subprocess.run(cmd, text=True, capture_output=True)
        except OSError:
            details = "Unable to read service details."
        else:
            if result.returncode != 0:
                details = "Unable to read service details."
            else:
                values = {}

                for line in result.stdout.splitlines():
                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    if key in fields:
                        values[key] = value

                details = "\n".join(
                    f"{field}: {values.get(field, '-')}" for field in fields
                )

        details_window = tk.Toplevel(self.root)
        details_window.title("Service Details")
        details_window.geometry("760x420")
        details_window.configure(bg="#0f1724")

        text = tk.Text(
            details_window,
            bg="#020617",
            fg="#e5e7eb",
            insertbackground="white",
            relief="flat",
            wrap="word",
            font=("Courier New", 10),
        )
        text.pack(fill="both", expand=True, padx=12, pady=12)

        text.insert("1.0", details)
        text.configure(state="disabled")

    def run(self):
        self.root.mainloop()
