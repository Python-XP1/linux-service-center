# Changelog

## 0.9.4 - 2026-06-19

### Added

- Support for both SYSTEM and USER services.
- User Service creation directly from the Service Assistant.
- Service type selection (User recommended / System advanced).
- Unified browser for installed services.
- Additional CLI actions (Open URL, Open Folder, Open in VS Code).
- Safety confirmations before executing system-level actions.

### Improved

- GUI and CLI now share the same service management logic.
- Service Assistant automatically recommends USER services for projects inside the home directory.
- Folder selection workflow has been redesigned.
- Improved automatic service scope detection.
- Improved service status, startup and uptime handling.
- Improved compatibility with existing services.
- Better handling of invalid or incomplete service entries.
- Updated `.gitignore` rules for local configuration files.

### Fixed

- Fixed incorrect folder selection in Service Assistant.
- Fixed Service Assistant losing focus after closing the folder picker.
- Fixed CLI crashes caused by command handling inconsistencies.
- Fixed several edge cases when reading service information.
- Fixed synchronization issues between GUI and CLI behavior.

### Security

- Added warnings before executing critical system actions.
- Improved separation between SYSTEM and USER service operations.
- USER services never require elevated privileges.

---

**Linux Service Center v0.9.4**

This release focuses on improving reliability, consistency and usability between the GUI and CLI versions.

The Service Assistant has been refined, USER services are now easier to create and manage, and several internal improvements have been made to provide a more predictable experience when working with multiple self-hosted projects and services.