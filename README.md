# Linux Service Center

![Python](https://img.shields.io/badge/python-3.x-blue)
![Platform](https://img.shields.io/badge/platform-Linux-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Status](https://img.shields.io/badge/status-work%20in%20progress-orange)

> [!WARNING]
> ## Private development workspace: `pythonxp-lab/dev-dbus`
>
> This repository contains the **active private development state** of Linux Service Center.
>
> It is **not a finished release** and may include incomplete features, experimental code, breaking changes or bugs. Tested development snapshots are mirrored separately to the public `linux-service-center/dev-dbus` branch.

Manage Linux services from a modern GUI or directly from a terminal interface.

Built for Raspberry Pi, Debian, Ubuntu and other Linux distributions.

⚠️ Linux only

This application requires `systemd` and is not compatible with Windows.

⚠️ Linux Service Center is an early-stage home lab project built for personal Raspberry Pi setups. It is not intended as a production-ready server management solution.

## Security note

System services are executed through `sudo`.

Whether a password is requested depends on your local `sudoers` configuration.

If your user has `NOPASSWD` privileges, no password prompt will appear.

Local runtime files such as `services.json`, `settings.json` and `favorites.json` are intentionally excluded from Git. They may contain local service names, paths, URLs or user preferences and should not be committed.

Never commit passwords, API keys, private keys, access tokens or local diagnostic exports.

Before mirroring changes to the public repository, also check screenshots for hostnames, IP addresses, local paths and personal service information.

Powered by PythonXP.

---

## Features

- Modern dark themed GUI
- Interactive CLI mode
- Start / Stop / Restart services
- Enable / Disable autostart
- View service logs
- Built-in diagnostics
- Add and remove custom services
- Search installed systemd services
- Resource monitoring (CPU, RAM, Temperature, Disk)
- Local URL shortcuts
- Lightweight and beginner friendly

---

## Screenshots

Private development screenshots may exist in this workspace for local testing and documentation.

They must not be mirrored to the public repository until hostnames, IP addresses, paths and personal service information have been removed.

Sanitized screenshots will be added before the next stable public release.

---

## Installation

Clone the public repository:

```bash
git clone https://github.com/Python-XP1/linux-service-center.git

cd Linux-Service-Center
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Start GUI

```bash
python -m ui.app
```

## Start CLI

```bash
python -m cli.app
```

---

## Supported Systems

- Raspberry Pi OS
- Debian
- Ubuntu
- Linux Mint
- Other Linux distributions using systemd

---

## Project Structure

```text
Linux-Service-Center/

assistant/
backends/
cli/
core/
diagnostics/
legacy/
models/
monitoring/
ui/
utils/

README.md
ROADMAP.md
SESSION_HANDOVER.md
LICENSE.txt
CHANGELOG.md
```

---

## Project Status

Linux Service Center is currently under active development.

The private `pythonxp-lab/dev-dbus` branch is the development source of truth. Tested snapshots are pushed to the public `linux-service-center/dev-dbus` branch, while stable releases remain on public `main`.

The project focuses on providing a simple, modern and beginner-friendly interface for managing Linux services on Raspberry Pi and Debian-based systems.

Built with ❤️ by PythonXP.