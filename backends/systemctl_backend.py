import subprocess


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
