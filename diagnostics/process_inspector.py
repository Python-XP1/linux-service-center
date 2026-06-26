from pathlib import Path
import os
import subprocess
import sys


INSPECTOR_SCRIPT = "process_inspector.py"
PROC_ROOT = Path("/proc")


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, FileNotFoundError, OSError):
        return ""


def read_link(path: Path) -> str:
    try:
        return str(path.resolve())
    except (PermissionError, FileNotFoundError, OSError):
        return ""


def parse_status(status: str) -> tuple[str, int]:
    name = ""
    ppid = 0

    for line in status.splitlines():
        if line.startswith("Name:"):
            name = line.partition(":")[2].strip()
        elif line.startswith("PPid:"):
            value = line.partition(":")[2].strip()
            try:
                ppid = int(value)
            except ValueError:
                ppid = 0

    return name, ppid


def get_process_info(pid: int) -> dict:
    proc_dir = PROC_ROOT / str(pid)

    status = read_text_file(proc_dir / "status")
    if not status:
        return {}

    name, ppid = parse_status(status)
    cmdline = read_text_file(proc_dir / "cmdline").replace("\x00", " ").strip()
    cgroup = read_text_file(proc_dir / "cgroup").strip()
    exe = read_link(proc_dir / "exe")
    cwd = read_link(proc_dir / "cwd")

    return {
        "pid": pid,
        "ppid": ppid,
        "name": name,
        "cmdline": cmdline,
        "exe": exe,
        "cwd": cwd,
        "cgroup": cgroup,
    }


def is_inspector_process(process: dict) -> bool:
    pid = process.get("pid", 0)
    cmdline = process.get("cmdline", "")

    if pid == os.getpid():
        return True

    return INSPECTOR_SCRIPT in cmdline


def list_processes() -> list[dict]:
    processes = []

    try:
        entries = list(PROC_ROOT.iterdir())
    except (PermissionError, FileNotFoundError, OSError):
        return processes

    for entry in entries:
        if not entry.name.isdigit():
            continue

        process = get_process_info(int(entry.name))
        if process and not is_inspector_process(process):
            processes.append(process)

    return processes


def find_processes_by_query(query: str) -> list[dict]:
    normalized_query = query.lower().strip()
    if not normalized_query:
        return []

    matches = []
    query_pid = int(normalized_query) if normalized_query.isdigit() else None

    for process in list_processes():
        if query_pid is not None and process.get("pid") == query_pid:
            matches.append(process)
            continue

        searchable_text = " ".join(
            [
                process.get("name", ""),
                process.get("cmdline", ""),
                process.get("exe", ""),
                process.get("cwd", ""),
                process.get("cgroup", ""),
            ]
        ).lower()

        if normalized_query in searchable_text:
            matches.append(process)

    return matches


def get_parent_chain(pid: int) -> list[dict]:
    chain = []
    current_pid = pid
    seen_pids = set()

    for _ in range(20):
        if current_pid <= 0 or current_pid in seen_pids:
            break

        seen_pids.add(current_pid)
        process = get_process_info(current_pid)
        if not process:
            break

        chain.append(process)
        parent_pid = process.get("ppid", 0)

        if parent_pid in (0, 1):
            break

        current_pid = parent_pid

    return chain


def detect_process_owner(process: dict) -> str:
    cgroup = process.get("cgroup", "")
    cmdline = process.get("cmdline", "")
    ppid = process.get("ppid", 0)

    if "system.slice" in cgroup:
        return "systemd system service"

    if "user.slice" in cgroup:
        return "systemd user session/service"

    if "app.py" in cmdline:
        return "application-managed process"

    if ppid > 1:
        return "child process"

    return "unknown"


def extract_unit_from_cgroup(cgroup: str) -> str:
    for segment in reversed(cgroup.split("/")):
        if segment.endswith(".service"):
            return segment

    return ""


