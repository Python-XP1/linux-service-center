#!/usr/bin/env python3
import json
import os
import re
import shlex
import shutil
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
VALID_SERVICE_SCOPES = {"system", "user"}
DEFAULT_SERVICE_SCOPE = "system"
PERMISSION_REQUIRED_MESSAGE = "Permission required or action cancelled."

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
APP_VERSION = "v0.9.3"

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


def run_interactive_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, timeout=timeout)
        return result.returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError as e:
        print(str(e))
        return 1


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


def parse_systemd_service_names(output):
    services = set()
    for line in output.splitlines():
        parts = line.split()
        if parts and parts[0].endswith(".service"):
            services.add(parts[0])
    return services


def collect_systemd_services(scope):
    scope = normalize_service_scope(scope)
    base_cmd = ["systemctl"]
    if scope == "user":
        base_cmd.append("--user")

    commands = [
        base_cmd + ["list-unit-files", "--type=service", "--no-legend"],
        base_cmd + ["list-units", "--type=service", "--all", "--no-legend"],
    ]

    services = set()
    for command in commands:
        _, out, _ = run_cmd(command, timeout=20)
        if out:
            services.update(parse_systemd_service_names(out))
    return services


def detect_service_scope(service):
    service = normalize_service_name(service)
    if not valid_service_name(service):
        return DEFAULT_SERVICE_SCOPE, False, False

    system_services = collect_systemd_services("system")
    user_services = collect_systemd_services("user")
    found_system = service in system_services
    found_user = service in user_services

    if found_system and not found_user:
        return "system", True, False
    if found_user and not found_system:
        return "user", False, True
    return None, found_system, found_user


def list_services_with_scopes():
    entries = []
    for service in sorted(collect_systemd_services("system")):
        entries.append((service, "system"))
    for service in sorted(collect_systemd_services("user")):
        entries.append((service, "user"))
    return entries


def normalize_service_scope(scope):
    scope = str(scope or DEFAULT_SERVICE_SCOPE).strip().lower()
    return scope if scope in VALID_SERVICE_SCOPES else DEFAULT_SERVICE_SCOPE


def is_user_service_not_found(scope, message):
    lowered = str(message or "").lower()
    return scope == "user" and any(
        token in lowered
        for token in ["could not be found", "not-found", "not found", "unit "]
    )


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


def resolve_venv_python(venv_path):
    if not venv_path:
        return ""
    return os.path.join(venv_path, "bin", "python")


