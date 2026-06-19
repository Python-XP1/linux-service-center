from dataclasses import dataclass


@dataclass
class ServiceEntry:
    name: str
    service: str
    scope: str = "system"
    status: str = "unknown"
    startup: str = "unknown"
    uptime: str = "-"
    url: str = ""
    folder: str = ""
    working_directory: str = ""
    venv_path: str = ""
    python_executable: str = ""
    start_command: str = ""

    @property
    def is_user_service(self) -> bool:
        return self.scope == "user"

    @property
    def is_system_service(self) -> bool:
        return self.scope == "system"
