# ui/main_window.py

import tkinter as tk
from tkinter import ttk, messagebox

from core.config_loader import load_services
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


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Linux Service Center")
        self.root.geometry("1100x650")

        self.services = []
        self.visible_services = []
        self.search_var = tk.StringVar()
        self.auto_refresh_enabled = tk.BooleanVar(value=True)
        self.auto_refresh_interval_ms = 10000

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

            self.visible_services.append(service)

            tag = self.get_tag(service.status)

            self.tree.insert(
                "",
                "end",
                values=(
                    service.scope,
                    service.service,
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

    def run(self):
        self.root.mainloop()
