import platform
import shutil
import subprocess


SEPARATOR = "------------------------"
LABEL_WIDTH = 12


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)

    if result.returncode != 0:
        return result.stderr.strip() or "Command failed."

    return result.stdout.strip()


def add_section(lines: list[str], title: str) -> None:
    if lines:
        lines.append("")

    lines.append(title)
    lines.append(SEPARATOR)


def add_value(lines: list[str], label: str, value: str) -> None:
    lines.append(f"{label + ':':<{LABEL_WIDTH}}{value}")


def parse_cpu_model(cpu_output: str) -> str:
    if not cpu_output:
        return "Not available"

    if ":" in cpu_output:
        return cpu_output.split(":", 1)[1].strip()

    return cpu_output.strip()


def parse_memory(memory_output: str) -> dict[str, str]:
    memory = {
        "total": "Not available",
        "used": "Not available",
        "free": "Not available",
        "available": "Not available",
    }

    for line in memory_output.splitlines():
        line = line.strip()

        if ":" not in line or line.lower().startswith("swap:"):
            continue

        parts = line.split()
        if len(parts) >= 7:
            memory["total"] = parts[1]
            memory["used"] = parts[2]
            memory["free"] = parts[3]
            memory["available"] = parts[6]
        break

    return memory


def get_system_diagnostics() -> str:
    lines = []

    add_section(lines, "🖥️ System")
    add_value(lines, "OS", f"{platform.system()} {platform.release()}")
    add_value(lines, "Machine", platform.machine())
    add_value(lines, "Python", platform.python_version())

    add_section(lines, "⚙️ CPU")
    cpu_model = parse_cpu_model(
        run_command(["sh", "-c", "lscpu | grep 'Model name' || true"])
    )
    add_value(lines, "Model", cpu_model)

    add_section(lines, "🧠 Memory")
    memory = parse_memory(run_command(["free", "-h"]))
    add_value(lines, "Total", memory["total"])
    add_value(lines, "Used", memory["used"])
    add_value(lines, "Free", memory["free"])
    add_value(lines, "Available", memory["available"])

    add_section(lines, "💾 Disk")
    disk = shutil.disk_usage("/")
    add_value(lines, "Total", f"{disk.total // (1024**3)} GB")
    add_value(lines, "Used", f"{disk.used // (1024**3)} GB")
    add_value(lines, "Free", f"{disk.free // (1024**3)} GB")

    add_section(lines, "🌡️ Temperature")
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