def systemd_quote_arg(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_command(command):
    try:
        return shlex.split(command)
    except ValueError:
        return []


def command_has_python_prefix(parts):
    if not parts:
        return False
    executable = os.path.basename(parts[0])
    return executable in {"python", "python3"} or executable.startswith("python3.")


def build_python_exec_start(python_executable, start_command, script_path):
    python_executable = normalize_path(python_executable) if python_executable else ""
    command = start_command.strip()

    if command:
        parts = split_command(command)
        if not parts:
            return ""
        if python_executable and command_has_python_prefix(parts):
            parts[0] = python_executable
            return " ".join(systemd_quote_arg(part) for part in parts)
        if python_executable:
            return " ".join([systemd_quote_arg(python_executable)] + [systemd_quote_arg(part) for part in parts])
        return " ".join(systemd_quote_arg(part) for part in parts)

    if not script_path:
        return ""

    python_cmd = python_executable or "/usr/bin/python3"
    return f"{systemd_quote_arg(python_cmd)} {systemd_quote_arg(script_path)}"


def validate_python_service_fields(workdir="", venv_path="", python_executable="", start_command=""):
    if workdir:
        workdir = normalize_path(workdir)
        if not os.path.isdir(workdir):
            return "Working directory does not exist."

    if venv_path:
        venv_path = normalize_path(venv_path)
        venv_python = resolve_venv_python(venv_path)
        if not os.path.isfile(venv_python):
            return f"Virtualenv Python executable was not found: {venv_python}"

    if python_executable:
        python_executable = normalize_path(python_executable)
        if not os.path.isfile(python_executable):
            return "Python executable does not exist."

    if "\n" in start_command or "\r" in start_command:
        return "Start command must not contain line breaks."

    return None


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
        path = str(item.get("path", "")).strip()
        workdir = str(item.get("workdir", "")).strip()

        services.append({
            "name": str(item.get("name", "")).strip(),
            "service": str(item.get("service", "")).strip(),
            "scope": normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE)),
            "path": path,
            "workdir": workdir,
            "venv_path": str(item.get("venv_path", "")).strip(),
            "python_executable": str(item.get("python_executable", "")).strip(),
            "start_command": str(item.get("start_command", "")).strip(),
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


def systemctl_read_command(scope, action, service):
    cmd = ["systemctl"]
    if normalize_service_scope(scope) == "user":
        cmd.append("--user")
    return cmd + [action, service]


def systemctl_action_command(scope, action, service):
    return systemctl_read_command(scope, action, service)


def journalctl_command(scope, service):
    if normalize_service_scope(scope) == "user":
        return ["journalctl", "--user-unit", service, "-n", "120", "--no-pager"]
    return ["journalctl", "-u", service, "-n", "120", "--no-pager"]


def run_systemctl_command(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        message = result.stderr.strip() or result.stdout.strip()
        return result.returncode == 0, message
    except subprocess.TimeoutExpired:
        raise
    except OSError as e:
        return False, str(e)


def needs_authentication(message):
    lowered = str(message or "").lower()
    return (
        "password" in lowered
        or "authentication" in lowered
        or "interactive authentication" in lowered
        or "not permitted" in lowered
    )


def is_permission_error(message):
    lowered = str(message or "").lower()
    return any(
        token in lowered
        for token in [
            "password",
            "authentication",
            "interactive authentication",
            "not permitted",
            "permission denied",
            "cancelled",
            "canceled",
        ]
    )


def run_systemctl_action(action, service, scope=DEFAULT_SERVICE_SCOPE):
    scope = normalize_service_scope(scope)

    try:
        base_cmd = systemctl_action_command(scope, action, service)

        if scope == "user":
            ok, message = run_systemctl_command(base_cmd)
            if not ok and is_user_service_not_found(scope, message):
                return False, f"User service not found: {service}"
            return ok, message

        if os.geteuid() == 0:
            return run_systemctl_command(base_cmd)

        ok, sudo_message = run_systemctl_command(["sudo"] + base_cmd)
        if ok:
            return True, sudo_message

        if is_permission_error(sudo_message) or not sudo_message:
            return False, PERMISSION_REQUIRED_MESSAGE
        return False, sudo_message

    except subprocess.TimeoutExpired:
        if scope == "system":
            return False, PERMISSION_REQUIRED_MESSAGE
        return False, "systemctl did not respond within 30 seconds."

    except OSError as e:
        return False, str(e)


def get_status(service, scope=DEFAULT_SERVICE_SCOPE):
    if not valid_service_name(service):
        return "invalid"

    code, out, err = run_cmd(systemctl_read_command(scope, "status", service) + ["--no-pager"])
    combined = f"{out}\\n{err}".lower()
    scope = normalize_service_scope(scope)
    if is_user_service_not_found(scope, combined):
        return "not-found"
    if "active: active" in combined:
        return "active"
    if "active: failed" in combined or "failed" in combined:
        return "failed"
    if "active: inactive" in combined or "inactive" in combined:
        return "inactive"
    if code != 0 and not combined.strip():
        return "unknown"
    return "unknown"


def get_enabled(service, scope=DEFAULT_SERVICE_SCOPE):
    if not valid_service_name(service):
        return "invalid"

    code, out, err = run_cmd(systemctl_read_command(scope, "is-enabled", service))
    message = err or out
    if is_user_service_not_found(normalize_service_scope(scope), message):
        return "not-found"
    if code != 0 and not out:
        return "unknown"
    return out if out else "unknown"


def get_uptime(service, scope=DEFAULT_SERVICE_SCOPE):
    if not valid_service_name(service) or get_status(service, scope) != "active":
        return "-"

    code, out, _ = run_cmd(systemctl_read_command(scope, "show", service) + [
        "--property=ActiveEnterTimestamp",
        "--value"
    ])

    if code != 0 or not out:
        return "-"

    try:
        result = subprocess.run(
            ["date", "-d", out, "+%s"],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT
        )
        start_ts = int(result.stdout.strip())
        diff = int(time.time()) - start_ts
    except (ValueError, subprocess.SubprocessError, OSError):
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

    print(f"\n{BOLD}{'#':<3} {'Scope':<8} {'Status':<10} {'Startup':<12} {'Uptime':<8} {'Name':<22} Service{RESET}")
    print("-" * 90)

    if not services_to_show:
        print(c("No services configured yet. Add a service to get started.", GRAY))

    for i, item in enumerate(services_to_show, start=1):
        service = item["service"]
        scope = normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))
        status = get_status(service, scope)
        enabled = get_enabled(service, scope)
        uptime = get_uptime(service, scope)
        marker = "o"

        print(
            f"{i:<3} "
            f"{scope:<8} "
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
    scope = normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))

    if scope == "system":
        confirm = read_input(
            "\nYou are about to run a system-level action. "
            "This may affect your operating system or critical services. Continue? [y/N]: ",
            default="n"
        )
        if confirm is None or confirm.lower() != "y":
            print(c(PERMISSION_REQUIRED_MESSAGE, RED))
            pause()
            return
        cmd = ["sudo", "systemctl", action, service]
    else:
        cmd = ["systemctl", "--user", action, service]

    print(f"\nRunning: {' '.join(cmd)}")

    if scope == "system":
        code = run_interactive_cmd(cmd, timeout=30)
        out = ""
        err = ""
    else:
        code, out, err = run_cmd(cmd, timeout=30)

    if code == 0:
        print(c("OK", GREEN))
    elif scope == "system":
        print(c("Permission required or action failed.", RED))
    else:
        print(c(err or out or "Failed", RED))

    pause()


