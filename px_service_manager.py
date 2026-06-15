#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "services.json")
COMMAND_TIMEOUT = 10
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")

APP_NAME = "PythonXP Service Manager CLI"
APP_VERSION = "v0.8.1-cli"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GRAY = "\033[90m"


def c(text, color):
    return f"{color}{text}{RESET}"


def clear():
    os.system("clear" if os.name == "posix" else "cls")


def pause():
    input(f"\n{DIM}Enter drücken zum Fortfahren...{RESET}")


def run_cmd(cmd, timeout=COMMAND_TIMEOUT):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Befehl nach {timeout}s abgebrochen: {' '.join(cmd)}"
    except Exception as e:
        return 1, "", str(e)


def sudo_cmd(cmd, timeout=30):
    return run_cmd(["sudo"] + cmd, timeout=timeout)


def valid_service_name(service):
    return bool(service and SERVICE_NAME_RE.fullmatch(service) and not service.startswith("-"))


def normalize_service_name(name):
    name = name.strip()
    if name and not name.endswith(".service"):
        name += ".service"
    return name


def valid_url(url):
    if not url:
        return True
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_path(path):
    if not path:
        return ""
    return os.path.abspath(os.path.expanduser(path.strip()))


def load_services():
    if not os.path.exists(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(c(f"services.json konnte nicht gelesen werden: {e}", RED))
        return []

    if not isinstance(data, list):
        print(c("services.json muss eine Liste sein.", RED))
        return []

    services = []
    for item in data:
        if not isinstance(item, dict):
            continue
        services.append({
            "name": str(item.get("name", "")).strip(),
            "service": str(item.get("service", "")).strip(),
            "path": str(item.get("path", "")).strip(),
            "url": str(item.get("url", "")).strip(),
        })
    return services


def save_services(services):
    directory = os.path.dirname(CONFIG_FILE)
    fd, tmp_path = tempfile.mkstemp(prefix=".services.", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(services, f, indent=4, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, CONFIG_FILE)
        return True
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        print(c(f"Speichern fehlgeschlagen: {e}", RED))
        return False


def get_status(service):
    if not valid_service_name(service):
        return "invalid"
    code, out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"


def get_enabled(service):
    if not valid_service_name(service):
        return "invalid"
    code, out, _ = run_cmd(["systemctl", "is-enabled", service])
    return out if out else "unknown"


def get_uptime(service):
    if not valid_service_name(service) or get_status(service) != "active":
        return "-"
    _, out, _ = run_cmd(["systemctl", "show", service, "--property=ActiveEnterTimestamp", "--value"])
    if not out:
        return "-"
    code, ts, _ = run_cmd(["date", "-d", out, "+%s"])
    try:
        diff = int(time.time()) - int(ts)
    except Exception:
        return "-"
    if diff < 60:
        return f"{diff}s"
    if diff < 3600:
        return f"{diff // 60}m"
    if diff < 86400:
        return f"{diff // 3600}h"
    return f"{diff // 86400}d"


def status_color(status):
    if status == "active":
        return GREEN
    if status == "inactive":
        return RED
    if status == "failed":
        return YELLOW
    return GRAY


def enabled_text(enabled):
    if enabled == "enabled":
        return c("an", GREEN)
    if enabled == "disabled":
        return c("aus", RED)
    return c(enabled, GRAY)


def print_header():
    print(c("╔" + "═" * 54 + "╗", CYAN))
    print(c(f"║ {APP_NAME:<52} ║", CYAN))
    print(c(f"║ {APP_VERSION:<52} ║", CYAN))
    print(c("╚" + "═" * 54 + "╝", CYAN))


def list_services(filter_text=""):
    services = load_services()
    filter_text = filter_text.lower().strip()

    if filter_text:
        services_to_show = [s for s in services if filter_text in s["name"].lower() or filter_text in s["service"].lower()]
    else:
        services_to_show = services

    print(f"\n{BOLD}{'#':<3} {'Status':<10} {'Autostart':<12} {'Uptime':<8} {'Name':<22} Service{RESET}")
    print("─" * 90)

    for i, item in enumerate(services_to_show, start=1):
        service = item["service"]
        status = get_status(service)
        enabled = get_enabled(service)
        uptime = get_uptime(service)
        dot = "●"
        print(
            f"{i:<3} "
            f"{c(dot, status_color(status))} {c(f'{status:<8}', status_color(status))} "
            f"{enabled_text(enabled):<21} "
            f"{uptime:<8} "
            f"{item['name']:<22} "
            f"{service}"
        )

    print("─" * 90)
    return services_to_show


def choose_service(prompt="Service wählen", allow_filter=True):
    filter_text = ""
    while True:
        clear()
        print_header()
        shown = list_services(filter_text)
        if allow_filter:
            print(f"\n{DIM}Filter aktiv: {filter_text or '-'}{RESET}")
            print("Zahl wählen, /suchtext zum Filtern, Enter für Filter löschen, q zurück")
        else:
            print("Zahl wählen oder q zurück")
        choice = input(f"\n{prompt}: ").strip()
        if choice.lower() == "q":
            return None
        if allow_filter and choice.startswith("/"):
            filter_text = choice[1:].strip()
            continue
        if allow_filter and choice == "":
            filter_text = ""
            continue
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(shown):
                return shown[idx]
        print(c("Ungültige Auswahl.", RED))
        time.sleep(0.8)


def control_service(action):
    item = choose_service(f"Service für '{action}'")
    if not item:
        return
    service = item["service"]
    print(f"\nFühre aus: sudo systemctl {action} {service}")
    code, out, err = sudo_cmd(["systemctl", action, service], timeout=30)
    if code == 0:
        print(c("OK", GREEN))
    else:
        print(c(err or out or "Fehlgeschlagen", RED))
    pause()


def show_logs():
    item = choose_service("Logs für Service")
    if not item:
        return
    service = item["service"]
    print(f"\nLogs: {service}\n")
    # Use journalctl directly, so paging works over SSH/Termius.
    subprocess.run(["journalctl", "-u", service, "-n", "120", "--no-pager"])
    pause()


def add_service_manual():
    clear()
    print_header()
    print(c("Service manuell zur Panel-Liste hinzufügen", BOLD))
    print(c("Hinweis: Die echte .service-Datei muss bereits existieren. Für neue Services den Assistenten nutzen.\n", DIM))

    name = input("Anzeigename: ").strip()
    service = normalize_service_name(input("Systemd Service, z.B. ssh.service: ").strip())
    path = normalize_path(input("Ordner optional: ").strip())
    url = input("URL optional: ").strip()

    if not name or not valid_service_name(service):
        print(c("Name fehlt oder Service-Name ungültig.", RED))
        pause()
        return
    if url and not valid_url(url):
        print(c("URL muss mit http:// oder https:// beginnen.", RED))
        pause()
        return

    services = load_services()
    services.append({"name": name, "service": service, "path": path, "url": url})
    if save_services(services):
        print(c("Service wurde zur Liste hinzugefügt.", GREEN))
    pause()


def remove_service_from_list():
    item = choose_service("Aus Panel-Liste entfernen")
    if not item:
        return
    confirm = input(f"\n{item['name']} wirklich nur aus der Liste entfernen? [j/N]: ").strip().lower()
    if confirm != "j":
        return
    services = load_services()
    services = [s for s in services if not (s["service"] == item["service"] and s["name"] == item["name"])]
    if save_services(services):
        print(c("Aus Liste entfernt. Die echte systemd-Datei bleibt erhalten.", GREEN))
    pause()


def browse_system_services():
    clear()
    print_header()
    query = input("Suchtext für installierte systemd Services: ").strip().lower()
    code, out, err = run_cmd(["systemctl", "list-unit-files", "--type=service", "--no-legend"], timeout=20)
    if code != 0 and not out:
        print(c(err or "Services konnten nicht gelesen werden.", RED))
        pause()
        return
    units = sorted(line.split()[0] for line in out.splitlines() if line.strip())
    if query:
        units = [u for u in units if query in u.lower()]
    print("\n".join(units[:200]))
    if len(units) > 200:
        print(c(f"... {len(units) - 200} weitere Treffer", DIM))
    pause()


def slugify_service_name(name):
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9_.@:-]+", "-", slug)
    slug = slug.strip("-._:")
    if not slug:
        slug = "pythonxp-service"
    return normalize_service_name(slug)


def make_unit_content(description, user, working_dir, exec_start, restart):
    return f"""[Unit]
Description={description}
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={working_dir}
ExecStart={exec_start}
Restart={restart}
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def service_assistant():
    clear()
    print_header()
    print(c("+ Service Assistent", BOLD))
    print("Erstellt eine echte systemd-Service-Datei und trägt sie ins Panel ein.\n")

    project_name = input("Projektname / Anzeigename: ").strip()
    if not project_name:
        print(c("Projektname fehlt.", RED)); pause(); return

    project_dir = normalize_path(input("Projektordner, z.B. /home/pi/Einkaufsliste: ").strip())
    if not project_dir or not os.path.isdir(project_dir):
        print(c("Projektordner existiert nicht.", RED)); pause(); return

    py_file = input("Python-Datei im Ordner, z.B. app.py [app.py]: ").strip() or "app.py"
    if os.path.isabs(py_file):
        py_path = py_file
    else:
        py_path = os.path.join(project_dir, py_file)
    if not os.path.isfile(py_path):
        print(c(f"Python-Datei nicht gefunden: {py_path}", RED)); pause(); return

    url = input("URL optional, z.B. http://127.0.0.1:5050: ").strip()
    if url and not valid_url(url):
        print(c("URL ungültig. Muss mit http:// oder https:// beginnen.", RED)); pause(); return

    default_service = slugify_service_name(project_name)
    service = normalize_service_name(input(f"Service-Dateiname [{default_service}]: ").strip() or default_service)
    if not valid_service_name(service):
        print(c("Service-Name ungültig.", RED)); pause(); return

    user = input("Linux-Benutzer [pi]: ").strip() or "pi"
    restart = input("Restart-Verhalten [always]: ").strip() or "always"
    autostart = input("Autostart aktivieren? [J/n]: ").strip().lower() != "n"
    start_now = input("Direkt starten? [j/N]: ").strip().lower() == "j"

    exec_start = f"/usr/bin/python3 {shlex.quote(py_path)}"
    unit_content = make_unit_content(project_name, user, project_dir, exec_start, restart)
    unit_path = f"/etc/systemd/system/{service}"

    clear()
    print_header()
    print(c("Folgende Service-Datei wird erstellt:", BOLD))
    print(c(unit_path, CYAN))
    print("\n" + unit_content)
    confirm = input("Erstellen? [j/N]: ").strip().lower()
    if confirm != "j":
        return

    # Write safely via sudo tee.
    try:
        proc = subprocess.run(
            ["sudo", "tee", unit_path],
            input=unit_content,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(c(proc.stderr.strip() or "Schreiben fehlgeschlagen.", RED)); pause(); return
    except Exception as e:
        print(c(str(e), RED)); pause(); return

    for cmd in [["systemctl", "daemon-reload"]]:
        code, out, err = sudo_cmd(cmd, timeout=30)
        if code != 0:
            print(c(err or out or f"Fehler bei {' '.join(cmd)}", RED)); pause(); return

    if autostart:
        code, out, err = sudo_cmd(["systemctl", "enable", service], timeout=30)
        if code != 0:
            print(c(err or out or "Enable fehlgeschlagen.", RED))

    if start_now:
        code, out, err = sudo_cmd(["systemctl", "start", service], timeout=30)
        if code != 0:
            print(c(err or out or "Start fehlgeschlagen.", RED))

    services = load_services()
    if not any(s["service"] == service for s in services):
        services.append({"name": project_name, "service": service, "path": project_dir, "url": url})
        save_services(services)

    print(c("\nService wurde erstellt und eingetragen.", GREEN))
    pause()


def main_menu():
    while True:
        clear()
        print_header()
        list_services()
        print(f"\n{BOLD}Aktionen:{RESET}")
        print("1  Aktualisieren / Services anzeigen")
        print("2  Service starten")
        print("3  Service stoppen")
        print("4  Service neustarten")
        print("5  Autostart aktivieren")
        print("6  Autostart deaktivieren")
        print("7  Logs anzeigen")
        print("8  Service manuell zur Liste hinzufügen")
        print("9  Service aus Liste entfernen")
        print("10 Installierte Services durchsuchen")
        print("11 + Service Assistent")
        print("q  Beenden")

        choice = input("\nAuswahl: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            break
        if choice == "1":
            continue
        if choice == "2":
            control_service("start")
        elif choice == "3":
            control_service("stop")
        elif choice == "4":
            control_service("restart")
        elif choice == "5":
            control_service("enable")
        elif choice == "6":
            control_service("disable")
        elif choice == "7":
            show_logs()
        elif choice == "8":
            add_service_manual()
        elif choice == "9":
            remove_service_from_list()
        elif choice == "10":
            browse_system_services()
        elif choice == "11":
            service_assistant()
        else:
            print(c("Ungültige Auswahl.", RED))
            time.sleep(0.8)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nBeendet.")
