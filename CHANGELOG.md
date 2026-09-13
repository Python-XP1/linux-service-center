# Changelog

## 0.10.0-dev - 2026-09-13

_Development snapshot. This is not yet a stable release._

### Added

- Integrated the Process Inspector into the main CLI as a dedicated menu entry.
- Added shared structured command items for Process Inspector suggestions used by both CLI and GUI.
- Added centralized command safety classification in `core/command_safety.py`.
- Added shared administrator credential validation in `core/admin_auth.py` for CLI Advanced Mode authentication.
- Added shared service catalog logic in `core/service_catalog.py` for saved, system and user service discovery.
- Added shared favorites persistence in `core/favorites.py` for both GUI and CLI.
- Added CLI User Service listing.
- Added CLI Enable and Disable service actions through the existing shared service manager backend.
- Added read-only CLI service log access through the existing shared service manager backend.
- Added a CLI Advanced Mode with administrator authentication and a five-minute inactivity timeout.
- Added CLI views for all services, search/filter, service details, favorites and system metrics.
- Added CLI Add/Remove saved-service management with the same Advanced-Mode requirement as the GUI.
- Added CLI Auto-refresh service monitoring with a ten-second refresh interval and Ctrl+C exit.
- Added CLI Open URL support for services with a configured URL.
- Added automated coverage for Process Inspector integration, command safety, administrator authentication, shared service discovery, favorites and CLI/GUI service parity.
- Added the project `logo.PNG` to the main GUI header beside the Linux Service Center title, with automatic size limiting and graceful fallback when the asset is unavailable.
- Added `Tools -> GitHub Repository` for direct access to the public project repository.
- Added a themed `About Linux Service Center...` window with the project logo when available, development-build status, MIT license note, GitHub shortcut and single-instance focus behavior.

### Improved

- Replaced Tkinter subsample logo rendering with Pillow/LANCZOS for smoother proportional scaling within 56 px, preserving RGBA transparency and the existing nested header placement.
- Made Pillow-backed logo rendering optional at import time: if Pillow is unavailable, the GUI still starts normally and simply omits the logo.
- Kept graceful logo fallback for missing or corrupt files and image/Tk conversion errors.
- Kept project links and About information in the Tools menu instead of adding more controls to the main service toolbar.
- Applied a shared Dark Luxury theme with navy/black backgrounds, warm gold/bronze borders, bright primary text and muted secondary labels.
- Harmonized navigation buttons and dark action tints, including legible disabled states and subdued service-status colors.
- Aligned search fields, filters, metrics, menus and Diagnostics panels with the same dashboard palette.
- Preserved the responsive three-row action bar and all existing service/diagnostic behavior.
- Added a compact bottom safe area to the responsive action bar so Auto Refresh and refresh status remain visible above desktop panels in maximized layouts.
- Reduced vertical action-bar padding while retaining the existing three-row grouping and equal-width responsive columns.
- CLI and GUI now share the same Process Inspector command classification path instead of maintaining separate command-group logic.
- Process Inspector suggestions are labeled as `READ-ONLY` or `ADVANCED` in the CLI.
- Process Inspector CLI output now clarifies that suggested commands are never executed automatically.
- Existing Process Inspector core analysis continues to be reused by both interfaces without duplicating detection, grouping, recovery or confidence logic.
- CLI and GUI now use the same deduplicated service catalog for saved, system and user services.
- CLI and GUI now use the same favorites storage implementation and file format.
- CLI service discovery supports both system and user scopes through the shared core/service-manager path.
- CLI Start, Stop and Restart actions now follow the same Advanced-Mode requirement as the GUI instead of being directly available from Normal Mode.
- CLI Enable and Disable actions use the same service-manager functions already used by the GUI.
- CLI service listings now include status, startup state and service description for both system and user services.
- CLI search and filtering follow the same scope/status semantics as the GUI and sort favorites first.
- GUI service refresh now consumes the shared service catalog rather than maintaining a separate discovery implementation.
- Reworked the GUI action area into responsive rows so controls no longer overflow horizontally on smaller or full-screen layouts.
- Separated read-only actions, service-changing actions and Auto Refresh/status into dedicated rows with equal-width responsive columns.

### Fixed

- Fixed header-logo discovery so the logo is found beside the nested title label inside the header frame instead of only searching direct root-window children.
- Fixed GUI import failure when Pillow is not installed; the logo feature now fails open instead of preventing `ui.application_window` from loading.

### Security

- Command classification now follows a fail-closed model: only explicitly known safe diagnostic command forms are allowed without Advanced Mode.
- Unknown, ambiguous or unsupported executables are classified as Advanced by default.
- State-changing `systemctl` actions remain Advanced while the existing explicit read-only allowlist is preserved.
- `kill`, `killall` and `pkill` remain Advanced-only.
- Shell control syntax, malformed command lines and shell wrappers such as `sh -c` and `bash -c` are classified conservatively as Advanced.
- `sudo` without a subcommand and `sudo` invocations using unsupported options are classified as Advanced.
- Only the known Process Inspector Python entry point is accepted as a normal diagnostic Python command; arbitrary Python scripts remain Advanced.
- `journalctl` is restricted to known read-only log-viewing forms; maintenance operations remain Advanced.
- CLI Start, Stop, Restart, Enable and Disable are blocked in Normal Mode.
- CLI Add and Remove saved-service actions are also blocked in Normal Mode to match GUI behavior.
- CLI Advanced Mode requires successful `sudo -v` credential validation and expires after five minutes of inactivity.
- System-scope write actions retain an additional explicit confirmation after Advanced Mode has been enabled.
- CLI service logs, service discovery, filtering, details, favorites, metrics and auto-refresh remain available without Advanced Mode because they are read-only or local presentation operations.

### Tests

- Expanded the automated test suite from 58 to 122 discovered tests; in the current Pi test environment 121 pass and one real-image Pillow integration check is skipped because Pillow is not installed.
- Added regression coverage for fail-closed handling, absolute executable paths, sudo wrapping, shell syntax, Python command restrictions, journalctl maintenance options and shared CLI/GUI command-item generation.
- Added tests confirming that Normal Mode blocks all CLI service write actions before any service backend call occurs.
- Added tests for Advanced Mode authentication success, authentication failure and inactivity expiration.
- Added tests for system-action confirmation, user-service write routing, User Service listing and read-only log access.
- Added tests for the shared administrator validation helper, including timeout/error fail-closed behavior.
- Added tests for shared service catalog deduplication, availability errors, filtering, favorite-first sorting and service lookup.
- Added tests for shared favorites load/save/toggle behavior without modifying the real project favorites file.
- Added tests for CLI service details, Add/Remove saved services, search/filter, favorites, system metrics, auto-refresh and Open URL behavior.
- Added tests confirming that the GUI delegates service discovery and favorites persistence to the shared core implementation.
- Added a headless GUI regression test for the responsive action-bar row layout, including the bottom safe-area reservation and compact button spacing.
- Added three headless theme tests covering shared widget styling, preserved callbacks and disabled-button color restoration.
- Added eight header-logo tests covering nested title discovery, automatic downscaling, persistent image references, missing-Pillow fail-open behavior, missing/corrupt assets, Pillow compatibility and alpha handling.
- Added five headless project-link tests covering Tools-menu entries, exact public GitHub URL routing, browser-error fallback, themed About content and single-instance About-window behavior.
- Existing Process Inspector integration, manager detection, restart-policy, recovery, grouping and adapter tests remain green.

---

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
