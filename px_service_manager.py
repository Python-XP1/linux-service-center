import subprocess
import time

SERVICES = [
    "ssh.service",
    "realvnc-vnc-server.service",
    "code-server.service",
    "einkaufsliste.service",
    "budget.service",
]

# Membership sets make action validation cheap and explicit.
SERVICE_SET = set(SERVICES)
COMMAND_TIMEOUT = 10
SERVICE_ACTIONS = {"start", "stop", "restart"}

def run_cmd(cmd):
    """Run a short-lived command and capture its output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT)
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", f"Befehl nach {COMMAND_TIMEOUT}s abgebrochen."
    except Exception as e:
        return "", str(e)

def service_status(service):
    """Return the systemd active state for a known service."""
    if service not in SERVICE_SET:
        return "unknown"
    out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"

def clear():
    """Clear the terminal without invoking a shell."""
    subprocess.run(["clear"], check=False)

def show_services():
    """Render the main terminal service overview."""
    clear()
    print("╔════════════════════════════════════╗")
    print("║     PythonXP Service Manager       ║")
    print("╚════════════════════════════════════╝\n")

    for i, service in enumerate(SERVICES, start=1):
        status = service_status(service)

        if status == "active":
            icon = "🟢"
        elif status == "inactive":
            icon = "🔴"
        elif status == "failed":
            icon = "🟠"
        else:
            icon = "⚪"

        # Keep columns aligned so the overview remains readable.
        print(f"{i}. {icon} {service:<30} {status}")

    print("\nAktionen:")
    print("[s] Starten")
    print("[t] Stoppen")
    print("[r] Neustarten")
    print("[l] Logs anzeigen")
    print("[q] Beenden")

def choose_service():
    """Ask the user for a service number and return the matching unit name."""
    try:
        num = int(input("\nService-Nummer: "))
        if 1 <= num <= len(SERVICES):
            return SERVICES[num - 1]
    except ValueError:
        pass

    print("Ungültige Auswahl.")
    time.sleep(1)
    return None

def control_service(action, service):
    """Run a start/stop/restart command for an allowed service."""
    if action not in SERVICE_ACTIONS or service not in SERVICE_SET:
        print("\nUngültige Aktion oder Service.")
        time.sleep(1)
        return

    print(f"\n{action} {service} ...")
    try:
        # sudo may prompt for a password, so keep this operation bounded by a timeout.
        result = subprocess.run(
            ["sudo", "systemctl", action, service],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(result.stderr.strip() or result.stdout.strip() or "Aktion fehlgeschlagen.")
    except subprocess.TimeoutExpired:
        print("systemctl hat nach 30 Sekunden nicht geantwortet.")
    except OSError as e:
        print(e)
    input("\nEnter drücken...")

def show_logs(service):
    """Show recent journalctl lines for an allowed service."""
    if service not in SERVICE_SET:
        print("\nUngültiger Service.")
        time.sleep(1)
        return

    clear()
    print(f"Logs für {service}\n")
    try:
        subprocess.run(["journalctl", "-u", service, "-n", "40", "--no-pager"], timeout=COMMAND_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("journalctl hat zu lange gebraucht.")
    except OSError as e:
        print(e)
    input("\nEnter drücken...")

def main():
    """Run the interactive terminal menu."""
    while True:
        show_services()
        choice = input("\nAuswahl: ").lower().strip()

        if choice == "q":
            break

        if choice in ["s", "t", "r", "l"]:
            service = choose_service()
            if not service:
                continue

            if choice == "s":
                control_service("start", service)
            elif choice == "t":
                control_service("stop", service)
            elif choice == "r":
                control_service("restart", service)
            elif choice == "l":
                show_logs(service)

if __name__ == "__main__":
    main()