def show_logs():
    item = choose_service("Logs for service")
    if not item:
        return

    service = item["service"]
    scope = normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))
    print(f"\nLogs: [{scope.upper()}] {service}\n")

    code, out, err = run_cmd(journalctl_command(scope, service), timeout=20)

    if out:
        print(out)
    if code != 0:
        if scope == "user" and is_user_service_not_found(scope, err or out):
            print(c(f"User service not found: {service}", RED))
        else:
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

    detected_scope, found_system, found_user = detect_service_scope(service_input)
    if found_system and found_user:
        print(c("This service exists as both system and user service. Please choose the correct scope.", YELLOW))
        detected_scope = DEFAULT_SERVICE_SCOPE
    elif detected_scope:
        print(c(f"Detected scope: {detected_scope}", GREEN))
    else:
        print(c("Service not found. Please select the correct scope manually.", YELLOW))
        detected_scope = DEFAULT_SERVICE_SCOPE

    scope_input = read_input(f"Scope [system/user] [{detected_scope}]: ", default=detected_scope)
    if scope_input is None:
        return
    scope = normalize_service_scope(scope_input)

    path_input = read_input("Folder/path optional: ")
    if path_input is None:
        return

    workdir_input = read_input("Working directory optional: ")
    if workdir_input is None:
        return

    venv_input = read_input("Virtualenv path optional, example /path/to/project/.venv: ")
    if venv_input is None:
        return

    python_input = read_input("Python executable optional, example /path/to/project/.venv/bin/python: ")
    if python_input is None:
        return

    start_command = read_input("Start command optional, example app.py or python app.py: ")
    if start_command is None:
        return

    url = read_input("URL optional: ")
    if url is None:
        return

    service = normalize_service_name(service_input)
    path = normalize_path(path_input)
    workdir = normalize_path(workdir_input)
    venv_path = normalize_path(venv_input)
    python_executable = normalize_path(python_input)

    if not name or not valid_service_name(service):
        print(c("Missing name or invalid service name.", RED))
        pause()
        return

    if url and not valid_url(url):
        print(c("URL must start with http:// or https://.", RED))
        pause()
        return

    validation_error = validate_python_service_fields(workdir, venv_path, python_executable, start_command)
    if validation_error:
        print(c(validation_error, RED))
        pause()
        return

    services = load_services()

    if any(s["service"] == service and normalize_service_scope(s.get("scope", DEFAULT_SERVICE_SCOPE)) == scope for s in services):
        print(c("This service is already in the panel list.", YELLOW))
        pause()
        return

    services.append({
        "name": name,
        "service": service,
        "scope": scope,
        "path": path or workdir,
        "workdir": workdir,
        "venv_path": venv_path,
        "python_executable": python_executable,
        "start_command": start_command,
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


def edit_service_entry():
    item = choose_service("Edit service")
    if not item:
        return

    services = load_services()
    try:
        index = next(
            i for i, service in enumerate(services)
            if service["name"] == item["name"]
            and service["service"] == item["service"]
            and normalize_service_scope(service.get("scope", DEFAULT_SERVICE_SCOPE)) == normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))
        )
    except StopIteration:
        print(c("The selected service no longer exists.", RED))
        pause()
        return

    print(c("\nLeave a field empty to keep the current value.", DIM))

    name = read_input(f"Display name [{item['name']}]: ", default=item["name"])
    if name is None:
        return

    service_input = read_input(f"Systemd service [{item['service']}]: ", default=item["service"])
    if service_input is None:
        return
    service_name = normalize_service_name(service_input)

    current_scope = normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))
    scope_input = read_input(f"Scope [system/user] [{current_scope}]: ", default=current_scope)
    if scope_input is None:
        return
    scope = normalize_service_scope(scope_input)

    path_value = read_input(f"Folder/path optional [{item.get('path', '')}]: ", default=item.get("path", ""))
    if path_value is None:
        return

    workdir_value = read_input(f"Working directory optional [{item.get('workdir', '')}]: ", default=item.get("workdir", ""))
    if workdir_value is None:
        return

    venv_value = read_input(f"Virtualenv path optional [{item.get('venv_path', '')}]: ", default=item.get("venv_path", ""))
    if venv_value is None:
        return

    python_value = read_input(f"Python executable optional [{item.get('python_executable', '')}]: ", default=item.get("python_executable", ""))
    if python_value is None:
        return

    command_value = read_input(f"Start command optional [{item.get('start_command', '')}]: ", default=item.get("start_command", ""))
    if command_value is None:
        return

    url = read_input(f"URL optional [{item.get('url', '')}]: ", default=item.get("url", ""))
    if url is None:
        return

    path = normalize_path(path_value)
    workdir = normalize_path(workdir_value)
    venv_path = normalize_path(venv_value)
    python_executable = normalize_path(python_value)

    if not name or not valid_service_name(service_name):
        print(c("Missing name or invalid service name.", RED))
        pause()
        return

    if url and not valid_url(url):
        print(c("URL must start with http:// or https://.", RED))
        pause()
        return

    validation_error = validate_python_service_fields(workdir, venv_path, python_executable, command_value)
    if validation_error:
        print(c(validation_error, RED))
        pause()
        return

    services[index] = {
        "name": name,
        "service": service_name,
        "scope": scope,
        "path": path or workdir,
        "workdir": workdir,
        "venv_path": venv_path,
        "python_executable": python_executable,
        "start_command": command_value,
        "url": url
    }

    if save_services(services):
        print(c("Service entry updated.", GREEN))

    pause()


