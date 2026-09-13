"""Shared administrator authentication helpers for CLI and GUI frontends."""

import subprocess


def verify_sudo_password(password: str) -> bool:
    """Validate sudo credentials without executing a service-management action."""
    if not password:
        return False

    try:
        result = subprocess.run(
            ["sudo", "-S", "-v"],
            input=password + "\n",
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (PermissionError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False

    return result.returncode == 0
