#app.py

from ui.main_window import MainWindow
from cli.menu import CliMenu


class LinuxServiceCenterApp:

    def __init__(self):
        self.gui = MainWindow()
        self.cli = CliMenu()

    def run_gui(self):
        self.gui.run()

    def run_cli(self):
        self.cli.run()
        