def extract_slice_from_cgroup(cgroup: str) -> str:
    for segment in reversed(cgroup.split("/")):
        if segment.endswith(".slice"):
            return segment

    return ""


def detect_manager(process: dict) -> dict:
    cgroup = process.get("cgroup", "")
    cmdline = process.get("cmdline", "")
    ppid = process.get("ppid", 0)
    unit = extract_unit_from_cgroup(cgroup)
    slice_name = extract_slice_from_cgroup(cgroup)

    if "system.slice" in cgroup:
        return {
            "type": "systemd-system",
            "unit": unit,
            "slice": slice_name,
            "description": "Managed by systemd as a system service.",
        }

    if "user.slice" in cgroup and unit:
        return {
            "type": "systemd-user",
            "unit": unit,
            "slice": slice_name,
            "description": "Managed by systemd as a user service.",
        }

    if "user.slice" in cgroup:
        return {
            "type": "user-session",
            "unit": unit,
            "slice": slice_name,
            "description": "Running inside a user session.",
        }

    if "app.py" in cmdline:
        return {
            "type": "application-managed",
            "unit": unit,
            "slice": slice_name,
            "description": "Likely managed by an application or custom launcher.",
        }

    if ppid > 1:
        return {
            "type": "child-process",
            "unit": unit,
            "slice": slice_name,
            "description": "Child process of another process.",
        }

    return {
        "type": "unknown",
        "unit": unit,
        "slice": slice_name,
        "description": "No clear process manager detected.",
    }


def verify_systemd_unit(manager: dict) -> dict:
    manager = manager.copy()
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")

    if manager_type not in {"systemd-system", "systemd-user"}:
        manager.setdefault("unit_exists", None)
        manager.setdefault("health", "unknown")
        manager.setdefault("warning", "")
        return manager

    if manager_type == "systemd-user":
        command = ["systemctl", "--user", "status", unit]
    else:
        command = ["systemctl", "status", unit]

    try:
        result = subprocess.run(command, text=True, capture_output=True)
    except (PermissionError, FileNotFoundError, OSError):
        result = None

    if result is not None and result.returncode == 0:
        manager["unit_exists"] = True
        manager["health"] = "healthy"
        manager["warning"] = ""
        return manager

    manager["unit_exists"] = False
    manager["health"] = "orphaned"
    manager[
        "warning"
    ] = "Process belongs to a service cgroup but the systemd unit no longer exists."
    return manager


def choose_respawn_search_term(process: dict) -> str:
    cmdline = process.get("cmdline", "")
    pid = process.get("pid", 0)

    if "/home/pi/Einkaufsliste/app.py" in cmdline:
        return "/home/pi/Einkaufsliste/app.py"

    if cmdline:
        return cmdline.split()[0]

    return str(pid)


def build_respawn_test_commands(process: dict) -> list[str]:
    pid = process.get("pid", 0)
    search_term = choose_respawn_search_term(process)

    return [
        f"kill {pid}",
        "sleep 2",
        f'python diagnostics/process_inspector.py "{search_term}"',
    ]


def build_slice_recovery_commands(manager: dict) -> list[str]:
    slice_name = manager.get("slice", "")
    manager_type = manager.get("type", "")

    if not slice_name:
        return []

    if manager_type == "systemd-user":
        return [
            f"systemctl --user status {slice_name}",
            f"systemctl --user stop {slice_name}",
        ]

    if manager_type == "systemd-system":
        return [
            f"systemctl status {slice_name}",
            f"sudo systemctl stop {slice_name}",
        ]

    return []


def detect_restart_policy(manager: dict) -> str:
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")

    if not unit:
        return "unknown"

    if manager_type == "systemd-system":
        command = ["systemctl", "show", unit, "-p", "Restart", "--value"]
    elif manager_type == "systemd-user":
        command = [
            "systemctl",
            "--user",
            "show",
            unit,
            "-p",
            "Restart",
            "--value",
        ]
    else:
        return "unknown"

    try:
        result = subprocess.run(command, text=True, capture_output=True)
    except (PermissionError, FileNotFoundError, OSError):
        return "unknown"

    if result.returncode != 0:
        return "unknown"

    value = result.stdout.strip()
    if not value:
        return "unknown"

    return value


