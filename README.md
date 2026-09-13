# Linux Service Center

![Python](https://img.shields.io/badge/python-3.x-blue)
![Platform](https://img.shields.io/badge/platform-Linux-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Version](https://img.shields.io/badge/version-0.10.0--rc1-B79A6A)
![Status](https://img.shields.io/badge/status-active%20development-orange)

Linux Service Center is a Linux-only service management and diagnostics tool with a modern Tkinter GUI and an interactive CLI.

It is designed primarily for Raspberry Pi OS, Debian, Ubuntu, Linux Mint and other Linux distributions using `systemd`.

> [!WARNING]
> **Development version:** `v0.10.0-rc1`
>
> This is an active development snapshot, not a stable production release. Features, UI details and internal APIs may still change.

Public repository:

https://github.com/Python-XP1/linux-service-center

---

## Features

- Modern dark-themed GUI with responsive service controls
- Interactive CLI with the same core service-management capabilities
- SYSTEM and USER service discovery
- Start / Stop / Restart services
- Enable / Disable autostart
- Add and remove saved services
- Search and filter services by status and scope
- Service details and status information
- Service favorites shared between GUI and CLI
- Service log viewer
- Local service URL shortcuts
- Auto-refresh service monitoring
- System metrics for CPU, RAM, disk and temperature
- Built-in system diagnostics
- Process Inspector with process grouping, parent-chain inspection, manager detection, systemd-unit detection, restart-policy analysis and recovery guidance
- Central fail-closed command safety classification for diagnostic suggestions
- Normal Mode / Advanced Mode separation for write operations
- D-Bus backend with `systemctl` fallback
- Direct GitHub repository shortcut and About dialog in the GUI

---

## Safety model

Read-only inspection and diagnostic features are available without Advanced Mode.

Write operations such as Start, Stop, Restart, Enable, Disable, Add and Remove require **Advanced Mode** in both GUI and CLI.

Advanced Mode validates administrator credentials with `sudo -v` and expires after five minutes of inactivity. System-scope write actions also require explicit confirmation before execution.

The Process Inspector does not automatically execute the recovery commands it suggests. Suggested commands are classified centrally as normal/read-only or Advanced, and unknown or ambiguous command forms fail closed to Advanced.

The selected service backend is D-Bus when available, with `systemctl` used as fallback.

Local runtime files such as `services.json`, `settings.json` and `favorites.json` may contain local service names, paths, URLs or preferences. Do not commit sensitive local data, passwords, API keys, tokens, private keys or diagnostic exports.

---

## Screenshots

The repository contains development screenshots used for documentation. They may lag slightly behind the latest development UI.

### Main GUI

![Linux Service Center main GUI](screenshots/main_gui.png)

### Add Service

![Add service dialog](screenshots/add_service.png)

### CLI

![Linux Service Center CLI](screenshots/cli.png)

### Diagnostics

![Diagnostics window](screenshots/diagnose.png)


---

## Requirements

- Linux with `systemd`
- Python 3
- Tkinter
- `psutil`
- Pillow for high-quality logo rendering

Pillow is optional at runtime: if it is unavailable, the GUI still starts normally and simply omits the logo.

On Debian-based systems, the recommended base packages are:

```bash
sudo apt install python3-tk python3-venv
```

---

## Installation

Clone the public repository:

```bash
git clone https://github.com/Python-XP1/linux-service-center.git
cd linux-service-center
```

A virtual environment is recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

---

## Start GUI

From the project root:

```bash
python3 -m ui.app
```

## Start CLI

From the project root:

```bash
python3 -m cli.app
```

---

## Supported systems

- Raspberry Pi OS
- Debian
- Ubuntu
- Linux Mint
- Other Linux distributions using `systemd`

Linux Service Center is not compatible with Windows.

---

## Relevant project structure

```text
linux-service-center/
├── assistant/      # backend-related helper logic
├── backends/       # D-Bus and systemctl service backends
├── cli/            # terminal interface
├── core/           # shared service, safety, auth, catalog and favorites logic
├── diagnostics/    # system diagnostics and Process Inspector
├── models/         # shared data models
├── screenshots/    # README/documentation screenshots
├── ui/             # Tkinter GUI, diagnostics window and shared theme
├── app.py
├── logo.PNG
├── requirements.txt
├── README.md
├── CHANGELOG.md
└── LICENSE.txt
```

GUI and CLI intentionally share the same core service-management, catalog, favorites and safety logic to reduce behavioral drift between interfaces.

---

## Development status

Current development version: **v0.10.0-rc1**.

The current development cycle focuses on CLI/GUI parity, safer administrative actions, Process Inspector diagnostics and a more polished desktop UI.

The latest stable release documented in the changelog remains **v0.9.4** until a new stable version is explicitly released.

---

## License

MIT License. See `LICENSE.txt`.

---

Built with ❤️ by PythonXP. Supported by AI.
