import platform
import shutil
import subprocess


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)

    if result.returncode != 0:
        return result.stderr.strip() or "Command failed."

    return result.stdout.strip()


def get_system_diagnostics() -> str:
    lines = []

    lines.append("System")
    lines.append("------")
    lines.append(f"OS: {platform.system()} {platform.release()}")
    lines.append(f"Machine: {platform.machine()}")
    lines.append(f"Python: {platform.python_version()}")
    lines.append("")

    lines.append("CPU")
    lines.append("---")
    lines.append(run_command(["sh", "-c", "lscpu | grep 'Model name' || true"]))
    lines.append("")

    lines.append("Memory")
    lines.append("------")
    lines.append(run_command(["free", "-h"]))
    lines.append("")

    lines.append("Disk")
    lines.append("----")
    disk = shutil.disk_usage("/")
    lines.append(f"Total: {disk.total // (1024**3)} GB")
    lines.append(f"Used:  {disk.used // (1024**3)} GB")
    lines.append(f"Free:  {disk.free // (1024**3)} GB")
    lines.append("")

    lines.append("Temperature")
    lines.append("-----------")
    lines.append(
        run_command(
            [
                "sh",
                "-c",
                "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000 \" °C\"}' || echo 'Not available'",
            ]
        )
    )

    return "\n".join(lines)
