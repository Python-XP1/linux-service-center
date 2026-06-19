import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import subprocess
import json
import os
import psutil
import time
import re
import shutil
import shlex
import tempfile
import threading
from urllib.parse import urlparse

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# =========================
# Modern UI Theme
# =========================
COLORS = {
    "bg": "#0b0f14",
    "panel": "#111827",
    "panel_2": "#162033",
    "card": "#151d2b",
    "row_active": "#10241c",
    "row_inactive": "#27151b",
    "row_failed": "#2a2112",
    "text": "#e5e7eb",
    "muted": "#8b98a9",
    "border": "#263244",
    "accent": "#22d3ee",
    "accent_2": "#3b82f6",
    "success": "#22c55e",
    "danger": "#f43f5e",
    "warning": "#f59e0b",
    "button": "#1f2937",
    "button_hover": "#334155",
    "button_text": "#e5e7eb",
}

FONT_MAIN = ("Arial", 11)
FONT_BOLD = ("Arial", 11, "bold")
FONT_TITLE = ("Arial", 26, "bold")
FONT_SMALL = ("Arial", 9)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "services.json")
LOGO_FILE = os.path.join(BASE_DIR, "logo.PNG")
LOGO_CANDIDATES = [
    LOGO_FILE,
    os.path.join(BASE_DIR, "logo.jpeg"),
    os.path.join(BASE_DIR, "logo.jpg"),
    os.path.join(BASE_DIR, "logo.png"),
]

APP_VERSION = "v0.9.3"
APP_NAME = "Linux Service Center"
APP_BRANDING = "powered by PythonXP"
GITHUB_URL = "https://github.com/Python-XP1"
PATREON_URL = "https://www.patreon.com/PythonXP"

COMMAND_TIMEOUT = 10

# Pixel widths for the main service table. Header and rows use the same
# grid configuration so status, startup, uptime, and actions stay aligned.
SERVICE_GRID_COLUMNS = {
    "service": 230,
    "scope": 90,
    "status": 110,
    "autostart": 110,
    "uptime": 90,
    "actions": 720,
}
ACTION_BUTTON_PADX = 2
VALID_SERVICE_SCOPES = {"system", "user"}
DEFAULT_SERVICE_SCOPE = "system"
SYSTEM_ACTION_WARNING = (
    "You are about to run a system-level action. "
    "This may affect your operating system or critical services. Continue?"
)
PERMISSION_REQUIRED_MESSAGE = "Permission required or action cancelled."

SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")
USER_NAME_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.-]*[$]?|[0-9]+)$")

# Keep diagnostics generic: avoid hard-coded optional remote-access services.
DIAGNOSTIC_COMMANDS = [
    ("hostname -I", ["hostname", "-I"]),
    ("uptime -p", ["uptime", "-p"]),
    ("who -b", ["who", "-b"]),
    ("ss -tulpen", ["ss", "-tulpen"]),
    ("ip addr", ["ip", "addr"]),
    ("systemctl --failed --no-pager", ["systemctl", "--failed", "--no-pager"]),
    ("systemctl list-units --type=service --state=running --no-pager", ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"]),
]
search_var = None
service_count_label = None
last_config_error = None
last_runtime_errors = set()
refresh_generation = 0
refresh_running = False
refresh_pending = False


def create_button(parent, text=None, command=None, width=None, variant="default", **kwargs):
    """Create a flatter, darker Tk button with hover feedback."""
    bg = COLORS["button"]
    fg = COLORS["button_text"]
    active_bg = COLORS["button_hover"]

    if variant == "success":
        bg = "#14532d"
        active_bg = "#166534"
    elif variant == "danger":
        bg = "#7f1d1d"
        active_bg = "#991b1b"
    elif variant == "warning":
        bg = "#78350f"
        active_bg = "#92400e"
    elif variant == "accent":
        bg = "#0e7490"
        active_bg = "#0891b2"
    elif variant == "muted":
        bg = "#111827"
        active_bg = "#1f2937"

    button = tk.Button(
        parent,
        text=text,
        command=command,
        width=width,
        bg=bg,
        fg=fg,
        activebackground=active_bg,
        activeforeground=fg,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        cursor="hand2",
        font=FONT_BOLD,
        padx=8,
        pady=5,
        **kwargs
    )

    def on_enter(_event):
        button.configure(bg=active_bg)

    def on_leave(_event):
        button.configure(bg=bg)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
    return button


def create_entry(parent, **kwargs):
    """Create a dark themed input field."""
    entry = tk.Entry(
        parent,
        bg="#0f172a",
        fg=COLORS["text"],
        insertbackground=COLORS["accent"],
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        font=FONT_MAIN,
        **kwargs
    )
    return entry


def create_listbox(parent, **kwargs):
    """Create a dark themed listbox."""
    listbox = tk.Listbox(
        parent,
        bg="#0f172a",
        fg=COLORS["text"],
        selectbackground=COLORS["accent_2"],
        selectforeground="#ffffff",
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        font=FONT_MAIN,
        **kwargs
    )
    return listbox

def create_link_label(parent, text, command):
    """Create a small footer link label."""
    label = tk.Label(
        parent,
        text=text,
        fg=COLORS["accent"],
        bg=COLORS["bg"],
        font=("Arial", 9, "bold"),
        cursor="hand2"
    )

    def on_enter(_event):
        label.configure(fg="#67e8f9")

    def on_leave(_event):
        label.configure(fg=COLORS["accent"])

    label.bind("<Button-1>", lambda _event: command())
    label.bind("<Enter>", on_enter)
    label.bind("<Leave>", on_leave)
    return label


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, event=None):
        if self.window or not self.text:
            return

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")

        tk.Label(
            self.window,
            text=self.text,
            bg="#020617",
            fg=COLORS["text"],
            relief=tk.SOLID,
            bd=1,
            padx=8,
            pady=4,
            font=FONT_SMALL
        ).pack()

    def hide(self, event=None):
        if self.window:
            self.window.destroy()
            self.window = None


def add_tooltip(widget, text):
    ToolTip(widget, text)
    return widget


def format_service_summary(services):
    active = 0
    inactive = 0
    failed = 0

    for item in services:
        status = get_status(item.get("service", ""), item.get("scope", DEFAULT_SERVICE_SCOPE))
        if status == "active":
            active += 1
        elif status == "failed":
            failed += 1
        else:
            inactive += 1

    return f"{len(services)} services · {active} active · {inactive} inactive · {failed} failed"


def uptime_color(uptime):
    if not uptime or uptime == "-":
        return COLORS["muted"]
    if uptime.endswith("d"):
        return COLORS["success"]
    if uptime.endswith("h"):
        return COLORS["accent_2"]
    if uptime.endswith("m"):
        return COLORS["warning"]
    return COLORS["muted"]


def load_services():
    global last_config_error

    if not os.path.exists(CONFIG_FILE):
        return []

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        report_config_error(f"{CONFIG_FILE} could not be read:\n{e}")
        return []

    if not isinstance(data, list):
        report_config_error("services.json must contain a list of services.")
        return []

    last_config_error = None
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
    fd, tmp_path = tempfile.mkstemp(prefix=".services.", suffix=".json", dir=directory)

    try:
        # Write through a temporary file so a failed save does not corrupt
        # the existing services.json.
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(services, f, indent=4, ensure_ascii=False)
            f.write("\n")

        os.replace(tmp_path, CONFIG_FILE)

    except OSError as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        show_error("Save failed", str(e))
        return False

    return True


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT
        )
        return result.stdout.strip(), result.stderr.strip()

    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {COMMAND_TIMEOUT}s: {' '.join(cmd)}"

    except Exception as e:
        return "", str(e)


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
    errors = []
    for command in commands:
        out, err = run_cmd(command)
        if out:
            services.update(parse_systemd_service_names(out))
        elif err:
            errors.append(err)
    return services, errors


def detect_service_scope(service):
    service = normalize_service_filename(service)
    if not is_valid_service_name(service):
        return DEFAULT_SERVICE_SCOPE, False, False

    system_services, _ = collect_systemd_services("system")
    user_services, _ = collect_systemd_services("user")
    found_system = service in system_services
    found_user = service in user_services

    if found_system and not found_user:
        return "system", True, False
    if found_user and not found_system:
        return "user", False, True
    return None, found_system, found_user


def list_services_with_scopes():
    system_services, _ = collect_systemd_services("system")
    user_services, _ = collect_systemd_services("user")
    entries = []

    for service in sorted(system_services):
        entries.append((service, "system", f"[SYSTEM] {service}"))
    for service in sorted(user_services):
        entries.append((service, "user", f"[USER] {service}"))

    return entries


def show_error(title, message):
    try:
        if tk._default_root:
            messagebox.showerror(title, message)
    except tk.TclError:
        pass

    print(f"{title}: {message}")


def report_config_error(message):
    global last_config_error

    if message == last_config_error:
        return

    last_config_error = message
    show_error("Invalid configuration", message)


def report_runtime_error(key, title, message):
    if key in last_runtime_errors:
        return

    last_runtime_errors.add(key)
    show_error(title, message)


def normalize_service_scope(scope):
    scope = str(scope or DEFAULT_SERVICE_SCOPE).strip().lower()
    return scope if scope in VALID_SERVICE_SCOPES else DEFAULT_SERVICE_SCOPE


