from backends import systemctl_backend

ACTIVE_BACKEND = "systemctl"


def get_backend():

    if ACTIVE_BACKEND == "systemctl":
        return systemctl_backend

    raise ValueError(f"Unbekanntes Backend: {ACTIVE_BACKEND}")
