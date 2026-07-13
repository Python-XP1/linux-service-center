from pathlib import Path
import os
import shlex
import subprocess
import sys


INSPECTOR_SCRIPT = "process_inspector.py"
PROC_ROOT = Path("/proc")
RESPAWN_POLICIES = {
    "always",
    "on-failure",
    "on-abnormal",
    "on-watchdog",
    "on-success",
}
GENERIC_SLICES = {"-.slice", "system.slice", "user.slice", "machine.slice"}


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
            try:
                ppid = int(line.partition(":")[2].strip())
            except ValueError:
                ppid = 0
    return name, ppid


def get_process_info(pid: int) -> dict:
    proc_dir = PROC_ROOT / str(pid)
    status = read_text_file(proc_dir / "status")
    if not status:
        return {}

    name, ppid = parse_status(status)
    return {
        "pid": pid,
        "ppid": ppid,
        "name": name,
        "cmdline": read_text_file(proc_dir / "cmdline").replace("\x00", " ").strip(),
        "exe": read_link(proc_dir / "exe"),
        "cwd": read_link(proc_dir / "cwd"),
        "cgroup": read_text_file(proc_dir / "cgroup").strip(),
    }


def is_inspector_process(process: dict) -> bool:
    return process.get("pid") == os.getpid() or INSPECTOR_SCRIPT in process.get(
        "cmdline", ""
    )


def list_processes() -> list[dict]:
    try:
        entries = list(PROC_ROOT.iterdir())
    except (PermissionError, FileNotFoundError, OSError):
        return []

    processes = []
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

    query_pid = int(normalized_query) if normalized_query.isdigit() else None
    matches = []
    for process in list_processes():
        if query_pid is not None and process.get("pid") == query_pid:
            matches.append(process)
            continue

        searchable = " ".join(
            str(process.get(key, ""))
            for key in ("name", "cmdline", "exe", "cwd", "cgroup")
        ).lower()
        if normalized_query in searchable:
            matches.append(process)
    return matches


def get_parent_chain(pid: int) -> list[dict]:
    chain = []
    current_pid = pid
    seen = set()

    for _ in range(20):
        if current_pid <= 0 or current_pid in seen:
            break
        seen.add(current_pid)
        process = get_process_info(current_pid)
        if not process:
            break
        chain.append(process)
        parent_pid = process.get("ppid", 0)
        if parent_pid in (0, 1):
            break
        current_pid = parent_pid
    return chain


def extract_cgroup_item(cgroup: str, suffix: str) -> str:
    for segment in reversed(cgroup.split("/")):
        if segment.endswith(suffix):
            return segment
    return ""


def detect_manager(process: dict) -> dict:
    cgroup = process.get("cgroup", "")
    cmdline = process.get("cmdline", "")
    ppid = process.get("ppid", 0)
    unit = extract_cgroup_item(cgroup, ".service")
    slice_name = extract_cgroup_item(cgroup, ".slice")

    if "system.slice" in cgroup:
        manager_type = "systemd-system"
        description = "Managed by systemd as a system service."
    elif "user.slice" in cgroup and unit:
        manager_type = "systemd-user"
        description = "Managed by systemd as a user service."
    elif "user.slice" in cgroup:
        manager_type = "user-session"
        description = "Running inside a user session."
    elif "app.py" in cmdline:
        manager_type = "application-managed"
        description = "Likely managed by an application or custom launcher."
    elif ppid > 1:
        manager_type = "child-process"
        description = "Child process of another process."
    else:
        manager_type = "unknown"
        description = "No clear process manager detected."

    return {
        "type": manager_type,
        "unit": unit,
        "slice": slice_name,
        "description": description,
    }


def detect_process_owner(manager: dict) -> str:
    labels = {
        "systemd-system": "systemd system service",
        "systemd-user": "systemd user service",
        "user-session": "systemd user session",
        "application-managed": "application-managed process",
        "child-process": "child process",
    }
    return labels.get(manager.get("type", ""), "unknown")