def is_user_service_not_found(scope, message):
    lowered = str(message or "").lower()
    return scope == "user" and any(
        token in lowered
        for token in ["could not be found", "not-found", "not found", "unit "]
    )


def is_permission_error(message):
    lowered = str(message or "").lower()
    return any(
        token in lowered
        for token in ["password", "authentication", "interactive authentication", "not permitted", "permission denied", "cancelled", "canceled"]
    )


def is_valid_service_name(service):
    return bool(service and SERVICE_NAME_RE.fullmatch(service) and not service.startswith("-"))


def is_valid_user_name(user_name):
    return bool(user_name and USER_NAME_RE.fullmatch(user_name))


def is_valid_url(url):
    if not url:
        return True

    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_path(path):
    if not path:
        return ""

    return os.path.abspath(os.path.expanduser(path))


def resolve_venv_python(venv_path):
    if not venv_path:
        return ""
    return os.path.join(venv_path, "bin", "python")


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

    if python_executable:
        return f"{systemd_quote_arg(python_executable)} {systemd_quote_arg(script_path)}"

    python_cmd = shutil.which("python3") or "/usr/bin/python3"
    return f"{systemd_quote_arg(python_cmd)} {systemd_quote_arg(script_path)}"


def validate_service_config(item):
    item["scope"] = normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))

    if not item["name"] or not item["service"]:
        return "Display name and systemd service are required."

    if not is_valid_service_name(item["service"]):
        return "The systemd service must look like a valid .service name, e.g. ssh.service."

    if item["url"] and not is_valid_url(item["url"]):
        return "The URL must start with http:// or https://."

    if item["path"]:
        item["path"] = normalize_path(item["path"])

    if item.get("workdir"):
        item["workdir"] = normalize_path(item["workdir"])
        if not os.path.isdir(item["workdir"]):
            return "The working directory does not exist."

    if item.get("venv_path"):
        item["venv_path"] = normalize_path(item["venv_path"])
        venv_python = resolve_venv_python(item["venv_path"])
        if not os.path.isfile(venv_python):
            return f"The virtualenv Python executable was not found: {venv_python}"

    if item.get("python_executable"):
        item["python_executable"] = normalize_path(item["python_executable"])
        if not os.path.isfile(item["python_executable"]):
            return "The Python executable does not exist."

    if item.get("start_command") and has_line_break(item["start_command"]):
        return "The start command must not contain line breaks."

    return None


def run_background(task, on_done=None):
    """Run blocking work off the Tk main loop and marshal results back safely."""
    def worker():
        try:
            result = task()
        except Exception as e:
            result = e

        if on_done:
            try:
                root.after(0, lambda: on_done(result))
            except tk.TclError:
                pass

    threading.Thread(target=worker, daemon=True).start()


def invalidate_refresh():
    global refresh_generation
    refresh_generation += 1


def run_systemctl_command(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30
    )
    message = result.stderr.strip() or result.stdout.strip()
    return result.returncode == 0, message


def needs_authentication(message):
    lowered = message.lower()
    return (
        "password" in lowered
        or "authentication" in lowered
        or "interactive authentication" in lowered
        or "not permitted" in lowered
    )


def systemctl_read_command(scope, action, service):
    cmd = ["systemctl"]
    if normalize_service_scope(scope) == "user":
        cmd.append("--user")
    return cmd + [action, service]


def journalctl_command(scope, service):
    if normalize_service_scope(scope) == "user":
        return ["journalctl", "--user-unit", service, "-n", "120", "--no-pager"]
    return ["journalctl", "-u", service, "-n", "120", "--no-pager"]


def systemctl_action_command(scope, action, service):
    return systemctl_read_command(scope, action, service)


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

        pkexec_cmd = shutil.which("pkexec")
        if pkexec_cmd:
            ok, message = run_systemctl_command([pkexec_cmd] + base_cmd)
            if ok:
                return True, message
            if is_permission_error(message) or not message:
                return False, PERMISSION_REQUIRED_MESSAGE
        else:
            message = ""

        ok, sudo_message = run_systemctl_command(["sudo"] + base_cmd)
        if ok:
            return True, sudo_message

        message = sudo_message or message
        if is_permission_error(message) or not message:
            return False, PERMISSION_REQUIRED_MESSAGE
        return False, message

    except subprocess.TimeoutExpired:
        if scope == "system":
            pkexec_cmd = shutil.which("pkexec")
            if pkexec_cmd:
                try:
                    return run_systemctl_command([pkexec_cmd] + systemctl_action_command(scope, action, service))
                except (subprocess.TimeoutExpired, OSError):
                    pass
            return False, PERMISSION_REQUIRED_MESSAGE
        return False, "systemctl did not respond within 30 seconds."

    except OSError as e:
        return False, str(e)


def run_diagnostic_command(command, timeout=15):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s."
    except OSError as e:
        return 1, "", str(e)


def format_command_result(label, code, stdout, stderr):
    parts = [f"$ {label}"]
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(stderr)
    if code != 0:
        parts.append(f"[Exit {code}]")
    parts.append("")
    return "\n".join(parts)


def get_status(service, scope=DEFAULT_SERVICE_SCOPE):
    if not is_valid_service_name(service):
        return "invalid"

    out, err = run_cmd(systemctl_read_command(scope, "status", service) + ["--no-pager"])
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
    return "unknown"


def get_enabled_status(service, scope=DEFAULT_SERVICE_SCOPE):
    if not is_valid_service_name(service):
        return "invalid"

    out, err = run_cmd(systemctl_read_command(scope, "is-enabled", service))
    message = err or out
    if is_user_service_not_found(normalize_service_scope(scope), message):
        return "not-found"
    return out if out else "unknown"


def get_uptime(service, scope=DEFAULT_SERVICE_SCOPE):
    if not is_valid_service_name(service) or get_status(service, scope) != "active":
        return "-"

    out, _ = run_cmd(systemctl_read_command(scope, "show", service) + [
        "--property=ActiveEnterTimestamp",
        "--value"
    ])

    if not out:
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


def get_cpu_usage():
    try:
        return f"{psutil.cpu_percent(interval=0.1):.1f}%"
    except (psutil.Error, OSError) as e:
        report_runtime_error("cpu", "System Info Error", f"CPU usage could not be read:\n{e}")
        return "N/A"


def get_ram_usage():
    try:
        return f"{psutil.virtual_memory().percent:.1f}%"
    except (psutil.Error, OSError) as e:
        report_runtime_error("ram", "System Info Error", f"RAM usage could not be read:\n{e}")
        return "N/A"


def get_temperature():
    if not shutil.which("vcgencmd"):
        return "N/A"

    out, _ = run_cmd(["vcgencmd", "measure_temp"])

    try:
        return out.split("=")[1]
    except IndexError:
        return "N/A"


def get_disk_free():
    try:
        disk = psutil.disk_usage("/")
        return f"{disk.free / (1024 ** 3):.1f} GB"
    except (psutil.Error, OSError) as e:
        report_runtime_error("disk", "System Info Error", f"Free disk space could not be read:\n{e}")
        return "N/A"


def control_service(action, service, scope=DEFAULT_SERVICE_SCOPE):
    scope = normalize_service_scope(scope)
    if action not in {"start", "stop", "restart"} or not is_valid_service_name(service):
        messagebox.showerror("Invalid action", "Service or action is invalid.")
        return

    if scope == "system" and not messagebox.askyesno("System-level action", SYSTEM_ACTION_WARNING):
        return

    invalidate_refresh()
    action_labels = {
        "start": "Start",
        "stop": "Stop",
        "restart": "Restart",
    }

    if service_count_label:
        service_count_label.config(text=f"{action_labels[action]} running for {service}...")

    def task():
        return run_systemctl_action(action, service, scope)

    def done(result):
        if isinstance(result, Exception):
            messagebox.showerror("systemctl Error", str(result))
        elif not result[0]:
            messagebox.showerror("systemctl Error", result[1] or "Action failed.")
        elif service_count_label:
            service_count_label.config(text=f"{action_labels[action]} completed for {service}. Checking status...")

        refresh_services()

    run_background(task, done)


