# Keep existing imports available to callers while sharing one policy implementation.
from core.command_safety import (
    READ_ONLY_SYSTEMCTL_ACTIONS,
    DESTRUCTIVE_PROCESS_COMMANDS,
    SYSTEMCTL_OPTIONS_WITH_VALUE,
    split_command,
    command_name,
    systemctl_action,
    command_requires_advanced,
)
from diagnostics.process_inspector import analyze_query, group_results


def build_command_items(result: dict) -> list[dict]:
    """Build shared CLI/GUI suggestions; source_key identifies the original group."""
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
                    "source_key": key,
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
