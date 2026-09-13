from ui import theme

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from diagnostics.process_inspector_adapter import analyze_grouped_query
from diagnostics.system_info import get_system_diagnostics


BG = theme.BG_MAIN
PANEL = theme.BG_PANEL
PANEL_ALT = theme.BG_HEADER
TEXT_BG = theme.BG_MAIN
TEXT_FG = theme.TEXT_PRIMARY
MUTED = theme.TEXT_SECONDARY
ACCENT = theme.ACCENT_GOLD


class DiagnosticsWindow:
    def __init__(
        self,
        parent: tk.Misc,
        is_advanced_mode: Callable[[], bool],
        on_close: Callable[[], None] | None = None,
    ):
        self.parent = parent
        self.is_advanced_mode = is_advanced_mode
        self.on_close = on_close
        self.closed = False
        self.groups = []
        self.visible_command_items = []
        self.selected_group_index = None
        self.analysis_request_id = 0
        self.analysis_running = False
        self.analysis_queue = queue.Queue()
        self.last_advanced_mode = None

        self.window = tk.Toplevel(parent)
        self.window.title("Diagnostics")
        self.window.configure(bg=BG)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._set_responsive_geometry()

        self.query_var = tk.StringVar(master=self.window)
        self.status_var = tk.StringVar(master=self.window, value="Ready.")
        self.mode_var = tk.StringVar(master=self.window)

        self._configure_styles()
        self._build_ui()
        self.refresh_system_overview()
        self.refresh_mode_state()
        self.window.after(500, self._poll_mode)

    def _set_responsive_geometry(self):
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        width = max(700, min(1180, screen_width - 40))
        height = max(460, min(760, screen_height - 80))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.minsize(min(760, width), min(520, height))

    def _configure_styles(self):
        style = ttk.Style(self.window)
        style.configure("Diagnostics.TNotebook", background=BG, borderwidth=0)
        style.configure(
            "Diagnostics.TNotebook.Tab",
            background=PANEL_ALT,
            foreground=TEXT_FG,
            padding=(16, 8),
        )
        style.map(
            "Diagnostics.TNotebook.Tab",
            background=[("selected", theme.SELECTED)],
            foreground=[("selected", theme.TEXT_PRIMARY)],
        )
        style.configure(
            "Diagnostics.Treeview",
            background=PANEL,
            foreground=theme.TEXT_PRIMARY,
            fieldbackground=PANEL,
            rowheight=27,
            bordercolor=theme.BORDER_GOLD,
            borderwidth=1,
        )
        style.configure(
            "Diagnostics.Treeview.Heading",
            bordercolor=theme.BORDER_GOLD,
            background=PANEL_ALT,
            foreground=theme.TEXT_PRIMARY,
            font=("Arial", 10, "bold"),
        )
        style.map(
            "Diagnostics.Treeview",
            background=[("selected", theme.SELECTED)],
            foreground=[("selected", theme.TEXT_PRIMARY)],
        )

    def _build_ui(self):
        header = tk.Frame(self.window, bg=BG, padx=18, pady=14)
        header.pack(fill="x")
        header.grid_columnconfigure(1, weight=1)

        tk.Label(
            header,
            text="Diagnostics",
            bg=BG,
            fg=theme.TEXT_PRIMARY,
            font=("Arial", 24, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="Read-only analysis. Commands are never executed automatically.",
            bg=BG,
            fg=MUTED,
            font=("Arial", 10),
            justify="right",
            anchor="e",
            wraplength=520,
        ).grid(row=0, column=1, sticky="e", padx=(20, 0))

        notebook = ttk.Notebook(self.window, style="Diagnostics.TNotebook")
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        system_tab = tk.Frame(notebook, bg=BG)
        inspector_tab = tk.Frame(notebook, bg=BG)
        notebook.add(system_tab, text="System Overview")
        notebook.add(inspector_tab, text="Process Inspector")

        self._build_system_tab(system_tab)
        self._build_inspector_tab(inspector_tab)

    def _build_system_tab(self, parent):
        toolbar = tk.Frame(parent, bg=BG, pady=10)
        toolbar.pack(fill="x")

        self._make_button(
            toolbar,
            "Refresh system overview",
            self.refresh_system_overview,
            theme.BG_SECONDARY,
        ).pack(side="left")

        text_frame = tk.Frame(parent, bg=BG)
        text_frame.pack(fill="both", expand=True, pady=(0, 8))
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.system_text = tk.Text(
            text_frame,
            **theme.INPUT,
            relief="flat",
            wrap="none",
            font=("Courier New", 10),
        )
        system_y = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.system_text.yview,
        )
        system_x = ttk.Scrollbar(
            text_frame,
            orient="horizontal",
            command=self.system_text.xview,
        )
        self.system_text.configure(
            yscrollcommand=system_y.set,
            xscrollcommand=system_x.set,
        )

        self.system_text.grid(row=0, column=0, sticky="nsew")
        system_y.grid(row=0, column=1, sticky="ns")
        system_x.grid(row=1, column=0, sticky="ew")

    def _build_inspector_tab(self, parent):
        search_frame = tk.Frame(parent, bg=BG, pady=10)
        search_frame.pack(fill="x")
        search_frame.grid_columnconfigure(1, weight=1)

        tk.Label(
            search_frame,
            text="PID, process, command or service",
            bg=BG,
            fg=theme.TEXT_SECONDARY,
            font=("Arial", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.query_entry = tk.Entry(
            search_frame,
            **theme.INPUT,
            textvariable=self.query_var,
            relief="flat",
            font=("Arial", 11),
        )
        self.query_entry.grid(row=0, column=1, sticky="ew")
        self.query_entry.bind("<Return>", self.start_analysis)

        self.analyze_button = self._make_button(
            search_frame,
            "Analyze",
            self.start_analysis,
            theme.ENABLE_BG,
        )
        self.analyze_button.grid(row=0, column=2, sticky="e", padx=(10, 0))

        info_row = tk.Frame(parent, bg=BG)
        info_row.pack(fill="x", pady=(0, 8))
        info_row.grid_columnconfigure(1, weight=1)

        tk.Label(
            info_row,
            textvariable=self.mode_var,
            bg=BG,
            fg=ACCENT,
            font=("Arial", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            info_row,
            textvariable=self.status_var,
            bg=BG,
            fg=MUTED,
            font=("Arial", 10),
            anchor="e",
            justify="right",
            wraplength=620,
        ).grid(row=0, column=1, sticky="ew", padx=(16, 0))

        content = tk.PanedWindow(
            parent,
            orient="vertical",
            bg=BG,
            sashwidth=6,
            relief="flat",
        )
        content.pack(fill="both", expand=True, pady=(0, 8))

        results_frame = tk.Frame(content, bg=BG)
        details_frame = tk.PanedWindow(
            content,
            orient="horizontal",
            bg=BG,
            sashwidth=6,
            relief="flat",
        )
        content.add(results_frame, minsize=150)
        content.add(details_frame, minsize=220)

        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        self.result_tree = ttk.Treeview(
            results_frame,
            columns=("manager", "target", "health", "restart", "processes", "confidence"),
            show="headings",
            style="Diagnostics.Treeview",
        )
        columns = (
            ("manager", "Manager", 150, 110),
            ("target", "Unit / Slice / Process", 300, 190),
            ("health", "Health", 100, 80),
            ("restart", "Restart Policy", 120, 100),
            ("processes", "Processes", 80, 70),
            ("confidence", "Confidence", 90, 80),
        )
        for column, label, width, minwidth in columns:
            self.result_tree.heading(column, text=label)
            self.result_tree.column(
                column,
                width=width,
                minwidth=minwidth,
                anchor="w",
                stretch=True,
            )

        result_y = ttk.Scrollbar(
            results_frame,
            orient="vertical",
            command=self.result_tree.yview,
        )
        result_x = ttk.Scrollbar(
            results_frame,
            orient="horizontal",
            command=self.result_tree.xview,
        )
        self.result_tree.configure(
            yscrollcommand=result_y.set,
            xscrollcommand=result_x.set,
        )

        self.result_tree.tag_configure(
            "healthy",
            background=theme.ACTIVE_BG,
            foreground=theme.ACTIVE_FG,
        )
        self.result_tree.tag_configure(
            "orphaned",
            background=theme.INACTIVE_BG,
            foreground=theme.INACTIVE_FG,
        )
        self.result_tree.tag_configure(
            "unknown",
            background=theme.NEUTRAL_BG,
            foreground=theme.TEXT_SECONDARY,
        )
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        result_y.grid(row=0, column=1, sticky="ns")
        result_x.grid(row=1, column=0, sticky="ew")
        self.result_tree.bind("<<TreeviewSelect>>", self._show_selected_group)

        detail_panel = tk.LabelFrame(
            details_frame,
            **theme.BORDER,
            text="Analysis details",
            bg=BG,
            fg=theme.TEXT_PRIMARY,
            font=("Arial", 10, "bold"),
            padx=8,
            pady=8,
        )
        command_panel = tk.LabelFrame(
            details_frame,
            **theme.BORDER,
            text="Copyable commands",
            bg=BG,
            fg=theme.TEXT_PRIMARY,
            font=("Arial", 10, "bold"),
            padx=8,
            pady=8,
        )
        details_frame.add(detail_panel, minsize=360)
        details_frame.add(command_panel, minsize=300)

        detail_panel.grid_rowconfigure(0, weight=1)
        detail_panel.grid_columnconfigure(0, weight=1)

        self.detail_text = tk.Text(
            detail_panel,
            **theme.INPUT,
            relief="flat",
            wrap="none",
            font=("Courier New", 9),
        )
        detail_y = ttk.Scrollbar(
            detail_panel,
            orient="vertical",
            command=self.detail_text.yview,
        )
        detail_x = ttk.Scrollbar(
            detail_panel,
            orient="horizontal",
            command=self.detail_text.xview,
        )
        self.detail_text.configure(
            yscrollcommand=detail_y.set,
            xscrollcommand=detail_x.set,
        )

        self.detail_text.grid(row=0, column=0, sticky="nsew")
        detail_y.grid(row=0, column=1, sticky="ns")
        detail_x.grid(row=1, column=0, sticky="ew")

        command_panel.grid_rowconfigure(0, weight=1)
        command_panel.grid_columnconfigure(0, weight=1)

        self.commands_listbox = tk.Listbox(
            command_panel,
            **theme.BORDER,
            bg=TEXT_BG,
            fg=TEXT_FG,
            selectbackground=theme.SELECTED,
            selectforeground=theme.TEXT_PRIMARY,
            relief="flat",
            font=("Courier New", 9),
            selectmode="extended",
        )
        command_y = ttk.Scrollbar(
            command_panel,
            orient="vertical",
            command=self.commands_listbox.yview,
        )
        command_x = ttk.Scrollbar(
            command_panel,
            orient="horizontal",
            command=self.commands_listbox.xview,
        )
        self.commands_listbox.configure(
            yscrollcommand=command_y.set,
            xscrollcommand=command_x.set,
        )

        self.commands_listbox.grid(row=0, column=0, sticky="nsew")
        command_y.grid(row=0, column=1, sticky="ns")
        command_x.grid(row=1, column=0, sticky="ew")

        self.copy_button = self._make_button(
            command_panel,
            "Copy selected",
            self.copy_selected_commands,
            theme.BG_SECONDARY,
        )
        self.copy_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self._set_text(
            self.detail_text,
            "Enter a PID, process name, command fragment or service name to begin.",
        )
        theme.set_button_state(self.copy_button, "disabled")

    def _make_button(self, parent, text, command, color):
        return tk.Button(
            parent,
            **theme.BUTTON,
            text=text,
            command=command,
            bg=color,
            fg=theme.TEXT_PRIMARY,
            relief="flat",
            padx=16,
            pady=7,
            font=("Arial", 10, "bold"),
        )

    def _set_text(self, widget, value: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def refresh_system_overview(self):
        try:
            diagnostics = get_system_diagnostics()
        except Exception as exc:
            diagnostics = f"Unable to load system diagnostics.\n\n{exc}"
        self._set_text(self.system_text, diagnostics or "No diagnostics available.")

    def start_analysis(self, event=None):
        if self.analysis_running:
            return

        query = self.query_var.get().strip()
        if not query:
            self.status_var.set("Enter a search term first.")
            self.query_entry.focus_set()
            return

        self.analysis_request_id += 1
        request_id = self.analysis_request_id
        self.analysis_running = True
        theme.set_button_state(self.analyze_button, "disabled", text="Analyzing...")
        self.status_var.set(f"Analyzing: {query}")
        self.result_tree.delete(*self.result_tree.get_children())
        self.groups = []
        self.selected_group_index = None
        self.visible_command_items = []
        self.commands_listbox.delete(0, "end")
        theme.set_button_state(self.copy_button, "disabled")
        self._set_text(self.detail_text, "Analysis is running...")

        worker = threading.Thread(
            target=self._analysis_worker,
            args=(request_id, query),
            daemon=True,
        )
        worker.start()
        self.window.after(100, self._poll_analysis_queue)

    def _analysis_worker(self, request_id: int, query: str):
        try:
            groups = analyze_grouped_query(query)
        except Exception as exc:
            self.analysis_queue.put((request_id, None, str(exc)))
        else:
            self.analysis_queue.put((request_id, groups, None))

    def _poll_analysis_queue(self):
        if self.closed:
            return

        handled_current_request = False
        while True:
            try:
                request_id, groups, error = self.analysis_queue.get_nowait()
            except queue.Empty:
                break

            if request_id != self.analysis_request_id:
                continue

            handled_current_request = True
            self._finish_analysis(groups, error)

        if self.analysis_running and not handled_current_request:
            self.window.after(100, self._poll_analysis_queue)

    def _finish_analysis(self, groups, error):
        self.analysis_running = False
        theme.set_button_state(self.analyze_button, "normal", text="Analyze")

        if error:
            self.status_var.set("Analysis failed.")
            self._set_text(self.detail_text, f"Unable to analyze processes.\n\n{error}")
            return

        self.groups = groups or []
        if not self.groups:
            self.status_var.set("No matching processes found.")
            self._set_text(self.detail_text, "No matching processes found.")
            return

        for index, group in enumerate(self.groups):
            primary = group.get("primary", {})
            process = primary.get("process", {})
            manager = primary.get("manager", {})
            confidence = primary.get("confidence", {})
            target = (
                manager.get("unit")
                or manager.get("slice")
                or process.get("name")
                or str(process.get("pid", ""))
            )
            health = manager.get("health", "unknown")
            tag = health if health in {"healthy", "orphaned"} else "unknown"

            self.result_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    manager.get("type", "unknown"),
                    target,
                    health,
                    manager.get("restart_policy", "unknown"),
                    group.get("process_count", 0),
                    f"{confidence.get('score', 0)}/100",
                ),
                tags=(tag,),
            )

        self.status_var.set(f"Found {len(self.groups)} process group(s).")
        first_item = self.result_tree.get_children()[0]
        self.result_tree.selection_set(first_item)
        self.result_tree.focus(first_item)
        self._show_selected_group()

    def _show_selected_group(self, event=None):
        selected = self.result_tree.selection()
        if not selected:
            return

        try:
            index = int(selected[0])
        except (TypeError, ValueError):
            return

        if index < 0 or index >= len(self.groups):
            return

        self.selected_group_index = index
        group = self.groups[index]
        self._set_text(self.detail_text, self._format_group_details(group))
        self._render_commands(group)

    def _format_group_details(self, group: dict) -> str:
        primary = group.get("primary", {})
        process = primary.get("process", {})
        manager = primary.get("manager", {})
        confidence = primary.get("confidence", {})
        advice = primary.get("recovery_advice", {})
        lines = [
            "PROCESS GROUP",
            "-------------",
            f"Key:              {group.get('group_key', '-')}",
            f"Process count:    {group.get('process_count', 0)}",
            "PIDs:             " + ", ".join(str(pid) for pid in group.get("pids", [])),
            "",
            "PRIMARY PROCESS",
            "---------------",
            f"PID:              {process.get('pid', '-')}",
            f"PPID:             {process.get('ppid', '-')}",
            f"Name:             {process.get('name', '-')}",
            f"Command:          {process.get('cmdline', '-')}",
            f"Executable:       {process.get('exe', '-')}",
            f"Working dir:      {process.get('cwd', '-')}",
            f"Owner hint:       {primary.get('owner_hint', '-')}",
            "",
            "MANAGER",
            "-------",
            f"Type:             {manager.get('type', 'unknown')}",
            f"Unit:             {manager.get('unit') or '-'}",
            f"Slice:            {manager.get('slice') or '-'}",
            f"Health:           {manager.get('health', 'unknown')}",
            f"Restart policy:   {manager.get('restart_policy', 'unknown')}",
            f"Description:      {manager.get('description', '-')}",
        ]

        if manager.get("warning"):
            lines.append(f"Warning:          {manager.get('warning')}")

        lines.extend(
            [
                "",
                "CONFIDENCE",
                "----------",
                f"Score:            {confidence.get('score', 0)}/100",
            ]
        )
        lines.extend(f"Signal:           {item}" for item in confidence.get("signals", []))
        lines.extend(f"Warning:          {item}" for item in confidence.get("warnings", []))

        lines.extend(["", "RECOVERY ADVISOR", "----------------"])
        lines.append(f"Summary:          {advice.get('summary', 'No advice available.')}")
        lines.extend(f"Detail:           {item}" for item in advice.get("details", []))
        for number, item in enumerate(advice.get("recommended_order", []), 1):
            lines.append(f"Step {number}:           {item}")

        lines.extend(["", "RELATED PROCESSES", "-----------------"])
        for related in group.get("processes", []):
            lines.append(
                f"{related.get('pid', '-')} -> {related.get('name', '-')} -> "
                f"{related.get('cmdline', '-')}"
            )

        lines.extend(["", "PARENT CHAIN", "------------"])
        parent_chain = primary.get("parent_chain", [])
        if parent_chain:
            for parent in parent_chain:
                lines.append(
                    f"{parent.get('pid', '-')} -> {parent.get('name', '-')} -> "
                    f"{parent.get('cmdline', '-')}"
                )
        else:
            lines.append("No parent chain available.")

        return "\n".join(lines)

    def _render_commands(self, group: dict):
        primary = group.get("primary", {})
        items = primary.get("command_items", [])
        advanced = self._advanced_mode_active()
        self.visible_command_items = [
            item for item in items if advanced or not item.get("requires_advanced", False)
        ]
        hidden_count = len(items) - len(self.visible_command_items)

        self.commands_listbox.delete(0, "end")
        for item in self.visible_command_items:
            prefix = item.get("label", "Command")
            self.commands_listbox.insert("end", f"[{prefix}] {item.get('command', '')}")

        if self.visible_command_items:
            theme.set_button_state(self.copy_button, "normal")
        else:
            self.commands_listbox.insert("end", "No commands available in the current mode.")
            theme.set_button_state(self.copy_button, "disabled")

        if hidden_count:
            self.status_var.set(
                f"{hidden_count} potentially destructive command(s) hidden in Normal Mode."
            )
        elif self.visible_command_items:
            self.status_var.set(
                f"{len(self.visible_command_items)} command(s) available for copying."
            )
        else:
            self.status_var.set("No commands available in the current mode.")

    def copy_selected_commands(self):
        selected = self.commands_listbox.curselection()
        if not selected or not self.visible_command_items:
            self.status_var.set("Select at least one command to copy.")
            return

        commands = [
            self.visible_command_items[index].get("command", "")
            for index in selected
            if index < len(self.visible_command_items)
        ]
        commands = [command for command in commands if command]
        if not commands:
            return

        self.window.clipboard_clear()
        self.window.clipboard_append("\n".join(commands))
        self.status_var.set("Command copied. Nothing was executed.")

    def _advanced_mode_active(self) -> bool:
        try:
            return bool(self.is_advanced_mode())
        except Exception:
            return False

    def refresh_mode_state(self):
        advanced = self._advanced_mode_active()
        self.last_advanced_mode = advanced
        self.mode_var.set(
            "Advanced Mode: all copyable commands visible."
            if advanced
            else "Normal Mode: potentially destructive commands are hidden."
        )

        if self.selected_group_index is not None and self.selected_group_index < len(self.groups):
            self._render_commands(self.groups[self.selected_group_index])

    def _poll_mode(self):
        if self.closed:
            return

        advanced = self._advanced_mode_active()
        if advanced != self.last_advanced_mode:
            self.refresh_mode_state()

        self.window.after(500, self._poll_mode)

    def is_open(self) -> bool:
        return not self.closed and bool(self.window.winfo_exists())

    def focus(self):
        if not self.is_open():
            return
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self):
        if self.closed:
            return

        self.closed = True
        self.analysis_request_id += 1
        if self.on_close is not None:
            self.on_close()
        self.window.destroy()