def build_suggested_commands(process: dict, manager: dict) -> list[str]:
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")
    pid = process.get("pid", 0)
    ppid = process.get("ppid", 0)

    if manager_type == "systemd-system" and unit:
        commands = [
            f"sudo systemctl status {unit}",
            f"sudo systemctl stop {unit}",
            f"sudo systemctl disable {unit}",
            f"sudo journalctl -u {unit} -n 80 --no-pager",
        ]

        if manager.get("health") == "orphaned":
            commands.extend(
                [
                    "systemctl list-units --all",
                    "systemctl list-unit-files",
                    "systemd-cgls",
                ]
            )

        return commands

    if manager_type == "systemd-user" and unit:
        commands = [
            f"systemctl --user status {unit}",
            f"systemctl --user stop {unit}",
            f"systemctl --user disable {unit}",
            f"journalctl --user -u {unit} -n 80 --no-pager",
        ]

        if manager.get("health") == "orphaned":
            commands.extend(
                [
                    "systemctl --user list-units --all",
                    "systemctl --user list-unit-files",
                    "systemd-cgls --user",
                ]
            )

        return commands

    if manager_type == "user-session":
        return [
            f"ps -fp {pid}",
            f"pstree -sp {pid}",
        ]

    if manager_type == "application-managed":
        commands = [
            f"ps -fp {pid}",
            f"pstree -sp {pid}",
        ]

        if ppid > 1:
            commands.append(f"ps -fp {ppid}")

        return commands

    if manager_type == "child-process":
        commands = [
            f"ps -fp {pid}",
        ]

        if ppid > 1:
            commands.append(f"ps -fp {ppid}")

        commands.append(f"pstree -sp {pid}")
        return commands

    return [
        f"ps -fp {pid}",
        f"pstree -sp {pid}",
    ]


def build_recovery_advice(process: dict, manager: dict) -> dict:
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")
    slice_name = manager.get("slice", "")
    health = manager.get("health", "unknown")
    restart_policy = manager.get("restart_policy", "unknown")

    if health == "orphaned":
        details = [
            f"Unit from cgroup: {unit}",
            "The process may be attached to a stale cgroup or transient unit.",
        ]
        recommended_order = [
            "List loaded units and unit files.",
            "Inspect the cgroup tree.",
        ]

        if slice_name:
            details.append(f"Surrounding slice: {slice_name}")
            recommended_order.append("Try stopping the surrounding slice.")

        recommended_order.append("Restart the user manager only as a last resort.")

        return {
            "summary": "Process belongs to a service cgroup, but the unit is not loaded.",
            "details": details,
            "recommended_order": recommended_order,
        }

    if manager_type in {"systemd-user", "systemd-system"} and restart_policy in {
        "always",
        "on-failure",
        "on-abnormal",
        "on-watchdog",
        "on-success",
    }:
        recommended_order = [
            "Stop the service unit first.",
            "Disable the service unit if it should not start again.",
            "Run the respawn test again.",
        ]

        if slice_name:
            recommended_order.append(
                "If the unit cannot be stopped, inspect or stop the surrounding slice."
            )

        recommended_order.append("Inspect logs if the process still comes back.")

        return {
            "summary": "Process is managed by systemd and may restart automatically.",
            "details": [
                f"Unit: {unit}",
                f"Restart policy: {restart_policy}",
                "Killing only the PID is usually not enough.",
            ],
            "recommended_order": recommended_order,
        }

    if manager_type == "application-managed":
        return {
            "summary": "Process may be managed by an application or launcher script.",
            "details": [
                "Look at the parent process and command line.",
                "The application may restart child processes itself.",
            ],
            "recommended_order": [
                "Inspect the parent process.",
                "Stop the parent process or launcher.",
                "Run the respawn test again.",
            ],
        }

    return {
        "summary": "No specific recovery advice available.",
        "details": [
            "Use process information and parent chain for manual analysis.",
        ],
        "recommended_order": [
            "Inspect the process.",
            "Inspect the parent chain.",
        ],
    }


