import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backends import systemctl_backend
from models.service_entry import ServiceEntry

try:
    from pydbus import SessionBus, SystemBus
except ImportError as error:
    SessionBus = None
    SystemBus = None
    PYDBUS_IMPORT_ERROR = error
else:
    PYDBUS_IMPORT_ERROR = None


SYSTEMD_BUS_NAME = "org.freedesktop.systemd1"
SYSTEMD_OBJECT_PATH = "/org/freedesktop/systemd1"


def get_bus(scope: str = "system"):
    if PYDBUS_IMPORT_ERROR:
        raise RuntimeError(f"pydbus not available: {PYDBUS_IMPORT_ERROR}")

    if scope == "user":
        return SessionBus()

    return SystemBus()


def get_manager(scope: str = "system"):
    bus = get_bus(scope)
    return bus.get(SYSTEMD_BUS_NAME, SYSTEMD_OBJECT_PATH)


def is_dbus_available(scope: str = "system") -> tuple[bool, str]:
    try:
        get_manager(scope)
    except Exception as error:
        return False, str(error)

    return True, "DBus available"


def list_units(scope: str = "system") -> tuple[bool, list | str]:
    try:
        manager = get_manager(scope)
        raw_units = manager.ListUnits()
    except Exception as error:
        return False, str(error)

    units = []

    for unit in raw_units:
        units.append(
            {
                "name": unit[0],
                "description": unit[1],
                "load_state": unit[2],
                "active_state": unit[3],
                "sub_state": unit[4],
                "unit_path": unit[6],
            }
        )

    return True, units


def list_services(scope: str = "system"):
    return list_units(scope)


def list_service_entries(
    scope: str = "system",
) -> tuple[bool, list[ServiceEntry] | str]:
    ok, result = list_units(scope)

    if not ok:
        return False, result

    entries = []

    for unit in result:
        unit_name = unit.get("name", "")

        if not unit_name.endswith(".service"):
            continue

        entries.append(
            ServiceEntry(
                name=unit.get("description") or unit_name,
                service=unit_name,
                scope=scope,
                status=unit.get("active_state", "unknown"),
                startup=unit.get("load_state", "unknown"),
                uptime="-",
            )
        )

    return True, entries


def get_unit_properties(
    unit_name: str, scope: str = "system"
) -> tuple[bool, dict | str]:
    try:
        manager = get_manager(scope)
        unit_path = manager.GetUnit(unit_name)
        bus = get_bus(scope)
        unit = bus.get(SYSTEMD_BUS_NAME, unit_path)
    except Exception as error:
        return False, str(error)

    properties = {}

    for key in [
        "Id",
        "Description",
        "LoadState",
        "ActiveState",
        "SubState",
        "UnitFileState",
        "FragmentPath",
        "MainPID",
    ]:
        if hasattr(unit, key):
            properties[key] = getattr(unit, key)

    return True, properties


def uses_systemctl_action_fallback() -> bool:
    return True


def get_backend_capabilities() -> dict:
    return {
        "listing": "dbus",
        "details": "dbus",
        "actions": "systemctl",
        "logs": "systemctl",
        "fallback_enabled": True,
    }


def start_service(scope: str, service: str):
    return systemctl_backend.start_service(scope, service)


def stop_service(scope: str, service: str):
    return systemctl_backend.stop_service(scope, service)


def restart_service(scope: str, service: str):
    return systemctl_backend.restart_service(scope, service)


def enable_service(scope: str, service: str):
    return systemctl_backend.enable_service(scope, service)


def disable_service(scope: str, service: str):
    return systemctl_backend.disable_service(scope, service)


def get_service_logs(scope: str, service: str, lines: int = 80):
    return systemctl_backend.get_service_logs(scope, service, lines)


if __name__ == "__main__":
    ok, result = is_dbus_available("system")
    print("DBUS:", ok, result)

    ok, units = list_units("system")
    print("LIST:", ok, len(units) if ok else units)

    ok, entries = list_service_entries("system")
    print("ENTRIES:", ok, len(entries) if ok else entries)

    print("CAPABILITIES:", get_backend_capabilities())
    print("ACTION FALLBACK:", uses_systemctl_action_fallback())
