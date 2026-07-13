import shlex

from diagnostics.process_inspector import analyze_query, group_results


DESTRUCTIVE_SYSTEMCTL_ACTIONS = {
    "disable",
    "enable",
    "kill",
    "mask",
    "reenable",
    "reload-or-restart",
    "restart",
    "start",
    "stop",
    "try-restart",
    "unmask",
}
DESTRUCTIVE_PROCESS_COMMANDS = {"kill", "killall", "pkill"}


def split_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def command_requires_advanced(command: str) -> bool:
    """Return True when copying the command should require Advanced Mode."""
    parts = split_command(command.strip())
    if not parts:
        return False

    if parts[0] == "sudo":
        parts = parts[1:]
    if not parts:
        return False

    executable = parts[0]
    if executable in DESTRUCTIVE_PROCESS_COMMANDS:
        return True

    if executable != "systemctl":
        return False

    for token in parts[1:]:
        if token.startswith("-"):
            continue
        return token in DESTRUCTIVE_SYSTEMCTL_ACTIONS

    return False


def build_command_items(result: dict) -> list[dict]:
    command_groups = (
        ("suggested", "Suggested command", "suggested_commands"),
        ("respawn-test", "Respawn test", "respawn_test_commands"),
        ("slice-recovery", "Slice recovery", "slice_recovery_commands"),
    )
    items = []

    for category, label, key in command_groups:
        for command in result.get(key, []):
            items.append(
                {
                    "command": command,
                    "category": category,
                    "label": label,
                    "requires_advanced": command_requires_advanced(command),
                }
            )

    return items


def analyze_grouped_query(query: str) -> list[dict]:
    """Run the existing inspector and enrich its grouped structured results for the GUI."""
    groups = group_results(analyze_query(query))

    for group in groups:
        primary = group.get("primary", {})
        primary["command_items"] = build_command_items(primary)

    return groups
