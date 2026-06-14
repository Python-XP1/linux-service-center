import subprocess
import os
import time

SERVICES = [
    "ssh.service",
    "realvnc-vnc-server.service",
    "code-server.service",
    "einkaufsliste.service",
    "budget.service",
]

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

def service_status(service):
    out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"

def clear():
    os.system("clear")

def show_services():
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

        print(f"{i}. {icon} {service:<30} {status}")

    print("\nAktionen:")
    print("[s] Starten")
    print("[t] Stoppen")
    print("[r] Neustarten")
    print("[l] Logs anzeigen")
    print("[q] Beenden")

def choose_service():
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
    print(f"\n{action} {service} ...")
    subprocess.run(["sudo", "systemctl", action, service])
    input("\nEnter drücken...")

def show_logs(service):
    clear()
    print(f"Logs für {service}\n")
    subprocess.run(["journalctl", "-u", service, "-n", "40", "--no-pager"])
    input("\nEnter drücken...")

def main():
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