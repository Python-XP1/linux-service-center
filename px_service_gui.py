import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import subprocess
import json
import os
import psutil
import time
import re
import shutil
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

APP_VERSION = "v1.0.0"
APP_NAME = "Linux Service Center"
APP_BRANDING = "powered by PythonXP"
GITHUB_URL = "https://github.com/Python-XP1"
PATREON_URL = "https://www.patreon.com/PythonXP"

COMMAND_TIMEOUT = 10
SERVICE_GRID_COLUMNS = {
    "service": 250,
    "status": 110,
    "autostart": 110,
    "uptime": 90,
    "actions": 720,
}
ACTION_BUTTON_PADX = 2

SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")
USER_NAME_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.-]*[$]?|[0-9]+)$")
PROTECTED_SERVICES = {
    "ssh.service": "SSH",
    "zerotier-one.service": "ZeroTier",
    "realvnc-vnc-server.service": "RealVNC",
    "vncserver-x11-serviced.service": "RealVNC",
    "wayvnc.service": "WayVNC",
}
DIAGNOSTIC_COMMANDS = [
    ("hostname -I", ["hostname", "-I"]),
    ("uptime -p", ["uptime", "-p"]),
    ("who -b", ["who", "-b"]),
    ("systemctl is-active ssh.service", ["systemctl", "is-active", "ssh.service"]),
    ("systemctl is-enabled ssh.service", ["systemctl", "is-enabled", "ssh.service"]),
    ("systemctl is-active zerotier-one.service", ["systemctl", "is-active", "zerotier-one.service"]),
    ("systemctl is-active realvnc-vnc-server.service", ["systemctl", "is-active", "realvnc-vnc-server.service"]),
    ("systemctl is-active vncserver-x11-serviced.service", ["systemctl", "is-active", "vncserver-x11-serviced.service"]),
    ("systemctl is-active wayvnc.service", ["systemctl", "is-active", "wayvnc.service"]),
    ("ss -tulpn", ["ss", "-tulpn"]),
    ("ip -br addr", ["ip", "-br", "addr"]),
    ("systemctl --failed --no-pager", ["systemctl", "--failed", "--no-pager"]),
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
        status = get_status(item.get("service", ""))
        if status == "active":
            active += 1
        elif status == "failed":
            failed += 1
        else:
            inactive += 1

    return f"{len(services)} Services · {active} aktiv · {inactive} inaktiv · {failed} failed"


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
        report_config_error(f"{CONFIG_FILE} konnte nicht gelesen werden:\n{e}")
        return []

    if not isinstance(data, list):
        report_config_error("services.json muss eine Liste von Services enthalten.")
        return []

    last_config_error = None
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

    except OSError as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        show_error("Speichern fehlgeschlagen", str(e))
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
        return "", f"Befehl nach {COMMAND_TIMEOUT}s abgebrochen: {' '.join(cmd)}"

    except Exception as e:
        return "", str(e)


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
    show_error("Konfiguration fehlerhaft", message)


def report_runtime_error(key, title, message):
    if key in last_runtime_errors:
        return

    last_runtime_errors.add(key)
    show_error(title, message)


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


def validate_service_config(item):
    if not item["name"] or not item["service"]:
        return "Anzeigename und Systemd Service müssen ausgefüllt sein."

    if not is_valid_service_name(item["service"]):
        return "Der Systemd Service muss wie ein gültiger .service-Name aussehen, z. B. ssh.service."

    if item["url"] and not is_valid_url(item["url"]):
        return "Die URL muss mit http:// oder https:// beginnen."

    if item["path"]:
        item["path"] = normalize_path(item["path"])

    return None


def run_background(task, on_done=None):
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


def run_systemctl_action(action, service):
    try:
        base_cmd = ["systemctl", action, service]

        if os.geteuid() == 0:
            return run_systemctl_command(base_cmd)

        ok, message = run_systemctl_command(["sudo", "-n"] + base_cmd)
        if ok:
            return True, message

        pkexec_cmd = shutil.which("pkexec")
        if needs_authentication(message) and pkexec_cmd:
            ok, pkexec_message = run_systemctl_command([pkexec_cmd] + base_cmd)
            if ok:
                return True, pkexec_message
            message = pkexec_message or message

        if needs_authentication(message):
            message = (
                "Für diese Aktion fehlen Rechte.\n"
                "Erlaube die angezeigte Authentifizierung, starte das Programm mit passenden Rechten "
                "oder richte sudoers für systemctl ein.\n\n"
                f"Originalmeldung:\n{message}"
            )
        return False, message

    except subprocess.TimeoutExpired:
        return False, "systemctl hat nach 30 Sekunden nicht geantwortet."

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
        return 124, "", f"Befehl nach {timeout}s abgebrochen."
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


def get_status(service):
    if not is_valid_service_name(service):
        return "invalid"

    out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"


def get_enabled_status(service):
    if not is_valid_service_name(service):
        return "invalid"

    out, _ = run_cmd(["systemctl", "is-enabled", service])
    return out if out else "unknown"


def get_uptime(service):
    if not is_valid_service_name(service):
        return "-"

    out, _ = run_cmd([
        "systemctl",
        "show",
        service,
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

        if diff < 60:
            return f"{diff}s"
        if diff < 3600:
            return f"{diff // 60}m"
        if diff < 86400:
            return f"{diff // 3600}h"

        return f"{diff // 86400}d"

    except (ValueError, subprocess.SubprocessError, OSError):
        return "-"


def get_cpu_usage():
    try:
        return f"{psutil.cpu_percent(interval=0.1):.1f}%"
    except (psutil.Error, OSError) as e:
        report_runtime_error("cpu", "Systeminfo Fehler", f"CPU-Auslastung konnte nicht gelesen werden:\n{e}")
        return "N/A"


def get_ram_usage():
    try:
        return f"{psutil.virtual_memory().percent:.1f}%"
    except (psutil.Error, OSError) as e:
        report_runtime_error("ram", "Systeminfo Fehler", f"RAM-Auslastung konnte nicht gelesen werden:\n{e}")
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
        report_runtime_error("disk", "Systeminfo Fehler", f"Freier Speicher konnte nicht gelesen werden:\n{e}")
        return "N/A"


def control_service(action, service):
    if action not in {"start", "stop", "restart"} or not is_valid_service_name(service):
        messagebox.showerror("Ungültige Aktion", "Service oder Aktion ist ungültig.")
        return

    protected_label = PROTECTED_SERVICES.get(service)
    if protected_label and action == "restart":
        if not messagebox.askyesno(
            "Kritischer Dienst",
            f"Kritischer Dienst: {protected_label}. Wirklich neu starten?"
        ):
            return
    elif protected_label and action == "stop":
        if not messagebox.askyesno(
            "Remote-Zugriff warnen",
            "Wenn du diesen Dienst stoppst, kannst du den Remote-Zugriff verlieren. Wirklich stoppen?"
        ):
            return

    invalidate_refresh()
    action_labels = {
        "start": "Start",
        "stop": "Stop",
        "restart": "Restart",
    }

    if service_count_label:
        service_count_label.config(text=f"{action_labels[action]} läuft für {service}...")

    def task():
        return run_systemctl_action(action, service)

    def done(result):
        if isinstance(result, Exception):
            messagebox.showerror("systemctl Fehler", str(result))
        elif not result[0]:
            messagebox.showerror("systemctl Fehler", result[1] or "Aktion fehlgeschlagen.")
        elif service_count_label:
            service_count_label.config(text=f"{action_labels[action]} ausgeführt für {service}. Status wird geprüft...")

        refresh_services()

    run_background(task, done)


def show_diagnostics_window():
    win = tk.Toplevel(root)
    win.title("Diagnose")
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
            output = [
                "Hinweis: Remote-Zugriff kann je nach System über unterschiedliche Dienste laufen, "
                "z.B. ssh.service, wayvnc.service, realvnc-vnc-server.service oder "
                "vncserver-x11-serviced.service.\n\n"
            ]
            for label, command in DIAGNOSTIC_COMMANDS:
                try:
                    code, stdout, stderr = run_diagnostic_command(command, timeout=15)
                    output.append(format_command_result(label, code, stdout, stderr))
                except Exception as e:
                    output.append(f"$ {label}\nFEHLER: {e}\n\n")
            output.append("Diagnose abgeschlossen.\n")

            try:
                root.after(0, lambda text="".join(output): finish_diagnostics(text))
            except tk.TclError as e:
                print(f"Diagnosefenster Fehler: {e}")

        threading.Thread(target=task, daemon=True).start()

    buttons.append(create_button(button_row, text="Diagnose neu laden", width=18, command=run_diagnostics, variant="accent"))
    buttons[-1].pack(side=tk.LEFT, padx=(0, 6))

    text_box.config(state=tk.DISABLED)
    run_diagnostics()


def control_autostart(action, service):
    if action not in {"enable", "disable"} or not is_valid_service_name(service):
        messagebox.showerror("Ungültige Aktion", "Service oder Aktion ist ungültig.")
        return

    invalidate_refresh()
    if service_count_label:
        service_count_label.config(text=f"Autostart-{action} läuft für {service}...")

    def task():
        return run_systemctl_action(action, service)

    def done(result):
        if isinstance(result, Exception):
            messagebox.showerror("systemctl Fehler", str(result))
        elif not result[0]:
            messagebox.showerror("systemctl Fehler", result[1] or "Aktion fehlgeschlagen.")

        refresh_services()

    run_background(task, done)


def open_external_link(url):
    if url and is_valid_url(url):
        subprocess.Popen(["xdg-open", url])
    else:
        messagebox.showwarning("Link ungültig", "Der hinterlegte Link ist ungültig.")


def open_url(url):
    if url and is_valid_url(url):
        try:
            subprocess.Popen(["xdg-open", url])
            return
        except OSError as e:
            messagebox.showerror("URL öffnen fehlgeschlagen", str(e))
            return

    messagebox.showwarning("URL ungültig", "Keine gültige http(s)-URL hinterlegt.")


def open_folder(path):
    safe_path = normalize_path(path)

    if safe_path and os.path.isdir(safe_path):
        try:
            subprocess.Popen(["xdg-open", safe_path])
        except OSError as e:
            messagebox.showerror("Ordner öffnen fehlgeschlagen", str(e))
    else:
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")


def open_code(path):
    safe_path = normalize_path(path)

    if not safe_path or not os.path.isdir(safe_path):
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")
        return

    try:
        code_cmd = shutil.which("code")

        if not code_cmd:
            messagebox.showerror(
                "VS Code Fehler",
                "VS Code wurde nicht gefunden."
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
        messagebox.showerror("VS Code Fehler", str(e))


def show_logs(service):
    if not is_valid_service_name(service):
        messagebox.showerror("Ungültiger Service", "Der Service-Name ist ungültig.")
        return

    out, err = run_cmd(["journalctl", "-u", service, "-n", "120", "--no-pager"])

    win = tk.Toplevel(root)
    win.title(f"Logs: {service}")
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
    text.insert(tk.END, out if out else err)
    text.config(state=tk.DISABLED)


def browse_services(target_entry):
    win = tk.Toplevel(root)
    win.title("Systemd Services durchsuchen")
    win.geometry("720x520")
    win.configure(bg=COLORS["bg"])

    tk.Label(
        win,
        text="Doppelklick auf einen Service zum Übernehmen",
        fg="white",
        bg=COLORS["bg"],
        font=("Arial", 11, "bold")
    ).pack(pady=10)

    tk.Label(
        win,
        text="Service suchen",
        fg=COLORS["text"],
        bg=COLORS["bg"],
        font=FONT_BOLD
    ).pack(anchor="w", padx=10)

    search_entry = create_entry(win, width=70)
    search_entry.pack(fill=tk.X, padx=10, pady=(3, 0))
    search_entry.insert(0, "Service suchen...")

    tk.Label(
        win,
        text="Tippe einen Namensteil ein, z.B. ssh, bluetooth, nginx",
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=FONT_SMALL
    ).pack(anchor="w", padx=10, pady=(2, 8))

    list_frame = tk.Frame(win, bg=COLORS["bg"])
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
    listbox = create_listbox(list_frame, width=85)
    listbox.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    out, err = run_cmd(["systemctl", "list-unit-files", "--type=service", "--no-legend"])

    if err and not out:
        messagebox.showwarning("Services laden", err)

    all_services = sorted([line.split()[0] for line in out.splitlines() if line.strip()])

    def fill_list(filter_text=""):
        listbox.delete(0, tk.END)

        for service in all_services:
            if filter_text.lower() in service.lower():
                listbox.insert(tk.END, service)

    def select_service(event=None):
        selection = listbox.curselection()

        if not selection:
            return

        service = listbox.get(selection[0])
        target_entry.delete(0, tk.END)
        target_entry.insert(0, service)
        win.destroy()

    def get_search_text():
        value = search_entry.get()
        return "" if value == "Service suchen..." else value

    def clear_placeholder(event=None):
        if search_entry.get() == "Service suchen...":
            search_entry.delete(0, tk.END)

    search_entry.bind("<FocusIn>", clear_placeholder)
    search_entry.bind("<KeyRelease>", lambda e: fill_list(get_search_text()))
    listbox.bind("<Double-Button-1>", select_service)

    create_button(win, text="Übernehmen", command=select_service).pack(pady=10)

    fill_list()


def project_form(title_text, existing=None, index=None):
    win = tk.Toplevel(root)
    win.title(title_text)
    win.geometry("520x430")
    win.configure(bg=COLORS["bg"])

    fields = {}

    tk.Label(win, text="Anzeigename", fg="white", bg=COLORS["bg"]).pack(anchor="w", padx=20, pady=(10, 0))
    fields["name"] = create_entry(win, width=60)
    fields["name"].pack(padx=20, pady=3)
    fields["name"].insert(0, existing.get("name", "") if existing else "")

    tk.Label(win, text="Systemd Service", fg="white", bg=COLORS["bg"]).pack(anchor="w", padx=20, pady=(10, 0))
    fields["service"] = create_entry(win, width=60)
    fields["service"].pack(padx=20, pady=3)
    fields["service"].insert(0, existing.get("service", "") if existing else "")

    tk.Label(
        win,
        text="Beispiel: ssh.service, code-server.service, bluetooth.service",
        fg=COLORS["muted"],
        bg=COLORS["bg"],
        font=("Arial", 9)
    ).pack(anchor="w", padx=20)

    create_button(
        win,
        text="Services durchsuchen",
        width=22,
        command=lambda: browse_services(fields["service"])
    ).pack(pady=6)

    tk.Label(win, text="Ordner/Pfad optional", fg="white", bg=COLORS["bg"]).pack(anchor="w", padx=20, pady=(10, 0))
    fields["path"] = create_entry(win, width=60)
    fields["path"].pack(padx=20, pady=3)
    fields["path"].insert(0, existing.get("path", "") if existing else "")

    tk.Label(win, text="URL optional", fg="white", bg=COLORS["bg"]).pack(anchor="w", padx=20, pady=(10, 0))
    fields["url"] = create_entry(win, width=60)
    fields["url"].pack(padx=20, pady=3)
    fields["url"].insert(0, existing.get("url", "") if existing else "")

    def save_project():
        services = load_services()

        item = {
            "name": fields["name"].get().strip(),
            "service": fields["service"].get().strip(),
            "path": fields["path"].get().strip(),
            "url": fields["url"].get().strip()
        }

        validation_error = validate_service_config(item)

        if validation_error:
            messagebox.showwarning("Eingabe prüfen", validation_error)
            return

        if index is None:
            services.append(item)
        elif 0 <= index < len(services):
            services[index] = item
        else:
            messagebox.showerror("Speichern fehlgeschlagen", "Der ausgewählte Service existiert nicht mehr.")
            return

        if not save_services(services):
            return

        refresh_services()
        win.destroy()

    create_button(win, text="Speichern", width=18, command=save_project).pack(pady=18)



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


def build_service_unit(description, command, working_dir, user_name, restart_policy):
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
        "WantedBy=multi-user.target",
        ""
    ])

    return "\n".join(lines)


def write_systemd_service(service_name, unit_text):
    """Write a service file into /etc/systemd/system using sudo tee."""
    if not is_valid_service_name(service_name):
        return False, "Ungültiger Service-Name. Beispiel: meinprojekt.service"

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
            return False, result.stderr.strip() or "Service-Datei konnte nicht geschrieben werden."

        chmod_result = subprocess.run(
            ["sudo", "chmod", "644", service_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if chmod_result.returncode != 0:
            return False, chmod_result.stderr.strip() or "Rechte konnten nicht gesetzt werden."

        reload_result = subprocess.run(
            ["sudo", "systemctl", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if reload_result.returncode != 0:
            return False, reload_result.stderr.strip() or "daemon-reload fehlgeschlagen."

        return True, f"Service erstellt: {service_path}"

    except subprocess.TimeoutExpired:
        return False, "Schreibvorgang hat zu lange gedauert."
    except OSError as e:
        return False, str(e)


def service_assistant_window():
    """Simple assistant that creates a real systemd .service file and adds it to the panel."""
    win = tk.Toplevel(root)
    win.title("+ Service Assistent")
    win.geometry("760x620")
    win.minsize(720, 560)
    win.configure(bg=COLORS["bg"])

    outer = tk.Frame(win, bg=COLORS["bg"])
    outer.pack(fill=tk.BOTH, expand=True)

    # Scrollbarer Inhaltsbereich: Der Button bleibt unten immer sichtbar,
    # auch bei kleinen VNC-Fenstern oder wenn "Erweiterte Einstellungen" offen ist.
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
        # Linux/X11 liefert Button-4/Button-5, Windows/macOS meist MouseWheel.
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
        text="Service Assistent",
        fg=COLORS["text"],
        bg=COLORS["bg"],
        font=("Arial", 18, "bold")
    ).pack(anchor="w")

    tk.Label(
        content,
        text="Einfacher Modus: Projektordner wählen, Python-Datei angeben, Service erstellen. Erweiterte Felder sind optional.",
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

    name_entry = add_field(simple_frame, "name", "Projektname", "So erscheint der Dienst im Panel, z.B. Web App")

    tk.Label(simple_frame, text="Projektordner", fg=COLORS["text"], bg=COLORS["bg"], font=FONT_BOLD).pack(anchor="w", pady=(8, 0))
    folder_row = tk.Frame(simple_frame, bg=COLORS["bg"])
    folder_row.pack(fill=tk.X, pady=(3, 0))
    workdir_entry = create_entry(folder_row, width=58)
    workdir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    fields["workdir"] = workdir_entry

    def choose_folder():
        selected = filedialog.askdirectory(title="Projektordner wählen")
        if not selected:
            return
        workdir_entry.delete(0, tk.END)
        workdir_entry.insert(0, selected)
        maybe_autofill_from_folder(selected)
        update_preview()

    create_button(folder_row, text="Ordner wählen", width=14, command=choose_folder, variant="muted").pack(side=tk.LEFT, padx=(8, 0))
    tk.Label(simple_frame, text="Beispiel: /home/pi/my-service", fg=COLORS["muted"], bg=COLORS["bg"], font=FONT_SMALL).pack(anchor="w", pady=(2, 0))

    script_entry = add_field(simple_frame, "script", "Python-Datei", "Meistens app.py oder main.py. Absoluter Pfad ist auch erlaubt.", "app.py")
    url_entry = add_field(simple_frame, "url", "URL optional", "Für Webapps, z.B. http://127.0.0.1:5050")

    options_frame = tk.Frame(simple_frame, bg=COLORS["bg"])
    options_frame.pack(anchor="w", pady=(12, 0), fill=tk.X)

    enable_var = tk.BooleanVar(value=True)
    start_var = tk.BooleanVar(value=False)
    add_panel_var = tk.BooleanVar(value=True)

    for text, var in [
        ("Autostart aktivieren", enable_var),
        ("Service nach Erstellung direkt starten", start_var),
        ("Direkt zur Panel-Liste hinzufügen", add_panel_var),
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
    service_entry = add_field(advanced_frame, "service", "Service-Dateiname", "Optional. Wird automatisch aus dem Projektnamen erzeugt, z.B. web-app.service")
    user_entry = add_field(advanced_frame, "user", "Linux-Benutzer", "Normalerweise: pi", current_user)
    command_entry = add_field(advanced_frame, "command", "Startbefehl", "Optional. Wird automatisch gebaut: /usr/bin/python3 /pfad/app.py")

    restart_row = tk.Frame(advanced_frame, bg=COLORS["panel"])
    restart_row.pack(anchor="w", pady=(8, 0), fill=tk.X)
    tk.Label(restart_row, text="Restart-Verhalten", fg=COLORS["text"], bg=COLORS["panel"], font=FONT_BOLD).pack(anchor="w")
    restart_var = tk.StringVar(value="always")
    restart_menu = tk.OptionMenu(restart_row, restart_var, "always", "on-failure", "no")
    restart_menu.configure(bg=COLORS["button"], fg=COLORS["text"], activebackground=COLORS["button_hover"], activeforeground=COLORS["text"], relief=tk.FLAT, highlightthickness=0)
    restart_menu["menu"].configure(bg=COLORS["button"], fg=COLORS["text"])
    restart_menu.pack(anchor="w", pady=(3, 0))

    def toggle_advanced():
        if advanced_visible.get():
            advanced_frame.pack_forget()
            advanced_visible.set(False)
            advanced_button.configure(text="Erweiterte Einstellungen anzeigen")
        else:
            advanced_frame.pack(fill=tk.X, pady=(12, 0))
            advanced_visible.set(True)
            advanced_button.configure(text="Erweiterte Einstellungen ausblenden")

    advanced_button = create_button(content, text="Erweiterte Einstellungen anzeigen", width=30, command=toggle_advanced, variant="muted")
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
            value = "meinprojekt"
        return normalize_service_filename(value)

    def maybe_autofill_from_folder(folder):
        folder = normalize_path(folder)
        if not folder:
            return

        if not fields["name"].get().strip():
            fields["name"].insert(0, os.path.basename(folder.rstrip(os.sep)) or "Mein Projekt")

        candidates = ["app.py", "main.py", "server.py", "run.py"]
        for filename in candidates:
            if os.path.isfile(os.path.join(folder, filename)):
                fields["script"].delete(0, tk.END)
                fields["script"].insert(0, filename)
                break

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
        script_path = resolve_script_path(workdir, fields["script"].get().strip())
        url = fields["url"].get().strip()
        service_name = normalize_service_filename(fields["service"].get().strip()) if fields["service"].get().strip() else slugify_service_name(name)
        user_name = fields["user"].get().strip()
        restart_policy = restart_var.get()
        command = fields["command"].get().strip()

        if not name:
            return None, "Projektname fehlt."
        if any(has_line_break(value) for value in [name, workdir, script_path, user_name, command]):
            return None, "Eingaben für die Service-Datei dürfen keine Zeilenumbrüche enthalten."
        if not is_valid_service_name(service_name):
            return None, "Service-Dateiname ungültig. Beispiel: meinprojekt.service"
        if user_name and not is_valid_user_name(user_name):
            return None, "Linux-Benutzer ungültig. Beispiel: pi oder root."
        if not workdir or not os.path.isdir(workdir):
            return None, "Projektordner existiert nicht."
        if not script_path or not os.path.isfile(script_path):
            return None, "Python-Datei wurde nicht gefunden. Beispiel: app.py oder /home/pi/projekt/app.py"
        if url and not is_valid_url(url):
            return None, "URL muss mit http:// oder https:// beginnen."
        if not command:
            python_cmd = shutil.which("python3") or "/usr/bin/python3"
            command = f"{systemd_quote_arg(python_cmd)} {systemd_quote_arg(script_path)}"

        unit_text = build_service_unit(
            description=name,
            command=command,
            working_dir=workdir,
            user_name=user_name,
            restart_policy=restart_policy
        )

        return {
            "name": name,
            "service": service_name,
            "path": workdir,
            "url": url,
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
            preview_box.insert(tk.END, f"Vorschau noch nicht vollständig:\n{error}")
        else:
            preview_box.insert(tk.END, data["unit_text"])
        preview_box.config(state=tk.DISABLED)

    for entry in fields.values():
        entry.bind("<KeyRelease>", update_preview)
    restart_var.trace_add("write", lambda *_: update_preview())

    def create_service():
        data, error = collect_data()
        if error:
            messagebox.showwarning("Eingabe prüfen", error)
            return

        if not messagebox.askyesno(
            "Service erstellen",
            f"Soll {data['service']} wirklich unter /etc/systemd/system erstellt werden?"
        ):
            return

        def task():
            ok, msg = write_systemd_service(data["service"], data["unit_text"])
            if not ok:
                return False, msg

            if data["enable"]:
                ok, msg = run_systemctl_action("enable", data["service"])
                if not ok:
                    return False, msg

            if data["start"]:
                ok, msg = run_systemctl_action("start", data["service"])
                if not ok:
                    return False, msg

            if data["add_panel"]:
                services = load_services()
                item = {
                    "name": data["name"],
                    "service": data["service"],
                    "path": data["path"],
                    "url": data["url"],
                }
                existing_index = next((i for i, s in enumerate(services) if s.get("service") == data["service"]), None)
                if existing_index is None:
                    services.append(item)
                else:
                    services[existing_index] = item
                if not save_services(services):
                    return False, "Service wurde erstellt, aber nicht in services.json gespeichert."

            return True, "Service wurde erfolgreich erstellt."

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror("Service Assistent", str(result))
                return
            ok, msg = result
            if ok:
                messagebox.showinfo("Service Assistent", msg)
                refresh_services()
                close_assistant()
            else:
                messagebox.showerror("Service Assistent", msg or "Erstellung fehlgeschlagen.")

        run_background(task, done)

    create_button(button_bar, text="Abbrechen", command=close_assistant, width=12, variant="muted").pack(side=tk.RIGHT, padx=6)
    create_button(button_bar, text="Service erstellen", command=create_service, width=20, variant="success").pack(side=tk.RIGHT, padx=6)

    update_preview()

def add_project_window():
    project_form("Service hinzufügen")


def edit_service_by_index(index):
    services = load_services()

    if 0 <= index < len(services):
        project_form("Service bearbeiten", services[index], index)


def edit_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Service bearbeiten")
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

    create_button(win, text="Bearbeiten", width=18, command=edit_selected).pack(pady=10)


def delete_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Service entfernen")
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

        if messagebox.askyesno("Entfernen", f"{name} wirklich aus der Liste entfernen?"):
            try:
                services.pop(index)
            except IndexError:
                messagebox.showerror("Entfernen fehlgeschlagen", "Der ausgewählte Service existiert nicht mehr.")
                return

            if not save_services(services):
                return

            refresh_services()
            win.destroy()

    create_button(win, text="Entfernen", width=18, command=delete_selected).pack(pady=10)


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
        print("Pillow fehlt. Logo wird nicht geladen.")
        return

    try:
        logo_img = Image.open(logo_path)
        logo_img.thumbnail((78, 78))

        logo_photo = ImageTk.PhotoImage(logo_img)

        logo_label = tk.Label(parent, image=logo_photo, bg=COLORS["bg"])
        logo_label.image = logo_photo
        logo_label.pack(side=tk.LEFT, padx=(10, 14))

    except Exception as e:
        print("Logo konnte nicht geladen werden:", e)


def add_header():
    header = tk.Frame(service_frame, bg=COLORS["panel_2"])
    header.pack(fill=tk.X, padx=12, pady=(10, 5))

    columns = [
        ("Service", "service", 0),
        ("Status", "status", 1),
        ("Autostart", "autostart", 2),
        ("Uptime", "uptime", 3),
        ("Aktionen", "actions", 4),
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
        path = item.get("path", "")
        url = item.get("url", "")

        status = get_status(service)
        enabled = get_enabled_status(service)
        uptime = get_uptime(service) if status == "active" else "-"

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
            "path": path,
            "url": url,
            "status": status,
            "enabled": enabled,
            "uptime": uptime,
        })

    summary = f"{len(services)} Services · {active} aktiv · {inactive} inaktiv · {failed} failed"
    return rows, summary


def render_service_snapshot(rows, summary, generation):
    if generation != refresh_generation:
        return

    for widget in service_frame.winfo_children():
        widget.destroy()

    add_header()

    if service_count_label:
        service_count_label.config(text=summary)

    for item in rows:
        index = item["index"]
        name = item["name"]
        service = item["service"]
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
            enabled_text = "an"
        elif enabled == "disabled":
            enabled_color = COLORS["danger"]
            enabled_text = "aus"

        row = tk.Frame(service_frame, bg=row_bg)
        row.pack(fill=tk.X, padx=10, pady=5)
        row.bind("<Double-Button-1>", lambda e, i=index: edit_service_by_index(i))
        row.grid_columnconfigure(0, minsize=SERVICE_GRID_COLUMNS["service"])
        row.grid_columnconfigure(1, minsize=SERVICE_GRID_COLUMNS["status"])
        row.grid_columnconfigure(2, minsize=SERVICE_GRID_COLUMNS["autostart"])
        row.grid_columnconfigure(3, minsize=SERVICE_GRID_COLUMNS["uptime"])
        row.grid_columnconfigure(4, minsize=SERVICE_GRID_COLUMNS["actions"])

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
        add_cell(1, status, status_color)
        add_cell(2, enabled_text, enabled_color)
        add_cell(3, uptime, uptime_color(uptime))

        actions_frame = tk.Frame(row, bg=row_bg)
        actions_frame.grid(row=0, column=4, sticky="w", padx=8, pady=4)

        create_button(actions_frame, text="Start", width=7, variant="success", command=lambda s=service: control_service("start", s)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Stop", width=7, variant="danger", command=lambda s=service: control_service("stop", s)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Restart", width=8, variant="warning", command=lambda s=service: control_service("restart", s)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Logs", width=7, variant="accent", command=lambda s=service: show_logs(s)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Auto an", width=8, variant="success", command=lambda s=service: control_autostart("enable", s)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
        create_button(actions_frame, text="Auto aus", width=8, variant="danger", command=lambda s=service: control_autostart("disable", s)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)

        if url:
            create_button(actions_frame, text="URL", width=7, variant="accent", command=lambda u=url: open_url(u)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)

        if path:
            create_button(actions_frame, text="Ordner", width=8, variant="muted", command=lambda p=path: open_folder(p)).pack(side=tk.LEFT, padx=ACTION_BUTTON_PADX)
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
            service_count_label.config(text="Services werden geprüft...")

        for widget in service_frame.winfo_children():
            widget.destroy()
        add_header()

        def task():
            return collect_service_snapshot(services, filter_text)

        def done(result):
            global refresh_running, refresh_pending

            if isinstance(result, Exception):
                report_runtime_error("refresh", "Aktualisieren fehlgeschlagen", str(result))
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
        report_runtime_error("refresh", "Aktualisieren fehlgeschlagen", str(e))


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
        report_runtime_error("system_info", "Systeminfo Fehler", str(e))

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
disk_value = create_info_card(info_frame, "DISK FREI", "N/A", COLORS["text"])

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
    text="Services werden geladen...",
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
    text="Service suchen",
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

refresh_button = create_button(button_frame, text="Aktualisieren", width=16, command=refresh_services)
refresh_button.pack(side=tk.LEFT, padx=4)
add_tooltip(refresh_button, "Service-Status neu laden")

add_button = create_button(button_frame, text="+ Service", width=14, command=add_project_window)
add_button.pack(side=tk.LEFT, padx=4)
add_tooltip(add_button, "Bestehenden systemd-Service zur Liste hinzufügen")

assistant_button = create_button(button_frame, text="+ Assistent", width=14, command=service_assistant_window, variant="accent")
assistant_button.pack(side=tk.LEFT, padx=4)
add_tooltip(assistant_button, "Neuen systemd-Service per Assistent erstellen")

diagnostics_button = create_button(button_frame, text="Diagnose", width=14, command=show_diagnostics_window, variant="warning")
diagnostics_button.pack(side=tk.LEFT, padx=4)
add_tooltip(diagnostics_button, "System- und Serviceinformationen anzeigen")

edit_button = create_button(button_frame, text="Bearbeiten", width=14, command=edit_project_window)
edit_button.pack(side=tk.LEFT, padx=4)
add_tooltip(edit_button, "Eintrag aus der Service-Liste bearbeiten")

delete_button = create_button(button_frame, text="- Service", width=14, command=delete_project_window)
delete_button.pack(side=tk.LEFT, padx=4)
add_tooltip(delete_button, "Eintrag aus der Service-Liste entfernen")

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