def open_url_for_service():
    item = choose_service("Open URL for service")
    if not item:
        return

    url = item.get("url", "")
    if not valid_url(url):
        print(c("No valid http(s) URL is configured.", RED))
        pause()
        return

    try:
        subprocess.Popen(["xdg-open", url])
        print(c(f"Opened URL: {url}", GREEN))
    except OSError as e:
        print(c(f"Open URL failed: {e}", RED))

    pause()


def open_folder_for_service():
    item = choose_service("Open folder for service")
    if not item:
        return

    path = normalize_path(item.get("path", "") or item.get("workdir", ""))
    if not path or not os.path.isdir(path):
        print(c("Project folder not found.", RED))
        pause()
        return

    try:
        subprocess.Popen(["xdg-open", path])
        print(c(f"Opened folder: {path}", GREEN))
    except OSError as e:
        print(c(f"Open folder failed: {e}", RED))

    pause()


def open_code_for_service():
    item = choose_service("Open in VS Code")
    if not item:
        return

    path = normalize_path(item.get("path", "") or item.get("workdir", ""))
    if not path or not os.path.isdir(path):
        print(c("Project folder not found.", RED))
        pause()
        return

    code_cmd = shutil.which("code")
    if not code_cmd:
        print(c("VS Code was not found.", RED))
        pause()
        return

    try:
        subprocess.Popen([code_cmd, path], cwd=path)
        print(c(f"Opened in VS Code: {path}", GREEN))
    except OSError as e:
        print(c(f"VS Code error: {e}", RED))

    pause()