def build_group_key(process: dict, manager: dict) -> str:
    if manager.get("unit"):
        return f"{manager.get('type', '')}:{manager.get('unit', '')}"

    if manager.get("slice"):
        return f"{manager.get('type', '')}:{manager.get('slice', '')}"

    return f"pid:{process.get('pid', 0)}"


def build_confidence_score(
    process: dict, manager: dict, parent_chain: list[dict]
) -> dict:
    score = 0
    signals = []
    warnings = []

    if manager.get("unit"):
        score += 30
        signals.append("Systemd unit was detected from cgroup.")

    if manager.get("type") != "unknown":
        score += 20
        signals.append(f"Manager type detected: {manager.get('type', '')}.")

    if manager.get("slice"):
        score += 15
        signals.append("Systemd slice was detected from cgroup.")

    if manager.get("restart_policy") != "unknown":
        score += 15
        signals.append(f"Restart policy detected: {manager.get('restart_policy', '')}.")

    if parent_chain:
        score += 10
        signals.append("Parent chain was resolved.")

    if manager.get("health") == "healthy":
        score += 10
        signals.append("Systemd unit appears healthy.")

    if manager.get("health") == "orphaned":
        warnings.append("Unit from cgroup is not loaded.")

    if manager.get("type") == "unknown":
        warnings.append("No clear process manager detected.")

    if not parent_chain:
        warnings.append("Parent chain could not be resolved.")

    return {
        "score": min(score, 100),
        "signals": signals,
        "warnings": warnings,
    }


def analyze_query(query: str) -> list[dict]:
    results = []

    for process in find_processes_by_query(query):
        manager = detect_manager(process)
        manager = verify_systemd_unit(manager)
        manager["restart_policy"] = detect_restart_policy(manager)
        parent_chain = get_parent_chain(process.get("pid", 0))
        results.append(
            {
                "process": process,
                "owner_hint": detect_process_owner(process),
                "manager": manager,
                "group_key": build_group_key(process, manager),
                "confidence": build_confidence_score(process, manager, parent_chain),
                "suggested_commands": build_suggested_commands(process, manager),
                "respawn_test_commands": build_respawn_test_commands(process),
                "slice_recovery_commands": build_slice_recovery_commands(manager),
                "recovery_advice": build_recovery_advice(process, manager),
                "parent_chain": parent_chain,
            }
        )

    return results


def group_results(results: list[dict]) -> list[dict]:
    groups = []
    grouped_by_key = {}

    for result in results:
        group_key = result.get("group_key", "")
        process = result.get("process", {})

        if group_key not in grouped_by_key:
            group = {
                "group_key": group_key,
                "primary": result,
                "process_count": 0,
                "pids": [],
                "processes": [],
            }
            grouped_by_key[group_key] = group
            groups.append(group)

        group = grouped_by_key[group_key]
        group["process_count"] += 1
        group["pids"].append(process.get("pid", 0))
        group["processes"].append(process)

    return groups


