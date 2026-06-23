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


if __name__ == "__main__":
    ok, result = is_dbus_available("system")
    print("DBUS:", ok, result)

    ok, units = list_units("system")
    print("LIST:", ok, len(units) if ok else units)
