from ui import theme

import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from core.favorites import load_favorites as core_load_favorites
from core.favorites import save_favorites as core_save_favorites
from core.service_catalog import load_service_catalog
from ui.diagnostics_window import DiagnosticsWindow
from ui.main_window import MainWindow


READ_ONLY_ACTIONS = ("Refresh", "Details", "Favorite", "Logs", "Open URL")
WRITE_ACTIONS = ("Add", "Remove", "Start", "Stop", "Restart", "Enable", "Disable")
ACTION_FRAME_PADY = 7
ACTION_BUTTON_PADY = 5
ACTION_ROW_GAP = 4
BOTTOM_SAFE_AREA = 28
LOGO_PATH = Path(__file__).resolve().parent.parent / "logo.PNG"
LOGO_MAX_SIZE = 56
GITHUB_URL = "https://github.com/Python-XP1/linux-service-center"
APP_STATUS = "Development build"


class ApplicationWindow(MainWindow):
    """Main application window with diagnostics and complete service discovery."""

    def __init__(self):
        self.diagnostics_window = None
        self.about_window = None
        self.logo_image = None
        self.logo_label = None
        super().__init__()
        self._install_header_logo()
        self._reflow_action_bar()
        self._install_application_menu()

    def load_favorites(self):
        """Use the shared favorites store also used by the CLI."""
        return core_load_favorites()

    def save_favorites(self, favorites):
        """Persist favorites through the shared core store."""
        core_save_favorites(favorites)

    def _find_title_label(self):
        """Find the title label anywhere below the root widget tree."""
        pending = list(self.root.winfo_children())

        while pending:
            widget = pending.pop(0)

            try:
                if widget.cget("text") == "Linux Service Center":
                    return widget
            except (tk.TclError, AttributeError):
                pass

            try:
                pending.extend(widget.winfo_children())
            except (tk.TclError, AttributeError):
                pass

        return None

    def _install_header_logo(self):
        """Place the project logo directly before the main title when available."""
        # Pillow is an optional visual enhancement. The application must remain
        # fully usable when it is not installed; in that case only the logo is omitted.
        if Image is None or ImageTk is None:
            return

        if not LOGO_PATH.is_file():
            return

        title_label = self._find_title_label()
        if title_label is None:
            return

        header = title_label.master
        if header is None:
            return

        try:
            with Image.open(LOGO_PATH) as source:
                pil_image = source.convert("RGBA")
            width, height = pil_image.size
            max_dimension = max(width, height)
            if max_dimension > LOGO_MAX_SIZE:
                scale = LOGO_MAX_SIZE / max_dimension
                new_size = (
                    max(1, round(width * scale)),
                    max(1, round(height * scale)),
                )
                resampling = getattr(Image, "Resampling", Image)
                pil_image = pil_image.resize(new_size, resampling.LANCZOS)
            image = ImageTk.PhotoImage(pil_image, master=self.root)
        except (OSError, ValueError, tk.TclError, RuntimeError, AttributeError):
            return

        # Re-pack only the left title group. Right-aligned mode/backend controls
        # keep their existing geometry and callbacks.
        title_label.pack_forget()
        self.logo_label = tk.Label(
            header,
            image=image,
            bg=theme.BG_MAIN,
            bd=0,
            highlightthickness=0,
        )
        self.logo_label.pack(side="left", padx=(0, 10))
        title_label.pack(side="left")

        # Tkinter images need a live Python reference for as long as they are shown.
        self.logo_image = image

    def _reflow_action_bar(self):
        """Arrange actions in responsive rows and keep status above desktop panels."""
        action_frame = self.add_button.master
        widgets = list(action_frame.winfo_children())
        widgets_by_text = {}
        auto_refresh = None
        refresh_status = None

        for widget in widgets:
            try:
                text = widget.cget("text")
            except tk.TclError:
                text = ""

            if text:
                widgets_by_text[text] = widget

            if text == "Auto refresh":
                auto_refresh = widget

            try:
                textvariable = widget.cget("textvariable")
            except tk.TclError:
                textvariable = ""

            if textvariable and str(textvariable) == str(self.refresh_status_var):
                refresh_status = widget

        # Every child in this frame was originally packed by MainWindow.build_ui().
        # Forget that geometry first; using one geometry manager per parent keeps
        # Tkinter predictable and allows the controls to stretch with the window.
        for widget in widgets:
            widget.pack_forget()

        # Keep the action area compact, while reserving a small internal safe area
        # below the status row. On desktops whose panel overlays maximized windows,
        # the spacer may be covered while the actual controls remain visible.
        action_frame.configure(pady=ACTION_FRAME_PADY)

        for column in range(7):
            action_frame.grid_columnconfigure(column, weight=1, uniform="action")

        for column, label in enumerate(READ_ONLY_ACTIONS):
            widget = widgets_by_text.get(label)
            if widget is not None:
                widget.configure(pady=ACTION_BUTTON_PADY)
                widget.grid(
                    row=0,
                    column=column,
                    padx=4,
                    pady=(0, ACTION_ROW_GAP),
                    sticky="ew",
                )

        for column, label in enumerate(WRITE_ACTIONS):
            widget = widgets_by_text.get(label)
            if widget is not None:
                widget.configure(pady=ACTION_BUTTON_PADY)
                widget.grid(
                    row=1,
                    column=column,
                    padx=4,
                    pady=(0, ACTION_ROW_GAP),
                    sticky="ew",
                )

        if auto_refresh is not None:
            auto_refresh.grid(
                row=2,
                column=0,
                columnspan=2,
                padx=6,
                pady=(0, 0),
                sticky="w",
            )

        if refresh_status is not None:
            refresh_status.grid(
                row=2,
                column=2,
                columnspan=5,
                padx=6,
                pady=(0, 0),
                sticky="e",
            )

        action_frame.grid_rowconfigure(3, minsize=BOTTOM_SAFE_AREA)

    def _install_application_menu(self):
        menu_bar = tk.Menu(self.root, **theme.MENU)
        tools_menu = tk.Menu(menu_bar, tearoff=0, **theme.MENU)
        tools_menu.add_command(
            label="Diagnostics...",
            command=self.open_diagnostics_window,
            accelerator="Ctrl+D",
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="GitHub Repository",
            command=self.open_github_repository,
        )
        tools_menu.add_command(
            label="About Linux Service Center...",
            command=self.show_about_window,
        )
        menu_bar.add_cascade(label="Tools", menu=tools_menu)
        self.root.configure(menu=menu_bar)
        self.root.bind("<Control-d>", self.open_diagnostics_window)

    def open_github_repository(self):
        """Open the public project repository in the system default browser."""
        try:
            return webbrowser.open(GITHUB_URL)
        except webbrowser.Error:
            return False

    def show_about_window(self):
        """Show a small themed project-information window."""
        if self.about_window is not None:
            try:
                if self.about_window.winfo_exists():
                    self.about_window.lift()
                    self.about_window.focus_force()
                    return
            except tk.TclError:
                pass

        about = tk.Toplevel(self.root)
        self.about_window = about
        about.title("About Linux Service Center")
        about.configure(bg=theme.BG_MAIN)
        about.resizable(False, False)
        about.transient(self.root)
        about.protocol("WM_DELETE_WINDOW", self._close_about_window)

        body = tk.Frame(
            about,
            bg=theme.BG_PANEL,
            highlightbackground=theme.BORDER_GOLD,
            highlightthickness=1,
            bd=0,
        )
        body.pack(fill="both", expand=True, padx=18, pady=18)

        if self.logo_image is not None:
            tk.Label(
                body,
                image=self.logo_image,
                bg=theme.BG_PANEL,
                bd=0,
                highlightthickness=0,
            ).pack(pady=(18, 8))

        tk.Label(
            body,
            text="Linux Service Center",
            bg=theme.BG_PANEL,
            fg=theme.TEXT_PRIMARY,
            font=("Arial", 18, "bold"),
        ).pack(padx=28, pady=(18 if self.logo_image is None else 0, 4))

        tk.Label(
            body,
            text=APP_STATUS,
            bg=theme.BG_PANEL,
            fg=theme.ACCENT_GOLD,
            font=("Arial", 10, "bold"),
        ).pack(pady=(0, 12))

        tk.Label(
            body,
            text="GUI + CLI service management for systemd-based Linux systems.",
            bg=theme.BG_PANEL,
            fg=theme.TEXT_SECONDARY,
            wraplength=360,
            justify="center",
        ).pack(padx=24, pady=(0, 6))

        tk.Label(
            body,
            text="Built with Python • MIT License",
            bg=theme.BG_PANEL,
            fg=theme.TEXT_SECONDARY,
        ).pack(padx=24, pady=(0, 14))

        tk.Button(
            body,
            text="GitHub Repository",
            command=self.open_github_repository,
            bg=theme.BG_SECONDARY,
            fg=theme.TEXT_PRIMARY,
            padx=18,
            pady=7,
            **theme.BUTTON,
        ).pack(fill="x", padx=24, pady=(0, 8))

        tk.Button(
            body,
            text="Close",
            command=self._close_about_window,
            bg=theme.BG_SECONDARY,
            fg=theme.TEXT_PRIMARY,
            padx=18,
            pady=7,
            **theme.BUTTON,
        ).pack(fill="x", padx=24, pady=(0, 18))

    def _close_about_window(self):
        if self.about_window is None:
            return
        try:
            self.about_window.destroy()
        except tk.TclError:
            pass
        finally:
            self.about_window = None

    def refresh_services(self):
        """Load the same deduplicated service catalog used by the CLI."""
        catalog = load_service_catalog()

        if not catalog.system_available:
            messagebox.showerror("Error", catalog.system_error)
            return

        self.services = catalog.services
        self.render_services()

        current_time = datetime.now().strftime("%H:%M:%S")
        if catalog.user_available:
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
