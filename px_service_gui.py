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


def open_folder(path):
    if path and os.path.exists(path):
        subprocess.Popen(["xdg-open", path])
    else:
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")


def open_url(url):
    if url:
        subprocess.Popen(["xdg-open", url])
    else:
        messagebox.showwarning("URL fehlt", "Keine URL hinterlegt.")


def open_code(path):
    if path and os.path.exists(path):
        subprocess.Popen(["code", path])
    else:
        messagebox.showwarning("Pfad fehlt", "Projektordner nicht gefunden.")


def show_logs(service):
    out, err = run_cmd(["journalctl", "-u", service, "-n", "100", "--no-pager"])

    log_window = tk.Toplevel(root)
    log_window.title(f"Logs: {service}")
    log_window.geometry("900x520")
    log_window.configure(bg="#121212")

    text = scrolledtext.ScrolledText(
        log_window,
        wrap=tk.WORD,
        bg="#0f0f0f",
        fg="#dddddd",
        insertbackground="white"
    )
    text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    text.insert(tk.END, out if out else err)
    text.config(state=tk.DISABLED)


def project_form(title_text, existing=None, index=None):
    win = tk.Toplevel(root)
    win.title(title_text)
    win.geometry("460x340")
    win.configure(bg="#121212")

    fields = {}

    labels = [
        ("name", "Name"),
        ("service", "Service"),
        ("path", "Pfad"),
        ("url", "URL")
    ]

    for key, label in labels:
        tk.Label(win, text=label, fg="white", bg="#121212").pack(anchor="w", padx=20, pady=(10, 0))
        entry = tk.Entry(win, width=55)
        entry.pack(padx=20, pady=3)
        entry.insert(0, existing.get(key, "") if existing else "")
        fields[key] = entry

    def save_project():
        services = load_services()

        item = {
            "name": fields["name"].get().strip(),
            "service": fields["service"].get().strip(),
            "path": fields["path"].get().strip(),
            "url": fields["url"].get().strip()
        }

        if not item["name"] or not item["service"]:
            messagebox.showwarning("Fehlt noch was", "Name und Service müssen ausgefüllt sein.")
            return

        if index is None:
            services.append(item)
        else:
            services[index] = item

        save_services(services)
        refresh_services()
        win.destroy()

    tk.Button(win, text="Speichern", command=save_project).pack(pady=18)


def add_project_window():
    project_form("Projekt hinzufügen")


def edit_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Projekt bearbeiten")
    win.geometry("420x260")
    win.configure(bg="#121212")

    tk.Label(win, text="Projekt auswählen:", fg="white", bg="#121212", font=("Arial", 12, "bold")).pack(pady=10)

    listbox = tk.Listbox(win, width=45)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def edit_selected():
        selection = listbox.curselection()
        if not selection:
            return

        index = selection[0]
        win.destroy()
        project_form("Projekt bearbeiten", services[index], index)

    tk.Button(win, text="Bearbeiten", command=edit_selected).pack(pady=10)


def delete_project_window():
    services = load_services()

    win = tk.Toplevel(root)
    win.title("Projekt entfernen")
    win.geometry("420x260")
    win.configure(bg="#121212")

    tk.Label(win, text="Projekt auswählen:", fg="white", bg="#121212", font=("Arial", 12, "bold")).pack(pady=10)

    listbox = tk.Listbox(win, width=45)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

    for item in services:
        listbox.insert(tk.END, item.get("name", "Unbenannt"))

    def delete_selected():
        selection = listbox.curselection()
        if not selection:
            return

        index = selection[0]
        name = services[index].get("name", "Unbenannt")

        if messagebox.askyesno("Entfernen", f"{name} wirklich entfernen?"):
            services.pop(index)
            save_services(services)
            refresh_services()
            win.destroy()

    tk.Button(win, text="Entfernen", command=delete_selected).pack(pady=10)


def create_info_card(parent, title, value, color):
    frame = tk.Frame(parent, bg="#1e1e1e", padx=18, pady=8)
    frame.pack(side=tk.LEFT, padx=8)

    label_title = tk.Label(frame, text=title, fg="#aaaaaa", bg="#1e1e1e", font=("Arial", 9, "bold"))
    label_title.pack()

    label_value = tk.Label(frame, text=value, fg=color, bg="#1e1e1e", font=("Arial", 13, "bold"))
    label_value.pack()

    return label_value


def refresh_services():
    for widget in service_frame.winfo_children():
        widget.destroy()

    services = load_services()

    for item in services:
        name = item.get("name", "Unbenannt")
        service = item.get("service", "")
        path = item.get("path", "")
        url = item.get("url", "")

        status = get_status(service)

        if status == "active":
            color = "#25c26e"
        elif status == "inactive":
            color = "#e04f5f"
        elif status == "failed":
            color = "#ffaa33"
        else:
            color = "#888888"

        row = tk.Frame(service_frame, bg="#1e1e1e")
        row.pack(fill=tk.X, padx=12, pady=7)

        tk.Label(
            row,
            text=f"●  {name}",
            fg=color,
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
            width=10
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(row, text="Start", width=8, command=lambda s=service: control_service("start", s)).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="Stop", width=8, command=lambda s=service: control_service("stop", s)).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="Restart", width=8, command=lambda s=service: control_service("restart", s)).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="Logs", width=8, command=lambda s=service: show_logs(s)).pack(side=tk.LEFT, padx=3)

        if url:
            tk.Button(row, text="Öffnen", width=8, command=lambda u=url: open_url(u)).pack(side=tk.LEFT, padx=3)

        if path:
            tk.Button(row, text="Ordner", width=8, command=lambda p=path: open_folder(p)).pack(side=tk.LEFT, padx=3)
            tk.Button(row, text="Code", width=8, command=lambda p=path: open_code(p)).pack(side=tk.LEFT, padx=3)


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
root.title("PythonXP Control Center")
root.geometry("1180x620")
root.configure(bg="#121212")

info_frame = tk.Frame(root, bg="#121212")
info_frame.pack(fill=tk.X, padx=20, pady=12)

cpu_value = create_info_card(info_frame, "CPU", "0.0%", "#25c26e")
ram_value = create_info_card(info_frame, "RAM", "0.0%", "#4ea3ff")
temp_value = create_info_card(info_frame, "TEMP", "N/A", "#ffaa33")
disk_value = create_info_card(info_frame, "SSD FREI", "N/A", "#dddddd")

title = tk.Label(
    root,
    text="PythonXP Control Center",
    fg="#ffffff",
    bg="#121212",
    font=("Arial", 24, "bold")
)
title.pack(pady=10)

service_frame = tk.Frame(root, bg="#1e1e1e")
service_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

button_frame = tk.Frame(root, bg="#121212")
button_frame.pack(pady=12)

tk.Button(button_frame, text="Status aktualisieren", command=refresh_services).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="+ Projekt", command=add_project_window).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Bearbeiten", command=edit_project_window).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="- Projekt", command=delete_project_window).pack(side=tk.LEFT, padx=5)

refresh_services()
update_system_info()
auto_refresh_services()

root.mainloop()