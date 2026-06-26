# Linux Service Center - Roadmap

## Ziel

Die Legacy-Version vollständig in die neue modulare Architektur überführen und anschließend auf DBus umstellen.

Regeln:

- Erst Feature-Parität zur Legacy erreichen
- Danach DBus integrieren
- Danach Sicherheitsfunktionen erweitern
- Danach Komfortfunktionen entwickeln

---

# Phase 1 - Grundsystem

## Architektur

- [x] Modulare Projektstruktur
- [x] GUI integriert
- [x] CLI integriert
- [x] Backend-Abstraktion
- [x] systemctl Backend
- [x] Sicherheitsabfragen
- [x] Live-Suche
- [x] README aktualisiert
- [x] Filter-Chips / Service-Filter

---

# Phase 2 - Legacy Migration

## Service Management

- [x] Enable Service
- [x] Disable Service
- [x] Service Logs anzeigen
- [x] Add Service
- [x] Remove Service
- [x] Auto-Refresh

## Diagnostics

- [x] Diagnostics Fenster migrieren

## Monitoring

- [x] CPU Monitoring
- [x] RAM Monitoring
- [x] Temperatur Monitoring
- [x] Speicherplatz Monitoring

## URL Shortcuts

- [x] URL Shortcuts migrieren

---

# Phase 3 - DBus Migration

## Neues Backend

- [x] dbus_backend.py erstellen
- [x] Backend-Auswahl erweitern
- [x] systemctl als Fallback behalten
- [x] DBus vollständig testen

## Hybrid Backend

- [x] Listing -> DBus
- [x] Details -> DBus
- [x] Actions -> systemctl Fallback
- [x] Logs -> systemctl Fallback

---

# Phase 4 - PythonXP Erweiterungen

## Komfortfunktionen

- [x] Favoriten
- [ ] Dashboard
- [ ] Benachrichtigungen
- [ ] Dark / Light Theme
- [ ] Export Funktionen

---

# Phase 5 - Sicherheit & Benutzerführung

## Session Sicherheit

- [x] Advanced Mode Session Timeout (5 Minuten)
- [x] Automatischer Wechsel zurück zu Normal Mode
- [x] Re-Authentifizierung erforderlich

## Benutzerführung

- [x] Buttons abhängig vom Modus sperren/freigeben
- [ ] Tooltipps für gefährliche Aktionen
- [ ] Sicherheitsstatus anzeigen

## Modusverwaltung

- [x] Normal Mode
- [x] Advanced Mode
- [x] Warning Dialog
- [x] GUI Passwort-Abfrage
- [ ] Passwort-Dialog optisch verbessern

---

# Phase 6 - Settings

## Konfiguration

- [ ] Settings Fenster

## Optionen

- [ ] Beginner Mode
- [ ] Auto Refresh
- [ ] Remember Favorites
- [ ] Hide System Services
- [ ] Show Temperatures
- [ ] Compact Mode

---

# Phase 7 - Dashboard 2.0

## Übersicht

- [ ] Aktive Services
- [ ] Fehlgeschlagene Services
- [ ] Activating Services
- [ ] CPU Übersicht
- [ ] Temperatur Übersicht
- [ ] RAM Übersicht
- [ ] Favoriten Übersicht

---

# Phase 8 - Langfristige Erweiterungen

## Linux Cockpit

- [ ] Services
- [ ] Logs
- [ ] Dashboard
- [ ] Docker
- [ ] Cronjobs
- [ ] Netzwerk
- [ ] System Updates
- [ ] PythonXP Integration

---

## Process Inspector

- [ ] Detect orphan processes
- [ ] Detect parent process
- [ ] Show process tree
- [ ] Detect Restart=always
- [ ] Detect user services
- [ ] Detect app-managed processes
- [ ] Process ownership analysis
- [ ] Detect stale/missing systemd unit from cgroup
- [ ] Suggest systemd-cgls / list-units / list-unit-files checks
- [ ] Detect respawn source when unit is not loaded

--

# Regeln

Neue Features erst beginnen, wenn:

- [x] Legacy Funktion vorhanden
- [x] Architektur sauber
- [x] DBus integriert
- [ ] Sicherheitsfunktionen implementiert

Erst danach neue Ideen ergänzen.