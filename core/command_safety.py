"""Shared command classification for diagnostic suggestions, not shell execution."""

import shlex


READ_ONLY_SYSTEMCTL_ACTIONS = {
    "cat",
    "get-default",
    "help",
    "is-active",
    "is-enabled",
    "is-failed",
    "list-dependencies",
    "list-jobs",
    "list-sockets",
    "list-timers",
    "list-unit-files",
    "list-units",
    "show",
    "show-environment",
    "status",
}
DESTRUCTIVE_PROCESS_COMMANDS = {"kill", "killall", "pkill"}
SYSTEMCTL_OPTIONS_WITH_VALUE = {
    "--host",
    "-H",
    "--lines",
    "-n",
    "--machine",
    "-M",
    "--output",
    "-o",
    "--property",
    "-p",
    "--root",
    "--state",
    "--type",
    "-t",
}


def split_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def command_name(token: str) -> str:
    """Return an executable basename without resolving or touching the filesystem."""
    return token.rsplit("/", 1)[-1]


def systemctl_action(parts: list[str]) -> str:
    """Return the first systemctl action after supported global options.

    Unknown/ambiguous option layouts deliberately return an empty action so the
    caller can fail closed instead of accidentally classifying a write command
    as read-only.
    """
    index = 1
    while index < len(parts):
        token = parts[index]

        if token == "--":
            index += 1
            break

        if token in SYSTEMCTL_OPTIONS_WITH_VALUE:
            if index + 1 >= len(parts):
                return ""
            index += 2
            continue

        if token.startswith("--") and "=" in token:
            index += 1
            continue

        if token.startswith("-"):
            index += 1
            continue

        return token

    if index < len(parts):
        return parts[index]
    return ""


def command_requires_advanced(command: str) -> bool:
    """Return True when copying the command should require Advanced Mode.

    Only known diagnostic command forms are accepted. This is a suggestion
    classifier, not a shell sandbox; executable identity and environment are
    assumed trusted. Unknown forms require Advanced Mode.
    """
    # Reject shell syntax conservatively, even inside quoted arguments.
    if any(character in command for character in ";&|<>`$\n\r"):
        return True
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return True
    if not parts:
        return False

    if command_name(parts[0]) == "sudo":
        parts = parts[1:]
        if not parts:
            return True
        # Generated commands use plain ``sudo <command>``. Rather than trying
        # to fully emulate sudo's option parser, any option-bearing wrapper is
        # conservatively classified as Advanced.
        if parts[0].startswith("-"):
            return True

    executable = command_name(parts[0])
    if executable in DESTRUCTIVE_PROCESS_COMMANDS:
        return True

    if executable == "systemctl":
        return systemctl_action(parts) not in READ_ONLY_SYSTEMCTL_ACTIONS

    args = parts[1:]
    if executable in {"ps", "pstree"}:
        option = "-fp" if executable == "ps" else "-sp"
        return not (len(args) == 2 and args[0] == option and args[1].isascii()
                    and args[1].isdigit() and int(args[1]) > 0)
    if executable == "systemd-cgls":
        return args not in ([], ["--user"])
    if executable == "sleep":
        return args != ["2"]
    if executable in {"python", "python3"}:
        # Only the project's diagnostic entry point with exactly one query.
        # As with other suggestions, run this relative path from the project root.
        return not (len(args) == 2 and args[0] == "diagnostics/process_inspector.py"
                    and bool(args[1]))
    if executable == "journalctl":
        # Accept only the generated log-reading grammar, never maintenance options.
        if args[:1] == ["--user"]:
            args = args[1:]
        if len(args) < 2 or args[0] != "-u" or not args[1] or args[1].startswith("-"):
            return True
        args = args[2:]
        if args[:1] == ["-n"]:
            if len(args) < 2 or not args[1].isascii() or not args[1].isdigit():
                return True
            args = args[2:]
        return args not in ([], ["--no-pager"])
    return True
