import subprocess
from models.service_entry import ServiceEntry


def build_systemctl_command(scope: str, action: str, service: str) -> list[str]:
    if scope == "user":
        return ["systemctl", "--user", action, service]

    return ["sudo", "systemctl", action, service]


def run_systemctl(scope: str, action: str, service: str) -> tuple[bool, str]:
    cmd = build_systemctl_command(scope, action, service)

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True
    )

    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def start_service(scope: str, service: str) -> tuple[bool, str]:
    return run_systemctl(scope, "start", service)


def stop_service(scope: str, service: str) -> tuple[bool, str]:
    return run_systemctl(scope, "stop", service)


def restart_service(scope: str, service: str) -> tuple[bool, str]:
    return run_systemctl(scope, "restart", service)


def enable_service(scope: str, service: str) -> tuple[bool, str]:
    return run_systemctl(scope, "enable", service)


def disable_service(scope: str, service: str) -> tuple[bool, str]:
    return run_systemctl(scope, "disable", service)

def list_services(scope: str = "system"):

    if scope == "user":

        cmd = [
            "systemctl",
            "--user",
            "list-units",
            "--type=service",
            "--all",
            "--no-pager"
        ]

    else:

        cmd = [
            "systemctl",
            "list-units",
            "--type=service",
            "--all",
            "--no-pager"
        ]

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True
    )

    if result.returncode != 0:
        return False, result.stderr

    return True, result.stdout

def parse_systemctl_list(output: str, scope: str = "system") -> list[ServiceEntry]:

    services = []

    for line in output.splitlines():

        line = line.strip()

        if not line:

            continue

        if line.startswith("UNIT "):

            continue

        if line.startswith("LOAD "):

            continue

        if line.startswith("Legend:"):

            continue

        if line.startswith("To show"):

            continue

        if not ".service" in line:

            continue

        parts = line.split(None, 4)

        if len(parts) < 4:

            continue

        unit = parts[0]

        load = parts[1]

        active = parts[2]

        sub = parts[3]

        description = parts[4] if len(parts) > 4 else ""

        services.append(

            ServiceEntry(

                name=description or unit,

                service=unit,

                scope=scope,

                status=active,

                startup=load,

                uptime="-"

            )

        )

    return services

def list_service_entries(scope: str = "system") -> tuple[bool, list[ServiceEntry] | str]:

    ok, output = list_services(scope)

    if not ok:

        return False, output

    return True, parse_systemctl_list(output, scope)