def print_process_result(result: dict):
    process = result["process"]

    print("Process:")
    print(f"  PID: {process.get('pid', '')}")
    print(f"  PPID: {process.get('ppid', '')}")
    print(f"  Name: {process.get('name', '')}")
    print(f"  Command: {process.get('cmdline', '')}")
    print(f"  Exe: {process.get('exe', '')}")
    print(f"  CWD: {process.get('cwd', '')}")
    print(f"  CGroup: {process.get('cgroup', '')}")
    print(f"  Owner hint: {result.get('owner_hint', '')}")
    print()

    manager = result.get("manager", {})
    print("Detected manager:")
    print(f"  Type: {manager.get('type', '')}")
    print(f"  Unit: {manager.get('unit', '')}")
    if manager.get("slice"):
        print(f"  Slice: {manager.get('slice', '')}")
    print(f"  Description: {manager.get('description', '')}")
    print(f"  Health: {manager.get('health', 'unknown').title()}")
    print(f"  Restart policy: {manager.get('restart_policy', 'unknown')}")
    if manager.get("restart_policy") in {
        "always",
        "on-failure",
        "on-abnormal",
        "on-watchdog",
        "on-success",
    }:
        print(
            "  Respawn risk: This process may restart automatically due to its "
            "systemd restart policy."
        )
    if manager.get("warning"):
        print(f"  Warning: {manager.get('warning')}")
    print()

    confidence = result.get("confidence", {})
    if confidence:
        print("Confidence:")
        print(f"  Score: {confidence.get('score', 0)}/100")
        print("  Signals:")
        signals = confidence.get("signals", [])
        if signals:
            for signal in signals:
                print(f"    - {signal}")
        else:
            print("    - None")
        print("  Warnings:")
        warnings = confidence.get("warnings", [])
        if warnings:
            for warning in warnings:
                print(f"    - {warning}")
        else:
            print("    - None")
        print()

    suggested_commands = result.get("suggested_commands", [])
    print("Suggested commands:")
    if suggested_commands:
        for command in suggested_commands:
            print(f"  {command}")
    else:
        print("  No suggestions available.")
    print()

    respawn_test_commands = result.get("respawn_test_commands", [])
    print("Respawn test:")
    print(
        "  These commands can be run manually to check whether the process comes back:"
    )
    for command in respawn_test_commands:
        print(f"  {command}")
    print()

    slice_recovery_commands = result.get("slice_recovery_commands", [])
    if slice_recovery_commands:
        print("Slice recovery:")
        print(
            "  If stopping the unit does not work, the surrounding slice may still "
            "hold the process."
        )
        print("  These commands can be run manually:")
        for command in slice_recovery_commands:
            print(f"  {command}")
        print()

    recovery_advice = result.get("recovery_advice", {})
    if recovery_advice:
        print("Recovery advisor:")
        print(f"  Summary: {recovery_advice.get('summary', '')}")
        print()
        print("  Details:")
        for detail in recovery_advice.get("details", []):
            print(f"    - {detail}")
        print()
        print("  Recommended order:")
        for index, item in enumerate(recovery_advice.get("recommended_order", []), 1):
            print(f"    {index}. {item}")
        print()

    print("Parent chain:")

    for parent in result.get("parent_chain", []):
        print(
            "  "
            f"{parent.get('pid', '')} -> "
            f"{parent.get('name', '')} -> "
            f"{parent.get('cmdline', '')}"
        )

    print()


def print_group_result(group: dict):
    print("Process group:")
    print(f"  Key: {group.get('group_key', '')}")
    print(f"  Process count: {group.get('process_count', 0)}")
    pids = ", ".join(str(pid) for pid in group.get("pids", []))
    print(f"  PIDs: {pids}")
    print()

    print_process_result(group["primary"])

    if group.get("process_count", 0) > 1:
        print("Related processes:")
        for process in group.get("processes", []):
            print(
                "  "
                f"{process.get('pid', '')} -> "
                f"{process.get('name', '')} -> "
                f"{process.get('cmdline', '')}"
            )
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnostics/process_inspector.py <query>")
        return

    query = sys.argv[1]
    results = analyze_query(query)

    if not results:
        print("No matching processes found.")
        return

    groups = group_results(results)

    for group in groups:
        print_group_result(group)


if __name__ == "__main__":
    main()
