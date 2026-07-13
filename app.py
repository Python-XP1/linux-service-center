# app.py

from cli.menu import CliMenu
from ui.application_window import ApplicationWindow


class LinuxServiceCenterApp:
    def __init__(self):
        self.gui = ApplicationWindow()
        self.cli = CliMenu()

    def run_gui(self):
        self.gui.run()

    def run_cli(self):
        self.cli.run()
