import tkinter as tk
from tkinter import scrolledtext, messagebox
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "services.json")
COMMAND_TIMEOUT = 10

# Accept only systemd service unit names, never command-like arguments.
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")

# Tkinter variables are initialized after the root window exists.
search_var = None

# Error caches prevent repeated auto-refresh popups for the same issue.
last_config_error = None
last_runtime_errors = set()


def load_services():
    """Load and normalize the service configuration from disk."""
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
        # Keep the rest of the app working even if JSON values are not strings.
        services.append({
            "name": str(item.get("name", "")).strip(),
            "service": str(item.get("service", "")).strip(),
            "path": str(item.get("path", "")).strip(),
            "url": str(item.get("url", "")).strip(),
        })
    return services


def save_services(services):
    """Write services.json atomically so a crash cannot leave a half-written file."""
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
    """Run a short-lived command and return stdout/stderr as strings."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT)
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", f"Befehl nach {COMMAND_TIMEOUT}s abgebrochen: {' '.join(cmd)}"
    except Exception as e:
        return "", str(e)


def show_error(title, message):
    """Show a GUI error when possible and always mirror it to stdout."""
    try:
        if tk._default_root:
            messagebox.showerror(title, message)
    except tk.TclError:
        pass
    print(f"{title}: {message}")


def report_config_error(message):
    """Report configuration errors once until the file is readable again."""
    global last_config_error
    if message == last_config_error:
        return
    last_config_error = message
    show_error("Konfiguration fehlerhaft", message)


def report_runtime_error(key, title, message):
    """Report recurring runtime errors once per error key."""
    if key in last_runtime_errors:
        return
    last_runtime_errors.add(key)
    show_error(title, message)


def is_valid_service_name(service):
    """Return True for safe systemd .service unit names."""
    return bool(service and SERVICE_NAME_RE.fullmatch(service) and not service.startswith("-"))


def is_valid_url(url):
    """Allow only browser-openable HTTP(S) URLs."""
    if not url:
        return True
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_path(path):
    """Expand user input to an absolute local filesystem path."""
    if not path:
        return ""
    return os.path.abspath(os.path.expanduser(path))


def validate_service_config(item):
    """Validate one service entry before it is persisted or used."""
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
    """Run blocking work off the Tkinter thread and deliver the result safely."""
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


def run_systemctl_action(action, service):
    """Execute privileged systemctl changes with a strict timeout."""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, service],
            capture_output=True,
            text=True,
            timeout=30
        )
        message = result.stderr.strip() or result.stdout.strip()
        return result.returncode == 0, message
    except subprocess.TimeoutExpired:
        return False, "systemctl hat nach 30 Sekunden nicht geantwortet."
    except OSError as e:
        return False, str(e)


def get_status(service):
    """Read the active/inactive/failed state of a service."""
    if not is_valid_service_name(service):
        return "invalid"
    out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"


def get_enabled_status(service):
    """Read whether a service is enabled for autostart."""
    if not is_valid_service_name(service):
        return "invalid"
    out, _ = run_cmd(["systemctl", "is-enabled", service])
    return out if out else "unknown"


def get_uptime(service):
    """Return a compact uptime string for active services."""
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
    """Return current CPU usage for the dashboard."""
    try:
        return f"{psutil.cpu_percent(interval=0.1):.1f}%"
    except (psutil.Error, OSError) as e:
        report_runtime_error("cpu", "Systeminfo Fehler", f"CPU-Auslastung konnte nicht gelesen werden:\n{e}")
        return "N/A"


def get_ram_usage():
    """Return current RAM usage for the dashboard."""
    try:
        return f"{psutil.virtual_memory().percent:.1f}%"
    except (psutil.Error, OSError) as e:
        report_runtime_error("ram", "Systeminfo Fehler", f"RAM-Auslastung konnte nicht gelesen werden:\n{e}")
        return "N/A"


def get_temperature():
    """Return Raspberry Pi temperature when vcgencmd is available."""
    if not shutil.which("vcgencmd"):
        return "N/A"
    out, _ = run_cmd(["vcgencmd", "measure_temp"])
    try:
        return out.split("=")[1]
    except IndexError:
        return "N/A"


def get_disk_free():
    """Return free space on the root filesystem."""
    try:
        disk = psutil.disk_usage("/")
        return f"{disk.free / (1024 ** 3):.1f} GB"
    except (psutil.Error, OSError) as e:
        report_runtime_error("disk", "Systeminfo Fehler", f"Freier Speicher konnte nicht gelesen werden:\n{e}")
        return "N/A"


def control_service(action, service):
    """Start, stop, or restart a service without freezing the UI."""
    if action not in {"start", "stop", "restart"} or not is_valid_service_name(service):
        messagebox.showerror("Ungültige Aktion", "Service oder Aktion ist ungültig.")
        return

    def task():
        return run_systemctl_action(action, service)

    def done(result):
        # The background worker returns either an exception or (success, message).
        if isinstance(result, Exception):
            messagebox.showerror("systemctl Fehler", str(result))
        elif not result[0]:
            messagebox.showerror("systemctl Fehler", result[1] or "Aktion fehlgeschlagen.")
        refresh_services()

    run_background(task, done)


def control_autostart(action, service):
    """Enable or disable service autostart without blocking Tkinter."""
    if action not in {"enable", "disable"} or not is_valid_service_name(service):
        messagebox.showerror("Ungültige Aktion", "Service oder Aktion ist ungültig.")
        return

    def task():
        return run_systemctl_action(action, service)

    def done(result):
        # Always refresh after the command so the UI reflects the real system state.
        if isinstance(result, Exception):
            messagebox.showerror("systemctl Fehler", str(result))
        elif not result[0]:
            messagebox.showerror("systemctl Fehler", result[1] or "Aktion fehlgeschlagen.")
        refresh_services()

    run_background(task, done)


def open_url(url):
    """Open a configured service URL with the desktop default browser."""
    if url and is_valid_url(url):
        try:
            subprocess.Popen(["xdg-open", url])
            return
        except OSError as e:
            messagebox.showerror("URL öffnen fehlgeschlagen", str(e))
            return
    messagebox.showwarning("URL ungültig", "Keine gültige http(s)-URL hinterlegt.")


def open_folder(path):
    """Open a configured project folder with the desktop file manager."""
    safe_path = normalize_path(path)
    if safe_path and os.path.isdir(safe_path):
        try:
            subprocess.Popen(["xdg-open", safe_path])
        except OSError as e:
            messagebox.showerror("Ordner öffnen fehlgeschlagen", str(e))
    else:
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")


def open_code(path):
    """Open a configured project folder in VS Code."""
    safe_path = normalize_path(path)
    if not safe_path or not os.path.isdir(safe_path):
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")
        return

    try:
        subprocess.Popen(
            ["/usr/bin/code", safe_path],
            cwd=safe_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        messagebox.showerror("VS Code Fehler", str(e))


def show_logs(service):
    """Display the latest journalctl lines for one service."""
    if not is_valid_service_name(service):
        messagebox.showerror("Ungültiger Service", "Der Service-Name ist ungültig.")
        return
    out, err = run_cmd(["journalctl", "-u", service, "-n", "120", "--no-pager"])

    win = tk.Toplevel(root)
    win.title(f"Logs: {service}")
    win.geometry("950x540")
    win.configure(bg="#121212")

    text = scrolledtext.ScrolledText(
        win,
        wrap=tk.WORD,
        bg="#0f0f0f",
        fg="#dddddd",
        insertbackground="white"
    )
    text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    text.insert(tk.END, out if out else err)
    text.config(state=tk.DISABLED)


def browse_services(target_entry):
    """Show installed systemd services and copy the selection into an entry."""
    win = tk.Toplevel(root)
    win.title("Systemd Services durchsuchen")
    win.geometry("720x520")
    win.configure(bg="#121212")

    tk.Label(
        win,
        text="Doppelklick auf einen Service zum Übernehmen",
        fg="white",
        bg="#121212",
        font=("Arial", 11, "bold")
    ).pack(pady=10)

    search_entry = tk.Entry(win, width=70)
    search_entry.pack(padx=10, pady=5)

    listbox = tk.Listbox(win, bg="#1e1e1e", fg="white", width=85)
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    out, err = run_cmd(["systemctl", "list-unit-files", "--type=service", "--no-legend"])
    if err and not out:
        messagebox.showwarning("Services laden", err)

    # systemctl prints columns; the first token is the unit name.
    all_services = sorted([line.split()[0] for line in out.splitlines() if line.strip()])

    def fill_list(filter_text=""):
        """Filter the service list as the user types."""
        listbox.delete(0, tk.END)
        for service in all_services:
            if filter_text.lower() in service.lower():
                listbox.insert(tk.END, service)

    def select_service(event=None):
        """Copy the chosen service name back into the form."""
        selection = listbox.curselection()
        if not selection:
            return
        service = listbox.get(selection[0])
        target_entry.delete(0, tk.END)
        target_entry.insert(0, service)
        win.destroy()

    search_entry.bind("<KeyRelease>", lambda e: fill_list(search_entry.get()))
    listbox.bind("<Double-Button-1>", select_service)

    tk.Button(win, text="Übernehmen", command=select_service).pack(pady=10)
    fill_list()


def project_form(title_text, existing=None, index=None):
    """Create the add/edit service dialog."""
    win = tk.Toplevel(root)
    win.title(title_text)
    win.geometry("520x430")
    win.configure(bg="#121212")

    fields = {}

    tk.Label(win, text="Anzeigename", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    fields["name"] = tk.Entry(win, width=60)
    fields["name"].pack(padx=20, pady=3)
    fields["name"].insert(0, existing.get("name", "") if existing else "")

    tk.Label(win, text="Systemd Service", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    fields["service"] = tk.Entry(win, width=60)
    fields["service"].pack(padx=20, pady=3)
    fields["service"].insert(0, existing.get("service", "") if existing else "")

    tk.Label(
        win,
        text="Beispiel: ssh.service, code-server.service, bluetooth.service",
        fg="#888888",
        bg="#121212",
        font=("Arial", 9)
    ).pack(anchor="w", padx=20)

    tk.Button(
        win,
        text="Services durchsuchen",
        width=22,
        command=lambda: browse_services(fields["service"])
    ).pack(pady=6)

    tk.Label(win, text="Ordner/Pfad optional", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    fields["path"] = tk.Entry(win, width=60)
    fields["path"].pack(padx=20, pady=3)
    fields["path"].insert(0, existing.get("path", "") if existing else "")

    tk.Label(win, text="URL optional", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    fields["url"] = tk.Entry(win, width=60)
    fields["url"].pack(padx=20, pady=3)
    fields["url"].insert(0, existing.get("url", "") if existing else "")

    def save_project():
        """Validate and persist the dialog contents."""
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

    tk.Button(win, text="Speichern", width=18, command=save_project).pack(pady=18)


def add_project_window():
    """Open the dialog for a new service entry."""
    project_form("Service hinzufügen")


def edit_service_by_index(index):
    """Open the edit dialog for the service at the given config index."""
    services = load_services()
    if 0 <= index < len(services):
        project_form("Service bearbeiten", services[index], index)


def edit_project_window():
    """Let the user choose a configured service to edit."""
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Service bearbeiten")
    win.geometry("430x270")
    win.configure(bg="#121212")

    listbox = tk.Listbox(win, width=46)
    listbox.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def edit_selected(event=None):
        """Open the edit dialog for the currently selected list item."""
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        win.destroy()
        edit_service_by_index(index)

    listbox.bind("<Double-Button-1>", edit_selected)
    tk.Button(win, text="Bearbeiten", width=18, command=edit_selected).pack(pady=10)


def delete_project_window():
    """Let the user remove a service entry from services.json."""
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Service entfernen")
    win.geometry("430x270")
    win.configure(bg="#121212")

    listbox = tk.Listbox(win, width=46)
    listbox.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def delete_selected():
        """Confirm and remove the selected service from the config file."""
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

    tk.Button(win, text="Entfernen", width=18, command=delete_selected).pack(pady=10)


def create_info_card(parent, title, value, color):
    """Create one compact system information card."""
    frame = tk.Frame(parent, bg="#1e1e1e", padx=18, pady=8)
    frame.pack(side=tk.LEFT, padx=8)

    tk.Label(frame, text=title, fg="#aaaaaa", bg="#1e1e1e", font=("Arial", 9, "bold")).pack()

    value_label = tk.Label(frame, text=value, fg=color, bg="#1e1e1e", font=("Arial", 13, "bold"))
    value_label.pack()

    return value_label


def add_header():
    """Render the fixed table header above the service rows."""
    header = tk.Frame(service_frame, bg="#2a2a2a")
    header.pack(fill=tk.X, padx=12, pady=(10, 5))

    for text, width in [
        ("Service", 20),
        ("Status", 10),
        ("Autostart", 11),
        ("Uptime", 8),
        ("Aktionen", 70)
    ]:
        tk.Label(header, text=text, fg="#dddddd", bg="#2a2a2a", font=("Arial", 10, "bold"), anchor="w", width=width).pack(side=tk.LEFT, padx=5)


def refresh_services():
    """Rebuild the service table from the current configuration and system state."""
    try:
        for widget in service_frame.winfo_children():
            widget.destroy()

        add_header()
        services = load_services()
        filter_text = search_var.get().lower() if search_var else ""

        for index, item in enumerate(services):
            name = item.get("name", "Unbenannt")
            service = item.get("service", "")
            path = item.get("path", "")
            url = item.get("url", "")

            if filter_text and filter_text not in name.lower() and filter_text not in service.lower():
                continue

            status = get_status(service)
            enabled = get_enabled_status(service)
            uptime = get_uptime(service) if status == "active" else "-"

            # Use row color as a quick visual signal for the service state.
            status_color = "#888888"
            row_bg = "#1e1e1e"

            if status == "active":
                status_color = "#25c26e"
                row_bg = "#1f2a24"
            elif status == "inactive":
                status_color = "#e04f5f"
                row_bg = "#2a1f22"
            elif status == "failed":
                status_color = "#ffaa33"
                row_bg = "#2a261f"

            enabled_color = "#888888"
            enabled_text = enabled

            if enabled == "enabled":
                enabled_color = "#25c26e"
                enabled_text = "an"
            elif enabled == "disabled":
                enabled_color = "#e04f5f"
                enabled_text = "aus"

            row = tk.Frame(service_frame, bg=row_bg)
            row.pack(fill=tk.X, padx=12, pady=6)
            row.bind("<Double-Button-1>", lambda e, i=index: edit_service_by_index(i))

            tk.Label(row, text=f"●  {name}", fg=status_color, bg=row_bg, font=("Arial", 13, "bold"), anchor="w", width=20).pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=status, fg="#cccccc", bg=row_bg, font=("Arial", 11), anchor="w", width=10).pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=enabled_text, fg=enabled_color, bg=row_bg, font=("Arial", 11, "bold"), anchor="w", width=11).pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=uptime, fg="#cccccc", bg=row_bg, font=("Arial", 11), anchor="w", width=8).pack(side=tk.LEFT, padx=5)

            tk.Button(row, text="Start", width=7, command=lambda s=service: control_service("start", s)).pack(side=tk.LEFT, padx=2)
            tk.Button(row, text="Stop", width=7, command=lambda s=service: control_service("stop", s)).pack(side=tk.LEFT, padx=2)
            tk.Button(row, text="Restart", width=8, command=lambda s=service: control_service("restart", s)).pack(side=tk.LEFT, padx=2)
            tk.Button(row, text="Logs", width=7, command=lambda s=service: show_logs(s)).pack(side=tk.LEFT, padx=2)
            tk.Button(row, text="Auto an", width=8, command=lambda s=service: control_autostart("enable", s)).pack(side=tk.LEFT, padx=2)
            tk.Button(row, text="Auto aus", width=8, command=lambda s=service: control_autostart("disable", s)).pack(side=tk.LEFT, padx=2)

            if url:
                tk.Button(row, text="URL", width=7, command=lambda u=url: open_url(u)).pack(side=tk.LEFT, padx=2)

            if path:
                tk.Button(row, text="Ordner", width=7, command=lambda p=path: open_folder(p)).pack(side=tk.LEFT, padx=2)
                tk.Button(row, text="Code", width=7, command=lambda p=path: open_code(p)).pack(side=tk.LEFT, padx=2)
    except Exception as e:
        report_runtime_error("refresh", "Aktualisieren fehlgeschlagen", str(e))


def auto_refresh_services():
    """Refresh service rows regularly while keeping the timer alive after errors."""
    try:
        refresh_services()
    finally:
        try:
            root.after(5000, auto_refresh_services)
        except tk.TclError:
            pass


def update_system_info():
    """Refresh dashboard metrics and reschedule itself."""
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
root.title("PythonXP Service Control")
root.geometry("1420x700")
root.configure(bg="#121212")

info_frame = tk.Frame(root, bg="#121212")
info_frame.pack(fill=tk.X, padx=20, pady=12)

cpu_value = create_info_card(info_frame, "CPU", "0.0%", "#25c26e")
ram_value = create_info_card(info_frame, "RAM", "0.0%", "#4ea3ff")
temp_value = create_info_card(info_frame, "TEMP", "N/A", "#ffaa33")
disk_value = create_info_card(info_frame, "SSD FREI", "N/A", "#dddddd")

title = tk.Label(root, text="PythonXP Service Control", fg="#ffffff", bg="#121212", font=("Arial", 24, "bold"))
title.pack(pady=8)

search_var = tk.StringVar()
search_entry = tk.Entry(root, textvariable=search_var, width=45)
search_entry.pack(pady=5)
search_entry.insert(0, "")
search_entry.bind("<KeyRelease>", lambda e: refresh_services())

service_frame = tk.Frame(root, bg="#1e1e1e")
service_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

button_frame = tk.Frame(root, bg="#121212")
button_frame.pack(pady=12)

tk.Button(button_frame, text="Aktualisieren", width=16, command=refresh_services).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="+ Service", width=14, command=add_project_window).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Bearbeiten", width=14, command=edit_project_window).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="- Service", width=14, command=delete_project_window).pack(side=tk.LEFT, padx=5)

refresh_services()
update_system_info()
auto_refresh_services()

root.mainloop()
