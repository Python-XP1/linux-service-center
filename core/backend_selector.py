import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backends import dbus_backend, systemctl_backend


ACTIVE_BACKEND = "dbus"


def get_backend(preferred=None):
    selected = preferred or ACTIVE_BACKEND

    if selected == "dbus":
        ok, _ = dbus_backend.is_dbus_available("system")

        if ok:
            return dbus_backend

    return systemctl_backend


def get_backend_name(preferred=None):
    selected = preferred or ACTIVE_BACKEND

    if selected == "dbus":
        ok, _ = dbus_backend.is_dbus_available("system")

        if ok:
            return "dbus"

    return "systemctl"


if __name__ == "__main__":
    backend = get_backend("dbus")

    print("Backend:", backend.__name__)

    print("Selected:", get_backend_name("dbus"))
