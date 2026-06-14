import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import json
import os
import psutil

CONFIG_FILE = "services.json"


def load_services():
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_services(services):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(services, f, indent=4, ensure_ascii=False)


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)


def get_status(service):
    out, _ = run_cmd(["systemctl", "is-active", service])
    return out if out else "unknown"


def get_enabled_status(service):
    out, _ = run_cmd(["systemctl", "is-enabled", service])
    return out if out else "unknown"


def get_cpu_usage():
    return f"{psutil.cpu_percent(interval=0.1):.1f}%"


def get_ram_usage():
    return f"{psutil.virtual_memory().percent:.1f}%"


def get_temperature():
    out, _ = run_cmd(["vcgencmd", "measure_temp"])
    try:
        return out.split("=")[1]
    except:
        return "N/A"


def get_disk_free():
    disk = psutil.disk_usage("/")
    return f"{disk.free / (1024 ** 3):.1f} GB"


def control_service(action, service):
    subprocess.run(["sudo", "systemctl", action, service])
    refresh_services()


def control_autostart(action, service):
    subprocess.run(["sudo", "systemctl", action, service])
    refresh_services()


def open_url(url):
    if url:
        subprocess.Popen(["xdg-open", url])
    else:
        messagebox.showwarning("URL fehlt", "Keine URL hinterlegt.")


def open_folder(path):
    if path and os.path.exists(path):
        subprocess.Popen(["xdg-open", path])
    else:
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")


