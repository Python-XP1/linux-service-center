#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "services.json")
COMMAND_TIMEOUT = 10

SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")
USER_NAME_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.-]*[$]?|[0-9]+)$")
RESTART_POLICIES = {"no", "always", "on-success", "on-failure", "on-abnormal", "on-abort", "on-watchdog"}

# Keep diagnostics generic so the project does not assume optional services
# such as a specific remote-access stack are installed.
DIAGNOSTIC_COMMANDS = [
    ("hostname -I", ["hostname", "-I"], False),
    ("uptime -p", ["uptime", "-p"], False),
    ("who -b", ["who", "-b"], False),
    ("ss -tulpen", ["ss", "-tulpen"], False),
    ("ip addr", ["ip", "addr"], False),
    ("systemctl --failed --no-pager", ["systemctl", "--failed", "--no-pager"], False),
    ("systemctl list-units --type=service --state=running --no-pager", ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"], False),
]

APP_NAME = "Linux Service Center CLI"
APP_VERSION = "v0.9.2-cli"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"


def c(text, color):
    return f"{color}{text}{RESET}"


def clear():
    os.system("clear" if os.name == "posix" else "cls")


def read_input(prompt_text, default=None):
    try:
        value = input(prompt_text).strip()
    except EOFError:
        print(c("\nInput cancelled: terminal input is not available.", RED))
        return None

    if value == "" and default is not None:
        return default
    return value


def pause():
    try:
        input(f"\n{DIM}Press Enter to continue...{RESET}")
    except EOFError:
        pass


def run_cmd(cmd, timeout=COMMAND_TIMEOUT):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 1, "", str(e)


def sudo_cmd(cmd, timeout=30):
    return run_cmd(["sudo"] + cmd, timeout=timeout)


def run_diagnostic_command(command, use_shell=False, timeout=20):
    try:
        result = subprocess.run(
            command,
            shell=use_shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout.strip()
        error = result.stderr.strip()
        if error:
            output = f"{output}\n{error}".strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 124, f"Command timed out after {timeout}s"
    except OSError as e:
        return 1, str(e)


def valid_service_name(service):
    return bool(service and SERVICE_NAME_RE.fullmatch(service) and not service.startswith("-"))


def valid_user_name(user_name):
    return bool(user_name and USER_NAME_RE.fullmatch(user_name))


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
    except json.JSONDecodeError as e:
        print(c(f"services.json contains invalid JSON: {e}", RED))
        return []
    except OSError as e:
        print(c(f"services.json could not be read: {e}", RED))
        return []

    if not isinstance(data, list):
        print(c("services.json must contain a list.", RED))
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
    tmp_path = None

    try:
        # Replace the config atomically to avoid leaving a partial JSON file
        # behind if writing fails.
        fd, tmp_path = tempfile.mkstemp(prefix=".services.", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(services, f, indent=4, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, CONFIG_FILE)
        return True
    except (OSError, TypeError, ValueError) as e:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        print(c(f"Save failed: {e}", RED))
        return False


def get_status(service):
    if not valid_service_name(service):
        return "invalid"
    _, out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"


def get_enabled(service):
    if not valid_service_name(service):
        return "invalid"
    _, out, _ = run_cmd(["systemctl", "is-enabled", service])
    return out if out else "unknown"


def get_uptime(service):
    if not valid_service_name(service) or get_status(service) != "active":
        return "-"

    _, out, _ = run_cmd([
        "systemctl",
        "show",
        service,
        "--property=ActiveEnterTimestamp",
        "--value"
    ])

    if not out:
        return "-"

    _, ts, _ = run_cmd(["date", "-d", out, "+%s"])

    try:
        diff = int(time.time()) - int(ts)
    except (TypeError, ValueError):
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
        return c("on", GREEN)
    if enabled == "disabled":
        return c("off", RED)
    return c(enabled, GRAY)


def print_header():
    width = 62
    print(c("+" + "-" * width + "+", CYAN))
    print(c(f"| {APP_NAME:<60} |", CYAN))
    print(c(f"| {APP_VERSION:<60} |", CYAN))
    print(c("+" + "-" * width + "+", CYAN))


def list_services(filter_text=""):
    services = load_services()
    filter_text = filter_text.lower().strip()

    if filter_text:
        services_to_show = [
            s for s in services
            if filter_text in s["name"].lower() or filter_text in s["service"].lower()
        ]
    else:
        services_to_show = services

    print(f"\n{BOLD}{'#':<3} {'Status':<10} {'Startup':<12} {'Uptime':<8} {'Name':<22} Service{RESET}")
    print("-" * 90)

    if not services_to_show:
        print(c("No services configured yet. Add a service to get started.", GRAY))

    for i, item in enumerate(services_to_show, start=1):
        service = item["service"]
        status = get_status(service)
        enabled = get_enabled(service)
        uptime = get_uptime(service)
        marker = "o"

        print(
            f"{i:<3} "
            f"{c(marker, status_color(status))} {c(f'{status:<8}', status_color(status))} "
            f"{enabled_text(enabled):<21} "
            f"{uptime:<8} "
            f"{item['name']:<22} "
            f"{service}"
        )

    print("-" * 90)
    return services_to_show


def choose_service(prompt="Select service", allow_filter=True):
    filter_text = ""

    while True:
        clear()
        print_header()
        shown = list_services(filter_text)

        if allow_filter:
            print(f"\n{DIM}Active filter: {filter_text or '-'}{RESET}")
            print("Choose number, /search to filter, Enter to clear filter, q back")
        else:
            print("Choose number or q back")

        choice = read_input(f"\n{prompt}: ")

        if choice is None:
            return None
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

        print(c("Invalid selection.", RED))
        time.sleep(0.8)


def control_service(action):
    item = choose_service(f"Service for '{action}'")
    if not item:
        return

    service = item["service"]
    print(f"\nRunning: sudo systemctl {action} {service}")

    code, out, err = sudo_cmd(["systemctl", action, service], timeout=30)

    if code == 0:
        print(c("OK", GREEN))
    else:
        print(c(err or out or "Failed", RED))

    pause()


def show_logs():
    item = choose_service("Logs for service")
    if not item:
        return

    service = item["service"]
    print(f"\nLogs: {service}\n")

    code, out, err = run_cmd(["journalctl", "-u", service, "-n", "120", "--no-pager"], timeout=20)

    if out:
        print(out)
    if code != 0:
        print(c(err or "Could not read logs.", RED))

    pause()


def add_service_manual():
    clear()
    print_header()
    print(c("Add existing service to panel list", BOLD))
    print(c("Note: The real .service file must already exist. Use assistant for new services.\n", DIM))

    name = read_input("Display name: ")
    if name is None:
        return

    service_input = read_input("Systemd service, example ssh.service: ")
    if service_input is None:
        return

    path_input = read_input("Folder optional: ")
    if path_input is None:
        return

    url = read_input("URL optional: ")
    if url is None:
        return

    service = normalize_service_name(service_input)
    path = normalize_path(path_input)

    if not name or not valid_service_name(service):
        print(c("Missing name or invalid service name.", RED))
        pause()
        return

    if url and not valid_url(url):
        print(c("URL must start with http:// or https://.", RED))
        pause()
        return

    services = load_services()

    if any(s["service"] == service for s in services):
        print(c("This service is already in the panel list.", YELLOW))
        pause()
        return

    services.append({
        "name": name,
        "service": service,
        "path": path,
        "url": url
    })

    if save_services(services):
        print(c("Service added to panel list.", GREEN))

    pause()


def remove_service_from_list():
    item = choose_service("Remove from panel list")
    if not item:
        return

    confirm = read_input(f"\nRemove {item['name']} only from panel list? [y/N]: ", default="n")
    if confirm is None:
        return

    if confirm.lower() != "y":
        return

    services = load_services()
    services = [
        s for s in services
        if not (s["service"] == item["service"] and s["name"] == item["name"])
    ]

    if save_services(services):
        print(c("Removed from list. The real systemd file remains unchanged.", GREEN))

    pause()


def browse_system_services():
    clear()
    print_header()

    query = read_input("Search text for installed systemd services: ", default="")
    if query is None:
        return

    query = query.lower()

    code, out, err = run_cmd(
        ["systemctl", "list-unit-files", "--type=service", "--no-legend"],
        timeout=20
    )

    if code != 0 and not out:
        print(c(err or "Could not read services.", RED))
        pause()
        return

    units = sorted(line.split()[0] for line in out.splitlines() if line.strip())

    if query:
        units = [u for u in units if query in u.lower()]

    print()

    for unit in units[:200]:
        print(unit)

    if len(units) > 200:
        print(c(f"... {len(units) - 200} more matches", DIM))

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
    print(c("+ Service Assistant", BOLD))
    print("Creates a real systemd service file and adds it to the panel.\n")

    project_name = read_input("Project name / display name: ")
    if project_name is None:
        return
    if not project_name:
        print(c("Project name missing.", RED))
        pause()
        return

    project_dir_input = read_input("Project folder, example /home/pi/my-service: ")
    if project_dir_input is None:
        return

    project_dir = normalize_path(project_dir_input)

    if not project_dir or not os.path.isdir(project_dir):
        print(c("Project folder does not exist.", RED))
        pause()
        return

    py_file = read_input("Python file in folder [app.py]: ", default="app.py")
    if py_file is None:
        return

    if os.path.isabs(py_file):
        py_path = py_file
    else:
        py_path = os.path.join(project_dir, py_file)

    if not os.path.isfile(py_path):
        print(c(f"Python file not found: {py_path}", RED))
        pause()
        return

    url = read_input("URL optional, example http://127.0.0.1:5050: ", default="")
    if url is None:
        return

    if url and not valid_url(url):
        print(c("Invalid URL. Must start with http:// or https://.", RED))
        pause()
        return

    default_service = slugify_service_name(project_name)

    service_input = read_input(f"Service filename [{default_service}]: ", default=default_service)
    if service_input is None:
        return

    service = normalize_service_name(service_input)

    if not valid_service_name(service):
        print(c("Invalid service name.", RED))
        pause()
        return

    user = read_input("Linux user [pi]: ", default="pi")
    if user is None:
        return

    if not valid_user_name(user):
        print(c("Invalid Linux user.", RED))
        pause()
        return

    restart = read_input("Restart policy [always]: ", default="always")
    if restart is None:
        return

    restart = restart.lower()

    if restart not in RESTART_POLICIES:
        print(c("Invalid restart policy. Example: always, on-failure or no.", RED))
        pause()
        return

    autostart_input = read_input("Enable startup? [Y/n]: ", default="y")
    if autostart_input is None:
        return

    start_now_input = read_input("Start now? [y/N]: ", default="n")
    if start_now_input is None:
        return

    autostart = autostart_input.lower() != "n"
    start_now = start_now_input.lower() == "y"

    exec_start = f"/usr/bin/python3 {shlex.quote(py_path)}"
    unit_content = make_unit_content(project_name, user, project_dir, exec_start, restart)
    unit_path = f"/etc/systemd/system/{service}"

    clear()
    print_header()
    print(c("This service file will be created:", BOLD))
    print(c(unit_path, CYAN))
    print("\n" + unit_content)

    confirm = read_input("Create service? [y/N]: ", default="n")
    if confirm is None:
        return

    if confirm.lower() != "y":
        return

    try:
        proc = subprocess.run(
            ["sudo", "tee", unit_path],
            input=unit_content,
            text=True,
            capture_output=True,
            timeout=30,
        )

        if proc.returncode != 0:
            print(c(proc.stderr.strip() or "Writing service file failed.", RED))
            pause()
            return

    except subprocess.TimeoutExpired:
        print(c("Writing failed: sudo tee timed out.", RED))
        pause()
        return
    except OSError as e:
        print(c(str(e), RED))
        pause()
        return

    warnings = []

    code, out, err = sudo_cmd(["systemctl", "daemon-reload"], timeout=30)
    if code != 0:
        print(c(err or out or "systemctl daemon-reload failed", RED))
        pause()
        return

    if autostart:
        code, out, err = sudo_cmd(["systemctl", "enable", service], timeout=30)
        if code != 0:
            warnings.append(err or out or "Enable failed.")

    if start_now:
        code, out, err = sudo_cmd(["systemctl", "start", service], timeout=30)
        if code != 0:
            warnings.append(err or out or "Start failed.")

    services = load_services()

    if not any(s["service"] == service for s in services):
        services.append({
            "name": project_name,
            "service": service,
            "path": project_dir,
            "url": url
        })

        if not save_services(services):
            warnings.append("Service was created but could not be saved to services.json.")

    if warnings:
        print(c("\nService file was created, but warnings occurred:", YELLOW))
        for warning in warnings:
            print(c(f"- {warning}", YELLOW))
    else:
        print(c("\nService created successfully.", GREEN))

    pause()


def show_diagnostics():
    clear()
    print_header()
    print(c("Diagnostics", BOLD))

    for label, command, use_shell in DIAGNOSTIC_COMMANDS:
        print(f"\n$ {label}")
        code, output = run_diagnostic_command(command, use_shell=use_shell)
        if output:
            print(output)
        else:
            print("(no output)")
        if code != 0:
            print(c(f"[Exit {code}]", YELLOW))

    pause()


def main_menu():
    while True:
        clear()
        print_header()
        list_services()

        print(f"\n{BOLD}Actions:{RESET}")
        print("1  Refresh / show services")
        print("2  Start service")
        print("3  Stop service")
        print("4  Restart service")
        print("5  Enable startup")
        print("6  Disable startup")
        print("7  Show logs")
        print("8  Add existing service to list")
        print("9  Remove service from list")
        print("10 Browse installed services")
        print("11 + Service Assistant")
        print("12 Show diagnostics")
        print("q  Quit")

        choice = read_input("\nSelection: ")

        if choice is None:
            break

        choice = choice.lower()

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
        elif choice == "12":
            show_diagnostics()
        else:
            print(c("Invalid selection.", RED))
            time.sleep(0.8)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nExited.")