def run_command(command: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(command, text=True, capture_output=True, timeout=10)
    except (PermissionError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def systemctl_base(manager_type: str) -> list[str]:
    if manager_type == "systemd-user":
        return ["systemctl", "--user"]
    return ["systemctl"]


def verify_systemd_unit(manager: dict) -> dict:
    manager = manager.copy()
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")

    if manager_type not in {"systemd-system", "systemd-user"} or not unit:
        manager.update(unit_exists=None, health="unknown", warning="")
        return manager

    command = systemctl_base(manager_type) + [
        "show",
        unit,
        "--property=LoadState",
        "--value",
    ]
    result = run_command(command)
    load_state = result.stdout.strip() if result is not None else ""
    exists = bool(
        result is not None
        and result.returncode == 0
        and load_state
        and load_state != "not-found"
    )

    manager["unit_exists"] = exists
    manager["health"] = "healthy" if exists else "orphaned"
    manager["warning"] = (
        ""
        if exists
        else "Process belongs to a service cgroup but the systemd unit is not loaded."
    )
    return manager


def detect_restart_policy(manager: dict) -> str:
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")
    if manager_type not in {"systemd-system", "systemd-user"} or not unit:
        return "unknown"

    command = systemctl_base(manager_type) + [
        "show",
        unit,
        "--property=Restart",
        "--value",
    ]
    result = run_command(command)
    if result is None or result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def split_cmdline(cmdline: str) -> list[str]:
    if not cmdline:
        return []
    try:
        return shlex.split(cmdline)
    except ValueError:
        return cmdline.split()


def choose_respawn_search_term(process: dict) -> str:
    """Choose an environment-neutral term that identifies the launched program."""
    parts = split_cmdline(process.get("cmdline", ""))
    cwd = process.get("cwd", "")

    if parts:
        executable_name = Path(parts[0]).name.lower()
        arguments = parts[1:]

        if executable_name.startswith("python"):
            for argument in arguments:
                if argument.startswith("-"):
                    continue
                candidate = Path(argument)
                if not candidate.is_absolute() and cwd:
                    candidate = Path(cwd) / candidate
                return str(candidate)

        for argument in arguments:
            if argument.startswith("/"):
                return argument

    return process.get("exe", "") or (parts[0] if parts else str(process.get("pid", 0)))


def build_respawn_test_commands(process: dict) -> list[str]:
    pid = process.get("pid", 0)
    search_term = choose_respawn_search_term(process)
    return [
        f"kill {pid}",
        "sleep 2",
        f'python diagnostics/process_inspector.py "{search_term}"',
    ]


def is_safe_slice_target(slice_name: str) -> bool:
    if not slice_name or slice_name in GENERIC_SLICES:
        return False
    if slice_name.startswith("user-") and slice_name.endswith(".slice"):
        return False
    return True


def build_slice_recovery_commands(manager: dict) -> list[str]:
    slice_name = manager.get("slice", "")
    manager_type = manager.get("type", "")
    if not is_safe_slice_target(slice_name):
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


def build_suggested_commands(process: dict, manager: dict) -> list[str]:
    manager_type = manager.get("type", "")
    unit = manager.get("unit", "")
    pid = process.get("pid", 0)
    ppid = process.get("ppid", 0)

    if manager_type in {"systemd-system", "systemd-user"} and unit:
        prefix = "systemctl --user" if manager_type == "systemd-user" else "sudo systemctl"
        journal = "journalctl --user" if manager_type == "systemd-user" else "sudo journalctl"
        commands = [
            f"{prefix} status {unit}",
            f"{prefix} stop {unit}",
            f"{prefix} disable {unit}",
            f"{journal} -u {unit} -n 80 --no-pager",
        ]
        if manager.get("health") == "orphaned":
            base = "systemctl --user" if manager_type == "systemd-user" else "systemctl"
            cgls = "systemd-cgls --user" if manager_type == "systemd-user" else "systemd-cgls"
            commands.extend(
                [f"{base} list-units --all", f"{base} list-unit-files", cgls]
            )
        return commands

    commands = [f"ps -fp {pid}", f"pstree -sp {pid}"]
    if manager_type in {"application-managed", "child-process"} and ppid > 1:
        commands.insert(1, f"ps -fp {ppid}")
    return commands


def build_recovery_advice(manager: dict) -> dict:
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
        order = ["List loaded units and unit files.", "Inspect the cgroup tree."]
        if is_safe_slice_target(slice_name):
            details.append(f"Surrounding slice: {slice_name}")
            order.append("Try stopping the surrounding slice.")
        order.append("Restart the user manager only as a last resort.")
        return {
            "summary": "Process belongs to a service cgroup, but the unit is not loaded.",
            "details": details,
            "recommended_order": order,
        }

    if manager_type in {"systemd-user", "systemd-system"} and restart_policy in RESPAWN_POLICIES:
        order = [
            "Stop the service unit first.",
            "Disable the service unit if it should not start again.",
            "Run the respawn test again.",
        ]
        if is_safe_slice_target(slice_name):
            order.append("If the unit cannot be stopped, inspect or stop its custom slice.")
        order.append("Inspect logs if the process still comes back.")
        return {
            "summary": "Process is managed by systemd and may restart automatically.",
            "details": [
                f"Unit: {unit}",
                f"Restart policy: {restart_policy}",
                "Killing only the PID is usually not enough.",
            ],
            "recommended_order": order,
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
        "details": ["Use process information and parent chain for manual analysis."],
        "recommended_order": ["Inspect the process.", "Inspect the parent chain."],
    }


def build_group_key(process: dict, manager: dict) -> str:
    if manager.get("unit"):
        return f"{manager.get('type', '')}:{manager.get('unit', '')}"
    if manager.get("slice"):
        return f"{manager.get('type', '')}:{manager.get('slice', '')}"
    return f"pid:{process.get('pid', 0)}"


def build_confidence_score(manager: dict, parent_chain: list[dict]) -> dict:
    score = 0
    signals = []
    warnings = []

    checks = [
        (bool(manager.get("unit")), 30, "Systemd unit was detected from cgroup."),
        (manager.get("type") != "unknown", 20, f"Manager type detected: {manager.get('type', '')}."),
        (bool(manager.get("slice")), 15, "Systemd slice was detected from cgroup."),
        (manager.get("restart_policy") != "unknown", 15, f"Restart policy detected: {manager.get('restart_policy', '')}."),
        (bool(parent_chain), 10, "Parent chain was resolved."),
        (manager.get("health") == "healthy", 10, "Systemd unit appears healthy."),
    ]
    for condition, points, signal in checks:
        if condition:
            score += points
            signals.append(signal)

    if manager.get("health") == "orphaned":
        warnings.append("Unit from cgroup is not loaded.")
    if manager.get("type") == "unknown":
        warnings.append("No clear process manager detected.")
    if not parent_chain:
        warnings.append("Parent chain could not be resolved.")

    return {"score": min(score, 100), "signals": signals, "warnings": warnings}


def analyze_query(query: str) -> list[dict]:
    results = []
    for process in find_processes_by_query(query):
        manager = verify_systemd_unit(detect_manager(process))
        manager["restart_policy"] = detect_restart_policy(manager)
        parent_chain = get_parent_chain(process.get("pid", 0))
        results.append(
            {
                "process": process,
                "owner_hint": detect_process_owner(manager),
                "manager": manager,
                "group_key": build_group_key(process, manager),
                "confidence": build_confidence_score(manager, parent_chain),
                "suggested_commands": build_suggested_commands(process, manager),
                "respawn_test_commands": build_respawn_test_commands(process),
                "slice_recovery_commands": build_slice_recovery_commands(manager),
                "recovery_advice": build_recovery_advice(manager),
                "parent_chain": parent_chain,
            }
        )
    return results


def group_results(results: list[dict]) -> list[dict]:
    groups = []
    by_key = {}
    for result in results:
        key = result.get("group_key", "")
        if key not in by_key:
            group = {
                "group_key": key,
                "primary": result,
                "process_count": 0,
                "pids": [],
                "processes": [],
            }
            by_key[key] = group
            groups.append(group)
        group = by_key[key]
        process = result.get("process", {})
        group["process_count"] += 1
        group["pids"].append(process.get("pid", 0))
        group["processes"].append(process)
    return groups


def print_list(title: str, values: list[str], prefix: str = "    - ") -> None:
    print(title)
    if values:
        for value in values:
            print(f"{prefix}{value}")
    else:
        print(f"{prefix}None")


def print_process_result(result: dict) -> None:
    process = result["process"]
    manager = result.get("manager", {})

    print("Process:")
    for label, key in (
        ("PID", "pid"),
        ("PPID", "ppid"),
        ("Name", "name"),
        ("Command", "cmdline"),
        ("Exe", "exe"),
        ("CWD", "cwd"),
        ("CGroup", "cgroup"),
    ):
        print(f"  {label}: {process.get(key, '')}")
    print(f"  Owner hint: {result.get('owner_hint', '')}")
    print()

    print("Detected manager:")
    print(f"  Type: {manager.get('type', '')}")
    print(f"  Unit: {manager.get('unit', '')}")
    if manager.get("slice"):
        print(f"  Slice: {manager.get('slice', '')}")
    print(f"  Description: {manager.get('description', '')}")
    print(f"  Health: {manager.get('health', 'unknown').title()}")
    print(f"  Restart policy: {manager.get('restart_policy', 'unknown')}")
    if manager.get("restart_policy") in RESPAWN_POLICIES:
        print("  Respawn risk: This process may restart automatically due to its systemd restart policy.")
    if manager.get("warning"):
        print(f"  Warning: {manager.get('warning')}")
    print()

    confidence = result.get("confidence", {})
    print("Confidence:")
    print(f"  Score: {confidence.get('score', 0)}/100")
    print_list("  Signals:", confidence.get("signals", []))
    print_list("  Warnings:", confidence.get("warnings", []))
    print()

    print_list("Suggested commands:", result.get("suggested_commands", []), "  ")
    print()

    print("Respawn test:")
    print("  These commands can be run manually to check whether the process comes back:")
    for command in result.get("respawn_test_commands", []):
        print(f"  {command}")
    print()

    slice_commands = result.get("slice_recovery_commands", [])
    if slice_commands:
        print("Slice recovery:")
        print("  If stopping the unit does not work, its custom slice may still hold the process.")
        print("  These commands can be run manually:")
        for command in slice_commands:
            print(f"  {command}")
        print()

    advice = result.get("recovery_advice", {})
    if advice:
        print("Recovery advisor:")
        print(f"  Summary: {advice.get('summary', '')}")
        print()
        print_list("  Details:", advice.get("details", []))
        print()
        print("  Recommended order:")
        for index, item in enumerate(advice.get("recommended_order", []), 1):
            print(f"    {index}. {item}")
        print()

    print("Parent chain:")
    for parent in result.get("parent_chain", []):
        print(
            f"  {parent.get('pid', '')} -> {parent.get('name', '')} -> "
            f"{parent.get('cmdline', '')}"
        )
    print()


def print_group_result(group: dict) -> None:
    print("=" * 72)
    print("Process group:")
    print(f"  Key: {group.get('group_key', '')}")
    print(f"  Process count: {group.get('process_count', 0)}")
    print("  PIDs: " + ", ".join(str(pid) for pid in group.get("pids", [])))
    print()
    print_process_result(group["primary"])

    if group.get("process_count", 0) > 1:
        print("Related processes:")
        for process in group.get("processes", []):
            print(
                f"  {process.get('pid', '')} -> {process.get('name', '')} -> "
                f"{process.get('cmdline', '')}"
            )
        print()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python diagnostics/process_inspector.py <query>")
        return

    results = analyze_query(sys.argv[1])
    if not results:
        print("No matching processes found.")
        return

    for group in group_results(results):
        print_group_result(group)


if __name__ == "__main__":
    main()