def browse_system_services():
    clear()
    print_header()

    query = read_input("Search text for installed systemd services: ", default="")
    if query is None:
        return

    query = query.lower()
    entries = list_services_with_scopes()
    if query:
        entries = [(service, scope) for service, scope in entries if query in service.lower() or query in scope]

    print()
    for service, scope in entries[:200]:
        print(f"[{scope.upper()}] {service}")

    if len(entries) > 200:
        print(c(f"... {len(entries) - 200} more matches", DIM))
    if not entries:
        print(c("No matching services found.", GRAY))

    pause()



def slugify_service_name(name):
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9_.@:-]+", "-", slug)
    slug = slug.strip("-._:")

    if not slug:
        slug = "pythonxp-service"

    return normalize_service_name(slug)


def make_unit_content(description, user, working_dir, exec_start, restart, install_target="multi-user.target"):
    user_line = f"User={user}\n" if user else ""
    return f"""[Unit]
Description={description}
After=network.target

[Service]
Type=simple
{user_line}\
WorkingDirectory={working_dir}
ExecStart={exec_start}
Restart={restart}
RestartSec=5

[Install]
WantedBy={install_target}
"""


def user_systemd_service_dir():
    return os.path.join(os.path.expanduser("~"), ".config", "systemd", "user")


def user_systemd_service_path(service):
    return os.path.join(user_systemd_service_dir(), service)


def folder_is_inside_home(folder):
    home = normalize_path(os.path.expanduser("~"))
    folder = normalize_path(folder)
    try:
        return os.path.commonpath([home, folder]) == home
    except ValueError:
        return False