def show_diagnostics_window():
    win = tk.Toplevel(root)
    win.title("Diagnostics")
    win.geometry("980x620")
    win.configure(bg=COLORS["bg"])

    text_box = scrolledtext.ScrolledText(
        win,
        wrap=tk.WORD,
        bg="#0f172a",
        fg=COLORS["text"],
        insertbackground=COLORS["accent"],
        selectbackground=COLORS["accent_2"],
        selectforeground="#ffffff",
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        font=("Courier", 10),
        padx=8,
        pady=8
    )
    text_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 6))

    button_row = tk.Frame(win, bg=COLORS["bg"])
    button_row.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 10))

    buttons = []

    def append_text(value):
        text_box.config(state=tk.NORMAL)
        text_box.insert(tk.END, value)
        text_box.see(tk.END)
        text_box.config(state=tk.DISABLED)

    def clear_text():
        text_box.config(state=tk.NORMAL)
        text_box.delete("1.0", tk.END)
        text_box.config(state=tk.DISABLED)

    def set_buttons_enabled(enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in buttons:
            button.config(state=state)

    def finish_diagnostics(text):
        append_text(text)
        set_buttons_enabled(True)

    def run_diagnostics():
        clear_text()
        append_text("Diagnosis running...\nPlease wait...\n\n")
        set_buttons_enabled(False)

        def task():
            # Collect output in the worker thread and update Tk only once from
            # the main thread.
            output = [
                "Note: Diagnostics show general system information and running systemd services.\n\n"
            ]
            for label, command in DIAGNOSTIC_COMMANDS:
                try:
                    code, stdout, stderr = run_diagnostic_command(command, timeout=15)
                    output.append(format_command_result(label, code, stdout, stderr))
                except Exception as e:
                    output.append(f"$ {label}\nERROR: {e}\n\n")
            output.append("Diagnostics completed successfully\n")

            try:
                root.after(0, lambda text="".join(output): finish_diagnostics(text))
            except tk.TclError as e:
                print(f"Diagnostics window error: {e}")

        threading.Thread(target=task, daemon=True).start()

    buttons.append(create_button(button_row, text="Reload diagnostics", width=18, command=run_diagnostics, variant="accent"))
    buttons[-1].pack(side=tk.LEFT, padx=(0, 6))

    text_box.config(state=tk.DISABLED)
    run_diagnostics()


def control_autostart(action, service, scope=DEFAULT_SERVICE_SCOPE):
    scope = normalize_service_scope(scope)
    if action not in {"enable", "disable"} or not is_valid_service_name(service):
        messagebox.showerror("Invalid action", "Service or action is invalid.")
        return

    if scope == "system" and not messagebox.askyesno("System-level action", SYSTEM_ACTION_WARNING):
        return

    invalidate_refresh()
    if service_count_label:
        service_count_label.config(text=f"Startup {action} running for {service}...")

    def task():
        return run_systemctl_action(action, service, scope)

    def done(result):
        if isinstance(result, Exception):
            messagebox.showerror("systemctl Error", str(result))
        elif not result[0]:
            messagebox.showerror("systemctl Error", result[1] or "Action failed.")

        refresh_services()

    run_background(task, done)


def open_external_link(url):
    if url and is_valid_url(url):
        subprocess.Popen(["xdg-open", url])
    else:
        messagebox.showwarning("Invalid link", "The configured link is invalid.")


def open_url(url):
    if url and is_valid_url(url):
        try:
            subprocess.Popen(["xdg-open", url])
            return
        except OSError as e:
            messagebox.showerror("Open URL failed", str(e))
            return

    messagebox.showwarning("Invalid URL", "No valid http(s) URL is configured.")


def open_folder(path):
    safe_path = normalize_path(path)

    if safe_path and os.path.isdir(safe_path):
        try:
            subprocess.Popen(["xdg-open", safe_path])
        except OSError as e:
            messagebox.showerror("Open folder failed", str(e))
    else:
        messagebox.showwarning("Missing path", "Project folder not found.")


def open_code(path):
    safe_path = normalize_path(path)

    if not safe_path or not os.path.isdir(safe_path):
        messagebox.showwarning("Missing path", "Project folder not found.")
        return

    try:
        code_cmd = shutil.which("code")

        if not code_cmd:
            messagebox.showerror(
                "VS Code Error",
                "VS Code was not found."
            )
            return

        subprocess.Popen(
            [code_cmd, safe_path],
            cwd=safe_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

    except Exception as e:
        messagebox.showerror("VS Code Error", str(e))


def show_logs(service, scope=DEFAULT_SERVICE_SCOPE):
    scope = normalize_service_scope(scope)
    if not is_valid_service_name(service):
        messagebox.showerror("Invalid service", "The service name is invalid.")
        return

    out, err = run_cmd(journalctl_command(scope, service))

    win = tk.Toplevel(root)
    win.title(f"Logs: [{scope.upper()}] {service}")
    win.geometry("950x540")
    win.configure(bg=COLORS["bg"])

    text = scrolledtext.ScrolledText(
        win,
        wrap=tk.WORD,
        bg="#0f0f0f",
        fg=COLORS["text"],
        insertbackground="white"
    )
    text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    if scope == "user" and is_user_service_not_found(scope, err or out):
        text.insert(tk.END, f"User service not found: {service}")
    else:
        text.insert(tk.END, out if out else err)
    text.config(state=tk.DISABLED)


def browse_services(target_entry, scope_var=None):
    win = tk.Toplevel(root)
    win.title("Browse systemd services")
    win.geometry("760x540")
    win.configure(bg=COLORS["bg"])

    tk.Label(
        win,
        text="Double-click a service to select it",
        fg="white",
        bg=COLORS["bg"],
        font=("Arial", 11, "bold")
    ).pack(pady=10)

    tk.Label(
        win,
        text="Search service",
        fg=COLORS["text"],
        bg=COLORS["bg"],
        font=FONT_BOLD
    ).pack(anchor="w", padx=10)

    search_entry = create_entry(win, width=70)
    search_entry.pack(fill=tk.X, padx=10, pady=(3, 0))
    search_entry.insert(0, "Search service...")

    tk.Label(
        win,
        text="System and user services are listed together with their scope.",
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=FONT_SMALL
    ).pack(anchor="w", padx=10, pady=(2, 8))

    list_frame = tk.Frame(win, bg=COLORS["bg"])
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
    listbox = create_listbox(list_frame, width=90)
    listbox.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    entries = list_services_with_scopes()
    label_to_entry = {label: (service, scope) for service, scope, label in entries}

    if not entries:
        listbox.insert(tk.END, "No systemd services found.")

    def fill_list(filter_text=""):
        listbox.delete(0, tk.END)
        lowered = filter_text.lower()
        for service, scope, label in entries:
            if lowered in service.lower() or lowered in scope:
                listbox.insert(tk.END, label)

    def select_service(event=None):
        selection = listbox.curselection()
        if not selection:
            return

        label = listbox.get(selection[0])
        if label not in label_to_entry:
            return

        service, scope = label_to_entry[label]
        target_entry.delete(0, tk.END)
        target_entry.insert(0, service)
        if scope_var is not None:
            scope_var.set(scope)
        win.destroy()

    def get_search_text():
        value = search_entry.get()
        return "" if value == "Search service..." else value

    def clear_placeholder(event=None):
        if search_entry.get() == "Search service...":
            search_entry.delete(0, tk.END)

    search_entry.bind("<FocusIn>", clear_placeholder)
    search_entry.bind("<KeyRelease>", lambda e: fill_list(get_search_text()))
    listbox.bind("<Double-Button-1>", select_service)

    create_button(win, text="Apply", command=select_service).pack(pady=10)
    fill_list()



def project_form(title_text, existing=None, index=None):
    win = tk.Toplevel(root)
    win.title(title_text)
    win.geometry("640x690")
    win.minsize(560, 520)
    win.configure(bg=COLORS["bg"])

    outer = tk.Frame(win, bg=COLORS["bg"])
    outer.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(outer, bg=COLORS["bg"], highlightthickness=0, bd=0)
    scrollbar = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    content = tk.Frame(canvas, bg=COLORS["bg"])
    content_window = canvas.create_window((0, 0), window=content, anchor="nw")

    def update_scroll_region(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(content_window, width=canvas.winfo_width())

    content.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", update_scroll_region)

    def on_mousewheel(event):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def bind_mousewheel(event=None):
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel)
        canvas.bind_all("<Button-5>", on_mousewheel)

    def unbind_mousewheel(event=None):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", bind_mousewheel)
    canvas.bind("<Leave>", unbind_mousewheel)
    content.bind("<Enter>", bind_mousewheel)
    content.bind("<Leave>", unbind_mousewheel)

    def close_window():
        nonlocal detection_after_id
        if detection_after_id:
            try:
                win.after_cancel(detection_after_id)
            except tk.TclError:
                pass
            detection_after_id = None
        unbind_mousewheel()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close_window)

    fields = {}
    detection_after_id = None
    last_detection_notice = {"service": "", "kind": ""}

    def add_form_field(key, label, value="", hint=""):
        tk.Label(content, text=label, fg="white", bg=COLORS["bg"]).pack(anchor="w", padx=20, pady=(8, 0))
        entry = create_entry(content, width=70)
        entry.pack(padx=20, pady=3, fill=tk.X)
        if value:
            entry.insert(0, value)
        if hint:
            tk.Label(content, text=hint, fg=COLORS["muted"], bg=COLORS["bg"], font=("Arial", 9)).pack(anchor="w", padx=20)
        fields[key] = entry
        return entry

    add_form_field("name", "Display name", existing.get("name", "") if existing else "")
    service_entry = add_form_field("service", "Systemd Service", existing.get("service", "") if existing else "")

    tk.Label(content, text="Scope", fg="white", bg=COLORS["bg"]).pack(anchor="w", padx=20, pady=(8, 0))
    scope_var = tk.StringVar(value=normalize_service_scope(existing.get("scope", DEFAULT_SERVICE_SCOPE) if existing else DEFAULT_SERVICE_SCOPE))
    scope_menu = tk.OptionMenu(content, scope_var, "system", "user")
    scope_menu.configure(bg=COLORS["button"], fg=COLORS["text"], activebackground=COLORS["button_hover"], activeforeground=COLORS["text"], relief=tk.FLAT, highlightthickness=0)
    scope_menu["menu"].configure(bg=COLORS["button"], fg=COLORS["text"])
    scope_menu.pack(anchor="w", padx=20, pady=3)
    tk.Label(
        content,
        text=(
            "Scope is detected by where the service is registered:\n"
            "System = /etc/systemd/system or system-wide systemd\n"
            "User = ~/.config/systemd/user or systemctl --user\n"
            "Your own projects can still be system services if they were installed system-wide."
        ),
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=("Arial", 9),
        justify="left",
        wraplength=560
    ).pack(anchor="w", padx=20)

    tk.Label(
        content,
        text="Example: ssh.service, bluetooth.service, nginx.service",
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=("Arial", 9)
    ).pack(anchor="w", padx=20)

    def show_detection_notice(service, kind, message, level="info"):
        if last_detection_notice["service"] == service and last_detection_notice["kind"] == kind:
            return
        last_detection_notice["service"] = service
        last_detection_notice["kind"] = kind
        if level == "warning":
            messagebox.showwarning("Scope detection", message)
        else:
            messagebox.showinfo("Scope detection", message)

    def looks_like_personal_project_service(service):
        name_value = fields["name"].get().strip().lower()
        service_base = service.rsplit(".service", 1)[0].lower()
        if name_value and name_value not in {"system", "service"}:
            normalized_name = re.sub(r"[^a-z0-9]+", "-", name_value).strip("-")
            if normalized_name and normalized_name in service_base:
                return True
        return any(token in service_base for token in ["app", "web", "project", "tool", "api", "flask", "django"])

    def detect_and_apply_scope(show_not_found=False):
        service = normalize_service_filename(service_entry.get().strip())
        if not service or not is_valid_service_name(service):
            return

        detected_scope, found_system, found_user = detect_service_scope(service)
        if found_system and found_user:
            show_detection_notice(
                service,
                "both",
                "This service exists as both system and user service. Please choose the correct scope.",
                "warning"
            )
            return
        if detected_scope:
            scope_var.set(detected_scope)
            if detected_scope == "system" and looks_like_personal_project_service(service):
                show_detection_notice(
                    service,
                    "personal-system",
                    "This service is registered as a system service. If you want it to run as a user service, create it under ~/.config/systemd/user and use systemctl --user.",
                    "warning"
                )
            return
        if show_not_found:
            show_detection_notice(
                service,
                "not-found",
                "Service not found. Please select the correct scope manually.",
                "warning"
            )

    def schedule_scope_detection(event=None):
        nonlocal detection_after_id
        if detection_after_id:
            win.after_cancel(detection_after_id)
        detection_after_id = win.after(650, lambda: detect_and_apply_scope(False))

    service_entry.bind("<KeyRelease>", schedule_scope_detection)
    service_entry.bind("<FocusOut>", lambda event: detect_and_apply_scope(True))
    service_entry.bind("<Return>", lambda event: detect_and_apply_scope(True))

    create_button(
        content,
        text="Browse services",
        width=22,
        command=lambda: browse_services(fields["service"], scope_var)
    ).pack(pady=6)

    add_form_field("path", "Folder/path optional", existing.get("path", "") if existing else "")
    add_form_field(
        "workdir",
        "Working directory optional",
        existing.get("workdir", "") if existing else "",
        "Used as WorkingDirectory= when a systemd service is generated."
    )
    add_form_field(
        "venv_path",
        "Virtualenv path optional",
        existing.get("venv_path", "") if existing else "",
        "Example: /path/to/project/.venv"
    )
    add_form_field(
        "python_executable",
        "Python executable optional",
        existing.get("python_executable", "") if existing else "",
        "Example: /path/to/project/.venv/bin/python"
    )
    add_form_field(
        "start_command",
        "Start command optional",
        existing.get("start_command", "") if existing else "",
        "Example: app.py or python app.py"
    )
    add_form_field("url", "URL optional", existing.get("url", "") if existing else "")

    button_bar = tk.Frame(win, bg=COLORS["panel"], padx=16, pady=12)
    button_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def save_project():
        services = load_services()
        path = fields["path"].get().strip()
        workdir = fields["workdir"].get().strip()

        item = {
            "name": fields["name"].get().strip(),
            "service": fields["service"].get().strip(),
            "scope": normalize_service_scope(scope_var.get()),
            "path": path or workdir,
            "workdir": workdir,
            "venv_path": fields["venv_path"].get().strip(),
            "python_executable": fields["python_executable"].get().strip(),
            "start_command": fields["start_command"].get().strip(),
            "url": fields["url"].get().strip()
        }

        validation_error = validate_service_config(item)

        if validation_error:
            messagebox.showwarning("Check input", validation_error)
            return

        if index is None:
            services.append(item)
        elif 0 <= index < len(services):
            services[index] = item
        else:
            messagebox.showerror("Save failed", "The selected service no longer exists.")
            return

        if not save_services(services):
            return

        refresh_services()
        close_window()

    create_button(button_bar, text="Cancel", width=12, command=close_window, variant="muted").pack(side=tk.RIGHT, padx=6)
    create_button(button_bar, text="Save", width=18, command=save_project, variant="success").pack(side=tk.RIGHT, padx=6)



def normalize_service_filename(name):
    """Normalize user input to a safe systemd .service filename."""
    service = name.strip()
    if service and not service.endswith(".service"):
        service += ".service"
    return service


def systemd_quote_arg(value):
    """Quote a systemd ExecStart argument, preserving paths with spaces."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def has_line_break(value):
    return "\n" in value or "\r" in value


def build_service_unit(description, command, working_dir, user_name, restart_policy, install_target="multi-user.target"):
    """Build the text content of a simple systemd service file."""
    lines = [
        "[Unit]",
        f"Description={description}",
        "After=network.target",
        "",
        "[Service]",
        "Type=simple",
    ]

    if user_name:
        lines.append(f"User={user_name}")

    if working_dir:
        lines.append(f"WorkingDirectory={working_dir}")

    lines.extend([
        f"ExecStart={command}",
        f"Restart={restart_policy}",
        "RestartSec=5",
        "",
        "[Install]",
        f"WantedBy={install_target}",
        ""
    ])

    return "\n".join(lines)


def write_systemd_service(service_name, unit_text):
    """Write a service file into /etc/systemd/system using sudo tee."""
    if not is_valid_service_name(service_name):
        return False, "Invalid service name. Example: my-project.service"

    service_path = f"/etc/systemd/system/{service_name}"

    try:
        result = subprocess.run(
            ["sudo", "tee", service_path],
            input=unit_text,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return False, result.stderr.strip() or "Service file could not be written."

        chmod_result = subprocess.run(
            ["sudo", "chmod", "644", service_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if chmod_result.returncode != 0:
            return False, chmod_result.stderr.strip() or "Permissions could not be set."

        reload_result = subprocess.run(
            ["sudo", "systemctl", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if reload_result.returncode != 0:
            return False, reload_result.stderr.strip() or "daemon-reload failed."

        return True, f"Service created: {service_path}"

    except subprocess.TimeoutExpired:
        return False, "Write operation timed out."
    except OSError as e:
        return False, str(e)


def user_systemd_service_dir():
    return os.path.join(os.path.expanduser("~"), ".config", "systemd", "user")


def user_systemd_service_path(service_name):
    return os.path.join(user_systemd_service_dir(), service_name)


def write_user_systemd_service(service_name, unit_text):
    """Write a user-level systemd service without administrator privileges."""
    if not is_valid_service_name(service_name):
        return False, "Invalid service name. Example: my-project.service"

    service_dir = user_systemd_service_dir()
    service_path = user_systemd_service_path(service_name)

    try:
        os.makedirs(service_dir, exist_ok=True)
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(unit_text)

        chmod_result = subprocess.run(
            ["chmod", "644", service_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        if chmod_result.returncode != 0:
            return False, chmod_result.stderr.strip() or "Permissions could not be set."

        reload_result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if reload_result.returncode != 0:
            return False, reload_result.stderr.strip() or "user daemon-reload failed."

        return True, f"User service created: {service_path}"

    except subprocess.TimeoutExpired:
        return False, "Write operation timed out."
    except OSError as e:
        return False, str(e)


def service_assistant_window():
    """Simple assistant that creates a real systemd .service file and adds it to the panel."""
    win = tk.Toplevel(root)
    win.title("+ Service Assistant")
    win.geometry("760x620")
    win.minsize(720, 560)
    win.configure(bg=COLORS["bg"])

    outer = tk.Frame(win, bg=COLORS["bg"])
    outer.pack(fill=tk.BOTH, expand=True)

    # Scrollable content area: the button bar remains visible at the bottom,
    # even in small windows or when advanced settings are open.
    scroll_area = tk.Frame(outer, bg=COLORS["bg"])
    scroll_area.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(
        scroll_area,
        bg=COLORS["bg"],
        highlightthickness=0,
        bd=0
    )
    scrollbar = tk.Scrollbar(scroll_area, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    content = tk.Frame(canvas, bg=COLORS["bg"])
    content_window = canvas.create_window((0, 0), window=content, anchor="nw")

    def update_scroll_region(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(content_window, width=canvas.winfo_width())

    def on_mousewheel(event):
        # Linux/X11 sends Button-4/Button-5, Windows/macOS usually MouseWheel.
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    mousewheel_bound = False

    def bind_mousewheel(event=None):
        nonlocal mousewheel_bound
        if mousewheel_bound:
            return
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel)
        canvas.bind_all("<Button-5>", on_mousewheel)
        mousewheel_bound = True

    def pointer_is_over_scroll_area():
        try:
            pointer_x = canvas.winfo_pointerx() - canvas.winfo_rootx()
            pointer_y = canvas.winfo_pointery() - canvas.winfo_rooty()
            return 0 <= pointer_x < canvas.winfo_width() and 0 <= pointer_y < canvas.winfo_height()
        except tk.TclError:
            return False

    def unbind_mousewheel(event=None, force=False):
        nonlocal mousewheel_bound
        if not mousewheel_bound:
            return
        if not force and pointer_is_over_scroll_area():
            return
        try:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        except tk.TclError:
            pass
        mousewheel_bound = False

    def unbind_mousewheel_if_outside(event=None):
        try:
            canvas.after(50, unbind_mousewheel)
        except tk.TclError:
            pass

    content.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", update_scroll_region)
    canvas.bind("<Enter>", bind_mousewheel)
    canvas.bind("<Leave>", unbind_mousewheel_if_outside)
    canvas.bind("<FocusIn>", bind_mousewheel)
    canvas.bind("<FocusOut>", unbind_mousewheel_if_outside)
    content.bind("<Enter>", bind_mousewheel)
    content.bind("<Leave>", unbind_mousewheel_if_outside)
    content.bind("<FocusIn>", bind_mousewheel)
    content.bind("<FocusOut>", unbind_mousewheel_if_outside)

    def close_assistant():
        unbind_mousewheel(force=True)

        try:
            win.destroy()
        except tk.TclError:
            pass

    win.protocol("WM_DELETE_WINDOW", close_assistant)

    content_inner = tk.Frame(content, bg=COLORS["bg"])
    content_inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=(18, 8))
    content_inner.bind("<Enter>", bind_mousewheel)
    content_inner.bind("<Leave>", unbind_mousewheel_if_outside)
    content_inner.bind("<FocusIn>", bind_mousewheel)
    content_inner.bind("<FocusOut>", unbind_mousewheel_if_outside)
    content = content_inner

    tk.Label(
        content,
        text="Service Assistant",
        fg=COLORS["text"],
        bg=COLORS["bg"],
        font=("Arial", 18, "bold")
    ).pack(anchor="w")

    tk.Label(
        content,
        text="Simple mode: choose a project folder, enter a Python file, and create the service. Virtualenv and advanced fields are optional.",
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=FONT_MAIN,
        wraplength=680,
        justify="left"
    ).pack(anchor="w", pady=(2, 14))

    fields = {}

    def add_field(parent, key, label, hint="", default="", width=70):
        tk.Label(parent, text=label, fg=COLORS["text"], bg=COLORS["bg"], font=FONT_BOLD).pack(anchor="w", pady=(8, 0))
        entry = create_entry(parent, width=width)
        entry.pack(anchor="w", pady=(3, 0), fill=tk.X)
        if default:
            entry.insert(0, default)
        if hint:
            tk.Label(parent, text=hint, fg=COLORS["muted"], bg=COLORS["bg"], font=FONT_SMALL).pack(anchor="w", pady=(2, 0))
        fields[key] = entry
        return entry

    simple_frame = tk.Frame(content, bg=COLORS["bg"])
    simple_frame.pack(fill=tk.X)

    name_entry = add_field(simple_frame, "name", "Project name", "This is how the service appears in the panel, e.g. Web App")

    tk.Label(simple_frame, text="Project folder", fg=COLORS["text"], bg=COLORS["bg"], font=FONT_BOLD).pack(anchor="w", pady=(8, 0))
    folder_row = tk.Frame(simple_frame, bg=COLORS["bg"])
    folder_row.pack(fill=tk.X, pady=(3, 0))
    workdir_entry = create_entry(folder_row, width=58)
    workdir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    fields["workdir"] = workdir_entry

    def bring_assistant_to_front():
        try:
            win.deiconify()
            win.lift()
            win.focus_force()
            win.attributes("-topmost", True)
            win.after(250, lambda: win.attributes("-topmost", False))
        except tk.TclError:
            pass

    def choose_existing_directory(initial_dir=None):
        current_dir = normalize_path(initial_dir or os.path.expanduser("~"))
        if not os.path.isdir(current_dir):
            current_dir = os.path.expanduser("~")

        selected_path = {"value": None}
        dialog = tk.Toplevel(win)
        dialog.title("Choose project folder")
        dialog.geometry("620x460")
        dialog.minsize(520, 360)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(win)
        dialog.grab_set()

        path_var = tk.StringVar(value=current_dir)

        tk.Label(
            dialog,
            text="Choose project folder",
            fg=COLORS["text"],
            bg=COLORS["bg"],
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=14, pady=(12, 4))

        path_label = tk.Label(
            dialog,
            textvariable=path_var,
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            font=FONT_SMALL,
            anchor="w"
        )
        path_label.pack(fill=tk.X, padx=14, pady=(0, 8))

        list_frame = tk.Frame(dialog, bg=COLORS["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        listbox = create_listbox(list_frame, width=80)
        listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        button_row = tk.Frame(dialog, bg=COLORS["panel"], padx=12, pady=10)
        button_row.pack(fill=tk.X, side=tk.BOTTOM)

        def list_dirs(folder):
            nonlocal current_dir
            folder = normalize_path(folder)
            if not os.path.isdir(folder):
                return
            current_dir = folder
            path_var.set(folder)
            listbox.delete(0, tk.END)
            try:
                entries = sorted(
                    name for name in os.listdir(folder)
                    if os.path.isdir(os.path.join(folder, name)) and not name.startswith(".")
                )
            except OSError as e:
                messagebox.showwarning("Choose project folder", str(e), parent=dialog)
                entries = []
            for name in entries:
                listbox.insert(tk.END, name)

        def selected_folder_or_current():
            selection = listbox.curselection()
            if selection:
                return os.path.join(current_dir, listbox.get(selection[0]))
            return current_dir

        def enter_selected(event=None):
            folder = selected_folder_or_current()
            if os.path.isdir(folder):
                list_dirs(folder)

        def choose_selected(event=None):
            folder = selected_folder_or_current()
            if os.path.isdir(folder):
                selected_path["value"] = normalize_path(folder)
                dialog.destroy()

        def go_up():
            parent = os.path.dirname(current_dir.rstrip(os.sep)) or os.sep
            list_dirs(parent)

        listbox.bind("<Double-Button-1>", enter_selected)
        listbox.bind("<Return>", choose_selected)

        create_button(button_row, text="Cancel", width=12, command=dialog.destroy, variant="muted").pack(side=tk.RIGHT, padx=5)
        create_button(button_row, text="OK", width=12, command=choose_selected, variant="success").pack(side=tk.RIGHT, padx=5)
        create_button(button_row, text="Open", width=12, command=enter_selected, variant="accent").pack(side=tk.RIGHT, padx=5)
        create_button(button_row, text="Up", width=10, command=go_up, variant="muted").pack(side=tk.LEFT, padx=5)

        list_dirs(current_dir)
        dialog.wait_window()
        return selected_path["value"]

    def choose_folder():
        initial_dir = fields["workdir"].get().strip() or os.path.expanduser("~")
        selected = choose_existing_directory(initial_dir)
        bring_assistant_to_front()
        if not selected:
            return
        workdir_entry.delete(0, tk.END)
        workdir_entry.insert(0, selected)
        maybe_autofill_from_folder(selected)
        update_preview()

    create_button(folder_row, text="Choose folder", width=14, command=choose_folder, variant="muted").pack(side=tk.LEFT, padx=(8, 0))
    tk.Label(simple_frame, text="Example: /home/pi/my-service", fg=COLORS["muted"], bg=COLORS["bg"], font=FONT_SMALL).pack(anchor="w", pady=(2, 0))

    venv_entry = add_field(simple_frame, "venv_path", "Virtualenv path optional", "If set, the assistant uses <venv>/bin/python when possible.")
    script_entry = add_field(simple_frame, "script", "Python file", "Usually app.py or main.py. Absolute paths are also allowed.", "app.py")
    url_entry = add_field(simple_frame, "url", "URL optional", "For web apps, e.g. http://127.0.0.1:5050")

    service_type_var = tk.StringVar(value="user")
    service_type_touched = tk.BooleanVar(value=False)

    service_type_frame = tk.Frame(simple_frame, bg=COLORS["bg"])
    service_type_frame.pack(fill=tk.X, pady=(14, 0))
    tk.Label(service_type_frame, text="Service type", fg=COLORS["text"], bg=COLORS["bg"], font=FONT_BOLD).pack(anchor="w")

    def mark_service_type_touched():
        service_type_touched.set(True)
        update_preview()

    tk.Radiobutton(
        service_type_frame,
        text="User service (recommended)",
        variable=service_type_var,
        value="user",
        command=mark_service_type_touched,
        fg=COLORS["text"],
        bg=COLORS["bg"],
        activebackground=COLORS["bg"],
        activeforeground=COLORS["text"],
        selectcolor=COLORS["panel"],
        font=FONT_MAIN
    ).pack(anchor="w")
    tk.Radiobutton(
        service_type_frame,
        text="System service (advanced)",
        variable=service_type_var,
        value="system",
        command=mark_service_type_touched,
        fg=COLORS["text"],
        bg=COLORS["bg"],
        activebackground=COLORS["bg"],
        activeforeground=COLORS["text"],
        selectcolor=COLORS["panel"],
        font=FONT_MAIN
    ).pack(anchor="w")
    tk.Label(
        service_type_frame,
        text=(
            "User service:\nRuns only for your account.\nNo administrator privileges required.\n\n"
            "System service:\nRuns system-wide and requires administrator privileges."
        ),
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=FONT_SMALL,
        justify="left",
        wraplength=680
    ).pack(anchor="w", pady=(2, 0))

    options_frame = tk.Frame(simple_frame, bg=COLORS["bg"])
    options_frame.pack(anchor="w", pady=(12, 0), fill=tk.X)

    enable_var = tk.BooleanVar(value=True)
    start_var = tk.BooleanVar(value=False)
    add_panel_var = tk.BooleanVar(value=True)

    for text, var in [
        ("Enable startup", enable_var),
        ("Start service after creation", start_var),
        ("Add directly to the panel list", add_panel_var),
    ]:
        cb = tk.Checkbutton(
            options_frame,
            text=text,
            variable=var,
            fg=COLORS["text"],
            bg=COLORS["bg"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel"],
            font=FONT_MAIN
        )
        cb.pack(anchor="w")

    advanced_visible = tk.BooleanVar(value=False)
    advanced_frame = tk.Frame(content, bg=COLORS["panel"], padx=12, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])

    current_user = os.environ.get("USER", "pi")
    service_entry = add_field(advanced_frame, "service", "Service filename", "Optional. Automatically generated from the project name, e.g. web-app.service")
    user_entry = add_field(advanced_frame, "user", "Linux user", "Usually: pi", current_user)
    python_entry = add_field(advanced_frame, "python_executable", "Python executable", "Optional. Example: /path/to/project/.venv/bin/python")
    command_entry = add_field(advanced_frame, "start_command", "Start command", "Optional. Example: app.py or python app.py")

    restart_row = tk.Frame(advanced_frame, bg=COLORS["panel"])
    restart_row.pack(anchor="w", pady=(8, 0), fill=tk.X)
    tk.Label(restart_row, text="Restart behavior", fg=COLORS["text"], bg=COLORS["panel"], font=FONT_BOLD).pack(anchor="w")
    restart_var = tk.StringVar(value="always")
    restart_menu = tk.OptionMenu(restart_row, restart_var, "always", "on-failure", "no")
    restart_menu.configure(bg=COLORS["button"], fg=COLORS["text"], activebackground=COLORS["button_hover"], activeforeground=COLORS["text"], relief=tk.FLAT, highlightthickness=0)
    restart_menu["menu"].configure(bg=COLORS["button"], fg=COLORS["text"])
    restart_menu.pack(anchor="w", pady=(3, 0))

    def toggle_advanced():
        if advanced_visible.get():
            advanced_frame.pack_forget()
            advanced_visible.set(False)
            advanced_button.configure(text="Show advanced settings")
        else:
            advanced_frame.pack(fill=tk.X, pady=(12, 0))
            advanced_visible.set(True)
            advanced_button.configure(text="Hide advanced settings")

    advanced_button = create_button(content, text="Show advanced settings", width=30, command=toggle_advanced, variant="muted")
    advanced_button.pack(anchor="w", pady=(12, 0))

    preview_box = scrolledtext.ScrolledText(
        content,
        height=6,
        bg="#0f172a",
        fg=COLORS["text"],
        insertbackground=COLORS["accent"],
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        font=("Courier", 9)
    )
    preview_box.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

    button_bar = tk.Frame(outer, bg=COLORS["panel"], padx=16, pady=12)
    button_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def slugify_service_name(value):
        value = value.strip().lower()
        value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        value = re.sub(r"[^a-z0-9_.@:-]+", "-", value).strip("-_.")
        if not value:
            value = "my-project"
        return normalize_service_filename(value)

    def folder_is_inside_home(folder):
        home = normalize_path(os.path.expanduser("~"))
        folder = normalize_path(folder)
        try:
            return os.path.commonpath([home, folder]) == home
        except ValueError:
            return False

    def recommend_service_type_for_folder(folder):
        if not service_type_touched.get() and folder_is_inside_home(folder):
            service_type_var.set("user")

    def maybe_autofill_from_folder(folder):
        folder = normalize_path(folder)
        if not folder:
            return

        recommend_service_type_for_folder(folder)

        if not fields["name"].get().strip():
            fields["name"].insert(0, os.path.basename(folder.rstrip(os.sep)) or "My Project")

        candidates = ["app.py", "main.py", "server.py", "run.py"]
        for filename in candidates:
            if os.path.isfile(os.path.join(folder, filename)):
                fields["script"].delete(0, tk.END)
                fields["script"].insert(0, filename)
                break

        venv_path = os.path.join(folder, ".venv")
        venv_python = resolve_venv_python(venv_path)
        if os.path.isfile(venv_python):
            if not fields["venv_path"].get().strip():
                fields["venv_path"].insert(0, venv_path)
            if not fields["python_executable"].get().strip():
                fields["python_executable"].insert(0, venv_python)

    def resolve_script_path(workdir, script_value):
        script_value = script_value.strip()
        if not script_value:
            return ""
        if os.path.isabs(script_value):
            return normalize_path(script_value)
        return normalize_path(os.path.join(workdir, script_value))

    def collect_data():
        name = fields["name"].get().strip()
        workdir = normalize_path(fields["workdir"].get().strip())
        script_value = fields["script"].get().strip()
        script_path = resolve_script_path(workdir, script_value)
        venv_path = normalize_path(fields["venv_path"].get().strip())
        python_executable = normalize_path(fields["python_executable"].get().strip())
        start_command = fields["start_command"].get().strip()
        url = fields["url"].get().strip()
        service_name = normalize_service_filename(fields["service"].get().strip()) if fields["service"].get().strip() else slugify_service_name(name)
        user_name = fields["user"].get().strip()
        restart_policy = restart_var.get()
        service_scope = normalize_service_scope(service_type_var.get())

        if not name:
            return None, "Project name is missing."
        if any(has_line_break(value) for value in [name, workdir, script_path, venv_path, python_executable, user_name, start_command]):
            return None, "Inputs for the service file must not contain line breaks."
        if not is_valid_service_name(service_name):
            return None, "Invalid service filename. Example: my-project.service"
        if user_name and not is_valid_user_name(user_name):
            return None, "Invalid Linux user. Example: pi or root."
        if not workdir or not os.path.isdir(workdir):
            return None, "Project folder does not exist."
        if venv_path:
            venv_python = resolve_venv_python(venv_path)
            if not os.path.isfile(venv_python):
                return None, f"Virtualenv Python executable was not found: {venv_python}"
            if not python_executable:
                python_executable = venv_python
        if python_executable and not os.path.isfile(python_executable):
            return None, "Python executable does not exist."
        if not start_command and (not script_path or not os.path.isfile(script_path)):
            return None, "Python file was not found. Example: app.py or /home/pi/project/app.py"
        if url and not is_valid_url(url):
            return None, "URL must start with http:// or https://."
        command = build_python_exec_start(python_executable, start_command, script_path)
        if not command:
            return None, "Start command could not be built."

        unit_text = build_service_unit(
            description=name,
            command=command,
            working_dir=workdir,
            user_name=user_name if service_scope == "system" else "",
            restart_policy=restart_policy,
            install_target="multi-user.target" if service_scope == "system" else "default.target"
        )

        return {
            "name": name,
            "service": service_name,
            "scope": service_scope,
            "path": workdir,
            "workdir": workdir,
            "venv_path": venv_path,
            "python_executable": python_executable,
            "start_command": start_command or script_value,
            "url": url,
            "service_path": user_systemd_service_path(service_name) if service_scope == "user" else f"/etc/systemd/system/{service_name}",
            "unit_text": unit_text,
            "enable": enable_var.get(),
            "start": start_var.get(),
            "add_panel": add_panel_var.get(),
        }, None

    def update_preview(event=None):
        data, error = collect_data()
        preview_box.config(state=tk.NORMAL)
        preview_box.delete("1.0", tk.END)
        if error:
            preview_box.insert(tk.END, f"Preview is not complete yet:\n{error}")
        else:
            preview_box.insert(tk.END, f"Target: {data['service_path']}\n\n{data['unit_text']}")
        preview_box.config(state=tk.DISABLED)

    def on_workdir_changed(event=None):
        recommend_service_type_for_folder(fields["workdir"].get().strip())
        update_preview()

    for key, entry in fields.items():
        if key == "workdir":
            entry.bind("<KeyRelease>", on_workdir_changed)
            entry.bind("<FocusOut>", on_workdir_changed)
        else:
            entry.bind("<KeyRelease>", update_preview)
    restart_var.trace_add("write", lambda *_: update_preview())
    service_type_var.trace_add("write", lambda *_: update_preview())

    def create_service():
        data, error = collect_data()
        if error:
            messagebox.showwarning("Check input", error)
            return

        if data["scope"] == "user":
            if not messagebox.askyesno(
                "Create user service?",
                f"Create user service?\n\nPath:\n~/.config/systemd/user/{data['service']}"
            ):
                return
        else:
            if not messagebox.askyesno(
                "Create system service?",
                f"Create system service?\n\nPath:\n/etc/systemd/system/{data['service']}\n\nAdministrator privileges required."
            ):
                return

            if (data["enable"] or data["start"]) and not messagebox.askyesno(
                "System-level action",
                SYSTEM_ACTION_WARNING
            ):
                return

        def task():
            if data["scope"] == "user":
                ok, msg = write_user_systemd_service(data["service"], data["unit_text"])
            else:
                ok, msg = write_systemd_service(data["service"], data["unit_text"])
            if not ok:
                return False, msg

            if data["enable"]:
                ok, msg = run_systemctl_action("enable", data["service"], data["scope"])
                if not ok:
                    return False, msg

            if data["start"]:
                ok, msg = run_systemctl_action("start", data["service"], data["scope"])
                if not ok:
                    return False, msg

            if data["add_panel"]:
                services = load_services()
                item = {
                    "name": data["name"],
                    "service": data["service"],
                    "scope": data["scope"],
                    "path": data["path"],
                    "workdir": data["workdir"],
                    "venv_path": data["venv_path"],
                    "python_executable": data["python_executable"],
                    "start_command": data["start_command"],
                    "url": data["url"],
                }
                existing_index = next((i for i, s in enumerate(services) if s.get("service") == data["service"]), None)
                if existing_index is None:
                    services.append(item)
                else:
                    services[existing_index] = item
                if not save_services(services):
                    return False, "Service was created but could not be saved to services.json."

            return True, "Service was created successfully."

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror("Service Assistant", str(result))
                return
            ok, msg = result
            if ok:
                messagebox.showinfo("Service Assistant", msg)
                refresh_services()
                close_assistant()
            else:
                messagebox.showerror("Service Assistant", msg or "Creation failed.")

        run_background(task, done)

    create_button(button_bar, text="Cancel", command=close_assistant, width=12, variant="muted").pack(side=tk.RIGHT, padx=6)
    create_button(button_bar, text="Create service", command=create_service, width=20, variant="success").pack(side=tk.RIGHT, padx=6)

    update_preview()

def add_project_window():
    project_form("Add service")


def edit_service_by_index(index):
    services = load_services()

    if 0 <= index < len(services):
        project_form("Edit service", services[index], index)


def edit_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Edit service")
    win.geometry("430x270")
    win.configure(bg=COLORS["bg"])

    list_frame = tk.Frame(win, bg=COLORS["bg"])
    list_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
    scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
    listbox = create_listbox(list_frame, width=46)
    listbox.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def edit_selected(event=None):
        selection = listbox.curselection()

        if not selection:
            return

        index = selection[0]
        win.destroy()
        edit_service_by_index(index)

    listbox.bind("<Double-Button-1>", edit_selected)

    create_button(win, text="Edit", width=18, command=edit_selected).pack(pady=10)


def delete_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Remove service")
    win.geometry("430x270")
    win.configure(bg=COLORS["bg"])

    list_frame = tk.Frame(win, bg=COLORS["bg"])
    list_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
    scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
    listbox = create_listbox(list_frame, width=46)
    listbox.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def delete_selected():
        selection = listbox.curselection()

        if not selection:
            return

        index = selection[0]
        name = services[index].get("name", "Unbenannt")

        if messagebox.askyesno("Remove", f"Remove {name} from the list?"):
            try:
                services.pop(index)
            except IndexError:
                messagebox.showerror("Remove failed", "The selected service no longer exists.")
                return

            if not save_services(services):
                return

            refresh_services()
            win.destroy()

    create_button(win, text="Remove", width=18, command=delete_selected).pack(pady=10)


def create_info_card(parent, title, value, color):
    frame = tk.Frame(parent, bg=COLORS["card"], padx=20, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])
    frame.pack(side=tk.LEFT, padx=8)

    tk.Label(
        frame,
        text=title,
        fg=COLORS["muted"],
        bg=COLORS["card"],
        font=("Arial", 9, "bold")
    ).pack()

    value_label = tk.Label(
        frame,
        text=value,
        fg=color,
        bg=COLORS["card"],
        font=("Arial", 14, "bold")
    )
    value_label.pack()

    return value_label


def load_logo(parent):
    logo_path = next((p for p in LOGO_CANDIDATES if os.path.exists(p)), None)

    if not logo_path:
        return

    if Image is None or ImageTk is None:
        print("Pillow is missing. Logo will not be loaded.")
        return

    try:
        logo_img = Image.open(logo_path)
        logo_img.thumbnail((78, 78))

        logo_photo = ImageTk.PhotoImage(logo_img)

        logo_label = tk.Label(parent, image=logo_photo, bg=COLORS["bg"])
        logo_label.image = logo_photo
        logo_label.pack(side=tk.LEFT, padx=(10, 14))

    except Exception as e:
        print("Logo could not be loaded:", e)


def add_header():
    header = tk.Frame(service_frame, bg=COLORS["panel_2"])
    header.pack(fill=tk.X, padx=12, pady=(10, 5))

    columns = [
        ("Service", "service", 0),
        ("Scope", "scope", 1),
        ("Status", "status", 2),
        ("Startup", "autostart", 3),
        ("Uptime", "uptime", 4),
        ("Actions", "actions", 5),
    ]

    for text, key, index in columns:
        header.grid_columnconfigure(index, minsize=SERVICE_GRID_COLUMNS[key])
        tk.Label(
            header,
            text=text,
            fg=COLORS["text"],
            bg=COLORS["panel_2"],
            font=("Arial", 10, "bold"),
            anchor="w"
        ).grid(row=0, column=index, sticky="w", padx=8, pady=6)


def collect_service_snapshot(services, filter_text):
    rows = []
    active = 0
    inactive = 0
    failed = 0

    for index, item in enumerate(services):
        name = item.get("name", "Unbenannt")
        service = item.get("service", "")
        scope = normalize_service_scope(item.get("scope", DEFAULT_SERVICE_SCOPE))
        path = item.get("path", "")
        url = item.get("url", "")

        status = get_status(service, scope)
        enabled = get_enabled_status(service, scope)
        uptime = get_uptime(service, scope) if status == "active" else "-"

        if status == "active":
            active += 1
        elif status == "failed":
            failed += 1
        else:
            inactive += 1

        if filter_text and filter_text not in name.lower() and filter_text not in service.lower():
            continue

        rows.append({
            "index": index,
            "name": name,
            "service": service,
            "scope": scope,
            "path": path,
            "url": url,
            "status": status,
            "enabled": enabled,
            "uptime": uptime,
        })

    summary = f"{len(services)} services · {active} active · {inactive} inactive · {failed} failed"
    return rows, summary


def render_service_snapshot(rows, summary, generation):
    if generation != refresh_generation:
        return

    for widget in service_frame.winfo_children():
        widget.destroy()

    add_header()

    if service_count_label:
        service_count_label.config(text=summary)

    if not rows:
        tk.Label(
            service_frame,
            text="No services configured yet. Add a service to get started.",
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            font=FONT_MAIN,
            anchor="w"
        ).pack(fill=tk.X, padx=18, pady=18)
        return

    for item in rows:
        index = item["index"]
        name = item["name"]
        service = item["service"]
        scope = item["scope"]
        path = item["path"]
        url = item["url"]
        status = item["status"]
        enabled = item["enabled"]
        uptime = item["uptime"]

        status_color = "#888888"
        row_bg = COLORS["panel"]

        if status == "active":
            status_color = COLORS["success"]
            row_bg = COLORS["row_active"]
        elif status == "inactive":
            status_color = COLORS["danger"]
            row_bg = COLORS["row_inactive"]
        elif status == "failed":
            status_color = COLORS["warning"]
            row_bg = COLORS["row_failed"]

        enabled_color = "#888888"
        enabled_text = enabled

        if enabled == "enabled":
            enabled_color = COLORS["success"]
            enabled_text = "on"
        elif enabled == "disabled":
            enabled_color = COLORS["danger"]
            enabled_text = "off"

        row = tk.Frame(service_frame, bg=row_bg)
        row.pack(fill=tk.X, padx=10, pady=5)
        row.bind("<Double-Button-1>", lambda e, i=index: edit_service_by_index(i))
        row.grid_columnconfigure(0, minsize=SERVICE_GRID_COLUMNS["service"])
        row.grid_columnconfigure(1, minsize=SERVICE_GRID_COLUMNS["scope"])
        row.grid_columnconfigure(2, minsize=SERVICE_GRID_COLUMNS["status"])
        row.grid_columnconfigure(3, minsize=SERVICE_GRID_COLUMNS["autostart"])
        row.grid_columnconfigure(4, minsize=SERVICE_GRID_COLUMNS["uptime"])
        row.grid_columnconfigure(5, minsize=SERVICE_GRID_COLUMNS["actions"])

        status_icon = "▲" if status == "failed" else "●"

        def add_cell(column, text, color, font=("Arial", 11, "bold")):
            tk.Label(
                row,
                text=text,
                fg=color,
                bg=row_bg,
                font=font,
                anchor="w"
            ).grid(row=0, column=column, sticky="w", padx=8, pady=6)

        add_cell(0, f"{status_icon}  {name}", status_color, ("Arial", 13, "bold"))
        add_cell(1, scope.upper(), COLORS["accent"] if scope == "user" else COLORS["muted"])
        add_cell(2, status, status_color)
        add_cell(3, enabled_text, enabled_color)
        add_cell(4, uptime, uptime_color(uptime))

        actions_frame = tk.Frame(row, bg=row_bg)
        actions_frame.grid(row=0, column=5, sticky="w", padx=8, pady=4)

        create_button(actions_frame, text="Start", width=7, variant="success", command=lambda s=service, sc=scope: control_service("start", s, sc)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Stop", width=7, variant="danger", command=lambda s=service, sc=scope: control_service("stop", s, sc)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Restart", width=8, variant="warning", command=lambda s=service, sc=scope: control_service("restart", s, sc)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Logs", width=7, variant="accent", command=lambda s=service, sc=scope: show_logs(s, sc)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Auto on", width=8, variant="success", command=lambda s=service, sc=scope: control_autostart("enable", s, sc)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Auto off", width=8, variant="danger", command=lambda s=service, sc=scope: control_autostart("disable", s, sc)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)

        if url:
            create_button(actions_frame, text="URL", width=7, variant="accent", command=lambda u=url: open_url(u)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)

        if path:
            create_button(actions_frame, text="Folder", width=8, variant="muted", command=lambda p=path: open_folder(p)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
            create_button(actions_frame, text="Code", width=7, variant="accent", command=lambda p=path: open_code(p)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)


def refresh_services():
    global refresh_generation, refresh_running, refresh_pending

    try:
        if refresh_running:
            refresh_pending = True
            return

        refresh_running = True
        refresh_generation += 1
        generation = refresh_generation
        services = load_services()
        filter_text = search_var.get().lower() if search_var else ""

        if service_count_label:
            service_count_label.config(text="Checking services...")

        for widget in service_frame.winfo_children():
            widget.destroy()
        add_header()

        def task():
            return collect_service_snapshot(services, filter_text)

        def done(result):
            global refresh_running, refresh_pending

            if isinstance(result, Exception):
                report_runtime_error("refresh", "Refresh failed", str(result))
            else:
                rows, summary = result
                render_service_snapshot(rows, summary, generation)

            refresh_running = False
            if refresh_pending:
                refresh_pending = False
                refresh_services()

        run_background(task, done)

    except Exception as e:
        refresh_running = False
        report_runtime_error("refresh", "Refresh failed", str(e))


def auto_refresh_services():
    try:
        refresh_services()
    finally:
        try:
            root.after(5000, auto_refresh_services)
        except tk.TclError:
            pass


def update_system_info():
    try:
        cpu_value.config(text=get_cpu_usage())
        ram_value.config(text=get_ram_usage())
        temp_value.config(text=get_temperature())
        disk_value.config(text=get_disk_free())

    except Exception as e:
        report_runtime_error("system_info", "System Info Error", str(e))

    finally:
        try:
            root.after(3000, update_system_info)
        except tk.TclError:
            pass


root = tk.Tk()
root.title(APP_NAME)
root.geometry("1280x720")
root.minsize(1100, 650)
root.configure(bg=COLORS["bg"])

# Start maximized where the window manager supports it.
try:
    root.state("zoomed")
except tk.TclError:
    try:
        root.attributes("-zoomed", True)
    except tk.TclError:
        pass

# Compact top area: system cards on the left, branding/search on the right.
top_frame = tk.Frame(root, bg=COLORS["bg"])
top_frame.pack(fill=tk.X, padx=18, pady=(7, 3))

info_frame = tk.Frame(top_frame, bg=COLORS["bg"])
info_frame.pack(side=tk.LEFT, anchor="n")

cpu_value = create_info_card(info_frame, "CPU", "0.0%", COLORS["success"])
ram_value = create_info_card(info_frame, "RAM", "0.0%", COLORS["accent_2"])
temp_value = create_info_card(info_frame, "TEMP", "N/A", COLORS["warning"])
disk_value = create_info_card(info_frame, "DISK FREE", "N/A", COLORS["text"])

header_frame = tk.Frame(top_frame, bg=COLORS["bg"])
header_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(26, 0), anchor="n")

load_logo(header_frame)

title_box = tk.Frame(header_frame, bg=COLORS["bg"])
title_box.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="n")

tk.Label(
    title_box,
    text=APP_NAME,
    fg=COLORS["text"],
    bg=COLORS["bg"],
    font=FONT_TITLE
).pack(anchor="w")

tk.Label(
    title_box,
    text=APP_BRANDING,
    fg=COLORS["muted"],
    bg=COLORS["bg"],
    font=("Arial", 9)
).pack(anchor="w")

meta_row = tk.Frame(title_box, bg=COLORS["bg"])
meta_row.pack(anchor="w", pady=(1, 0))

tk.Label(
    meta_row,
    text=f"Version {APP_VERSION}",
    fg=COLORS["muted"],
    bg=COLORS["bg"],
    font=("Arial", 10)
).pack(side=tk.LEFT)

service_count_label = tk.Label(
    meta_row,
    text="Loading services...",
    fg=COLORS["accent"],
    bg=COLORS["bg"],
    font=("Arial", 10, "bold")
)
service_count_label.pack(side=tk.LEFT, padx=(14, 0))

search_var = tk.StringVar()

search_frame = tk.Frame(title_box, bg=COLORS["bg"])
search_frame.pack(fill=tk.X, anchor="w", pady=(8, 0))

tk.Label(
    search_frame,
    text="Search service",
    fg=COLORS["muted"],
    bg=COLORS["bg"],
    font=("Arial", 10, "bold")
).pack(anchor="w")

search_entry = create_entry(search_frame, textvariable=search_var, width=62)
search_entry.pack(fill=tk.X, pady=(3, 0))
search_entry.insert(0, "")
search_entry.bind("<KeyRelease>", lambda e: refresh_services())

service_panel = tk.Frame(root, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border"])
service_panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=(3, 7))

service_canvas = tk.Canvas(service_panel, bg=COLORS["panel"], highlightthickness=0, bd=0)
service_scrollbar = tk.Scrollbar(service_panel, orient=tk.VERTICAL, command=service_canvas.yview)
service_canvas.configure(yscrollcommand=service_scrollbar.set)
service_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
service_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

service_frame = tk.Frame(service_canvas, bg=COLORS["panel"])
service_window = service_canvas.create_window((0, 0), window=service_frame, anchor="nw")

def update_service_scroll_region(event=None):
    service_canvas.configure(scrollregion=service_canvas.bbox("all"))
    service_canvas.itemconfigure(service_window, width=service_canvas.winfo_width())

service_frame.bind("<Configure>", update_service_scroll_region)
service_canvas.bind("<Configure>", update_service_scroll_region)

bottom_frame = tk.Frame(root, bg=COLORS["bg"])
bottom_frame.pack(fill=tk.X, padx=18, pady=(0, 7))

button_frame = tk.Frame(bottom_frame, bg=COLORS["bg"])
button_frame.pack(side=tk.TOP)

refresh_button = create_button(button_frame, text="Refresh", width=16, command=refresh_services)
refresh_button.pack(side=tk.LEFT, padx=4)
add_tooltip(refresh_button, "Reload service status")

add_button = create_button(button_frame, text="+ Service", width=14, command=add_project_window)
add_button.pack(side=tk.LEFT, padx=4)
add_tooltip(add_button, "Add an existing systemd service to the list")

assistant_button = create_button(button_frame, text="+ Assistant", width=14, command=service_assistant_window, variant="accent")
assistant_button.pack(side=tk.LEFT, padx=4)
add_tooltip(assistant_button, "Create a new systemd service with the assistant")

diagnostics_button = create_button(button_frame, text="Diagnostics", width=14, command=show_diagnostics_window, variant="warning")
diagnostics_button.pack(side=tk.LEFT, padx=4)
add_tooltip(diagnostics_button, "Show system and service information")

edit_button = create_button(button_frame, text="Edit", width=14, command=edit_project_window)
edit_button.pack(side=tk.LEFT, padx=4)
add_tooltip(edit_button, "Edit an entry in the service list")

delete_button = create_button(button_frame, text="- Service", width=14, command=delete_project_window)
delete_button.pack(side=tk.LEFT, padx=4)
add_tooltip(delete_button, "Remove an entry from the service list")

footer_frame = tk.Frame(bottom_frame, bg=COLORS["bg"])
footer_frame.pack(side=tk.TOP, pady=(6, 0))

tk.Label(
    footer_frame,
    text=f"{APP_NAME} {APP_VERSION}  ·  {APP_BRANDING}  ·  ",
    fg=COLORS["muted"],
    bg=COLORS["bg"],
    font=("Arial", 9)
).pack(side=tk.LEFT)

create_link_label(
    footer_frame,
    "GitHub",
    lambda: open_external_link(GITHUB_URL)
).pack(side=tk.LEFT, padx=4)

tk.Label(footer_frame, text=" · ", fg=COLORS["muted"], bg=COLORS["bg"], font=("Arial", 9)).pack(side=tk.LEFT)

create_link_label(
    footer_frame,
    "Patreon",
    lambda: open_external_link(PATREON_URL)
).pack(side=tk.LEFT, padx=4)

refresh_services()
update_system_info()
auto_refresh_services()

root.mainloop()