def open_code(path):
    if not path or not os.path.exists(path):
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")
        return

    try:
        subprocess.Popen(
            ["/usr/bin/code", path],
            cwd=path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        messagebox.showerror("VS Code Fehler", str(e))


def show_logs(service):
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

    listbox = tk.Listbox(
        win,
        bg="#1e1e1e",
        fg="white",
        width=85
    )
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    result = subprocess.run(
        ["systemctl", "list-unit-files", "--type=service", "--no-legend"],
        capture_output=True,
        text=True
    )

    all_services = []

    for line in result.stdout.splitlines():
        if line.strip():
            service = line.split()[0]
            all_services.append(service)

    all_services.sort()

    def fill_list(filter_text=""):
        listbox.delete(0, tk.END)

        for service in all_services:
            if filter_text.lower() in service.lower():
                listbox.insert(tk.END, service)

    def filter_services(event=None):
        fill_list(search_entry.get())

    def select_service(event=None):
        selection = listbox.curselection()
        if not selection:
            return

        service = listbox.get(selection[0])
        target_entry.delete(0, tk.END)
        target_entry.insert(0, service)
        win.destroy()

    search_entry.bind("<KeyRelease>", filter_services)
    listbox.bind("<Double-Button-1>", select_service)

    tk.Button(win, text="Übernehmen", command=select_service).pack(pady=10)

    fill_list()


def project_form(title_text, existing=None, index=None):
    win = tk.Toplevel(root)
    win.title(title_text)
    win.geometry("520x430")
    win.configure(bg="#121212")

    fields = {}

    tk.Label(win, text="Anzeigename", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    name_entry = tk.Entry(win, width=60)
    name_entry.pack(padx=20, pady=3)
    name_entry.insert(0, existing.get("name", "") if existing else "")
    fields["name"] = name_entry

    tk.Label(win, text="Systemd Service", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    service_entry = tk.Entry(win, width=60)
    service_entry.pack(padx=20, pady=3)
    service_entry.insert(0, existing.get("service", "") if existing else "")
    fields["service"] = service_entry

    tk.Label(
        win,
        text="Beispiel: ssh.service, code-server.service, nginx.service",
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
    path_entry = tk.Entry(win, width=60)
    path_entry.pack(padx=20, pady=3)
    path_entry.insert(0, existing.get("path", "") if existing else "")
    fields["path"] = path_entry

    tk.Label(
        win,
        text="Optional: Projektordner für Ordner- und Code-Button",
        fg="#888888",
        bg="#121212",
        font=("Arial", 9)
    ).pack(anchor="w", padx=20)

    tk.Label(win, text="URL optional", fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
    url_entry = tk.Entry(win, width=60)
    url_entry.pack(padx=20, pady=3)
    url_entry.insert(0, existing.get("url", "") if existing else "")
    fields["url"] = url_entry

    tk.Label(
        win,
        text="Optional: z.B. http://127.0.0.1:5050",
        fg="#888888",
        bg="#121212",
        font=("Arial", 9)
    ).pack(anchor="w", padx=20)

    def save_project():
        services = load_services()

        item = {
            "name": fields["name"].get().strip(),
            "service": fields["service"].get().strip(),
            "path": fields["path"].get().strip(),
            "url": fields["url"].get().strip()
        }

        if not item["name"] or not item["service"]:
            messagebox.showwarning("Fehlt noch was", "Anzeigename und Systemd Service müssen ausgefüllt sein.")
            return

        if index is None:
            services.append(item)
        else:
            services[index] = item

        save_services(services)
        refresh_services()
        win.destroy()

    tk.Button(win, text="Speichern", width=18, command=save_project).pack(pady=18)


def add_project_window():
    project_form("Service hinzufügen")


def edit_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Service bearbeiten")
    win.geometry("430x270")
    win.configure(bg="#121212")

    tk.Label(win, text="Service auswählen:", fg="white", bg="#121212", font=("Arial", 12, "bold")).pack(pady=10)

    listbox = tk.Listbox(win, width=46)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def edit_selected():
        selection = listbox.curselection()
        if not selection:
            return

        index = selection[0]
        win.destroy()
        project_form("Service bearbeiten", services[index], index)

    tk.Button(win, text="Bearbeiten", width=18, command=edit_selected).pack(pady=10)


def delete_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Service entfernen")
    win.geometry("430x270")
    win.configure(bg="#121212")

    tk.Label(win, text="Service auswählen:", fg="white", bg="#121212", font=("Arial", 12, "bold")).pack(pady=10)

    listbox = tk.Listbox(win, width=46)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def delete_selected():
        selection = listbox.curselection()
        if not selection:
            return

        index = selection[0]
        name = services[index].get("name", "Unbenannt")

        if messagebox.askyesno("Entfernen", f"{name} wirklich aus der Liste entfernen?"):
            services.pop(index)
            save_services(services)
            refresh_services()
            win.destroy()

    tk.Button(win, text="Entfernen", width=18, command=delete_selected).pack(pady=10)


def create_info_card(parent, title, value, color):
    frame = tk.Frame(parent, bg="#1e1e1e", padx=18, pady=8)
    frame.pack(side=tk.LEFT, padx=8)

    tk.Label(frame, text=title, fg="#aaaaaa", bg="#1e1e1e", font=("Arial", 9, "bold")).pack()

    value_label = tk.Label(frame, text=value, fg=color, bg="#1e1e1e", font=("Arial", 13, "bold"))
    value_label.pack()

    return value_label


def add_header():
    header = tk.Frame(service_frame, bg="#2a2a2a")
    header.pack(fill=tk.X, padx=12, pady=(10, 5))

    labels = [
        ("Service", 20),
        ("Status", 10),
        ("Autostart", 11),
        ("Aktionen", 70)
    ]

    for text, width in labels:
        tk.Label(
            header,
            text=text,
            fg="#dddddd",
            bg="#2a2a2a",
            font=("Arial", 10, "bold"),
            anchor="w",
            width=width
        ).pack(side=tk.LEFT, padx=5)


def refresh_services():
    for widget in service_frame.winfo_children():
        widget.destroy()

    add_header()
    services = load_services()

    for item in services:
        name = item.get("name", "Unbenannt")
        service = item.get("service", "")
        path = item.get("path", "")
        url = item.get("url", "")

        status = get_status(service)
        enabled = get_enabled_status(service)

        status_color = "#888888"
        if status == "active":
            status_color = "#25c26e"
        elif status == "inactive":
            status_color = "#e04f5f"
        elif status == "failed":
            status_color = "#ffaa33"

        enabled_color = "#888888"
        enabled_text = enabled

        if enabled == "enabled":
            enabled_color = "#25c26e"
            enabled_text = "an"
        elif enabled == "disabled":
            enabled_color = "#e04f5f"
            enabled_text = "aus"

        row = tk.Frame(service_frame, bg="#1e1e1e")
        row.pack(fill=tk.X, padx=12, pady=6)

        tk.Label(
            row,
            text=f"●  {name}",
            fg=status_color,
            bg="#1e1e1e",
            font=("Arial", 13, "bold"),
            anchor="w",
            width=20
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            row,
            text=status,
            fg="#cccccc",
            bg="#1e1e1e",
            font=("Arial", 11),
            anchor="w",
            width=10
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            row,
            text=enabled_text,
            fg=enabled_color,
            bg="#1e1e1e",
            font=("Arial", 11, "bold"),
            anchor="w",
            width=11
        ).pack(side=tk.LEFT, padx=5)

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


def auto_refresh_services():
    refresh_services()
    root.after(5000, auto_refresh_services)


def update_system_info():
    cpu_value.config(text=get_cpu_usage())
    ram_value.config(text=get_ram_usage())
    temp_value.config(text=get_temperature())
    disk_value.config(text=get_disk_free())

    root.after(3000, update_system_info)


root = tk.Tk()
root.title("PythonXP Service Control")
root.geometry("1360x680")
root.configure(bg="#121212")

info_frame = tk.Frame(root, bg="#121212")
info_frame.pack(fill=tk.X, padx=20, pady=12)

cpu_value = create_info_card(info_frame, "CPU", "0.0%", "#25c26e")
ram_value = create_info_card(info_frame, "RAM", "0.0%", "#4ea3ff")
temp_value = create_info_card(info_frame, "TEMP", "N/A", "#ffaa33")
disk_value = create_info_card(info_frame, "SSD FREI", "N/A", "#dddddd")

title = tk.Label(
    root,
    text="PythonXP Service Control",
    fg="#ffffff",
    bg="#121212",
    font=("Arial", 24, "bold")
)
title.pack(pady=8)

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