def write_user_service_file(service, unit_content):
    service_dir = user_systemd_service_dir()
    service_path = user_systemd_service_path(service)

    try:
        os.makedirs(service_dir, exist_ok=True)
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(unit_content)
        os.chmod(service_path, 0o644)
        return True, service_path
    except OSError as e:
        return False, str(e)


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

    recommended_scope = "user" if folder_is_inside_home(project_dir) else "system"
    print("\nService type")
    print("User service:")
    print("  Runs only for your account.")
    print("  No administrator privileges required.")
    print("System service:")
    print("  Runs system-wide and requires administrator privileges.")

    service_scope_input = read_input(
        f"Service type [user/system] [{recommended_scope}]: ",
        default=recommended_scope
    )
    if service_scope_input is None:
        return

    service_scope = normalize_service_scope(service_scope_input)

    detected_venv = os.path.join(project_dir, ".venv")
    if not os.path.isfile(resolve_venv_python(detected_venv)):
        detected_venv = ""

    venv_path = read_input(
        f"Virtualenv path optional [{detected_venv}]: " if detected_venv else "Virtualenv path optional: ",
        default=detected_venv
    )
    if venv_path is None:
        return

    venv_path = normalize_path(venv_path)

    if venv_path:
        venv_python = resolve_venv_python(venv_path)
        if not os.path.isfile(venv_python):
            print(c(f"Virtualenv Python executable not found: {venv_python}", RED))
            pause()
            return
    else:
        venv_python = ""

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

    python_default = venv_python
    python_executable = read_input(
        f"Python executable optional [{python_default}]: " if python_default else "Python executable optional: ",
        default=python_default
    )
    if python_executable is None:
        return

    python_executable = normalize_path(python_executable)

    if python_executable and not os.path.isfile(python_executable):
        print(c("Python executable does not exist.", RED))
        pause()
        return

    start_command = read_input("Start command optional, example app.py or python app.py: ", default="")
    if start_command is None:
        return

    validation_error = validate_python_service_fields(project_dir, venv_path, python_executable, start_command)
    if validation_error:
        print(c(validation_error, RED))
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

    user = ""
    if service_scope == "system":
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

    exec_start = build_python_exec_start(python_executable, start_command, py_path)
    if not exec_start:
        print(c("Start command could not be built.", RED))
        pause()
        return

    install_target = "default.target" if service_scope == "user" else "multi-user.target"
    unit_content = make_unit_content(project_name, user, project_dir, exec_start, restart, install_target)
    unit_path = user_systemd_service_path(service) if service_scope == "user" else f"/etc/systemd/system/{service}"

    clear()
    print_header()
    if service_scope == "user":
        print(c("Create user service?", BOLD))
    else:
        print(c("Create system service?", BOLD))
        print(c("Administrator privileges required.", YELLOW))
    print(c(unit_path, CYAN))
    print("\n" + unit_content)

    confirm = read_input("Create service? [y/N]: ", default="n")
    if confirm is None:
        return

    if confirm.lower() != "y":
        return

    warnings = []

    if service_scope == "user":
        ok, message = write_user_service_file(service, unit_content)
        if not ok:
            print(c(message or "Writing service file failed.", RED))
            pause()
            return

        code, out, err = run_cmd(["systemctl", "--user", "daemon-reload"], timeout=30)
        if code != 0:
            print(c(err or out or "systemctl --user daemon-reload failed", RED))
            pause()
            return
    else:
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

        code, out, err = sudo_cmd(["systemctl", "daemon-reload"], timeout=30)
        if code != 0:
            print(c(err or out or "systemctl daemon-reload failed", RED))
            pause()
            return

    if autostart:
        if service_scope == "user":
            code, out, err = run_cmd(["systemctl", "--user", "enable", service], timeout=30)
        else:
            code, out, err = sudo_cmd(["systemctl", "enable", service], timeout=30)
        if code != 0:
            warnings.append(err or out or "Enable failed.")

    if start_now:
        if service_scope == "user":
            code, out, err = run_cmd(["systemctl", "--user", "start", service], timeout=30)
        else:
            code, out, err = sudo_cmd(["systemctl", "start", service], timeout=30)
        if code != 0:
            warnings.append(err or out or "Start failed.")

    services = load_services()

    if not any(
        s["service"] == service
        and normalize_service_scope(s.get("scope", DEFAULT_SERVICE_SCOPE)) == service_scope
        for s in services
    ):
        services.append({
            "name": project_name,
            "service": service,
            "scope": service_scope,
            "path": project_dir,
            "workdir": project_dir,
            "venv_path": venv_path,
            "python_executable": python_executable,
            "start_command": start_command or py_file,
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
        print("13 Edit service entry")
        print("14 Open URL")
        print("15 Open folder")
        print("16 Open in VS Code")
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
        elif choice == "13":
            edit_service_entry()
        elif choice == "14":
            open_url_for_service()
        elif choice == "15":
            open_folder_for_service()
        elif choice == "16":
            open_code_for_service()
        else:
            print(c("Invalid selection.", RED))
            time.sleep(0.8)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nExited.")
