import tkinter as tk

from ui.diagnostics_window import DiagnosticsWindow
from ui.main_window import MainWindow


class ApplicationWindow(MainWindow):
    """Main application window with the read-only diagnostics workspace attached."""

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
