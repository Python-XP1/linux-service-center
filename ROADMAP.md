# Linux Service Center - Roadmap

## Ziel

Die Legacy-Version vollständig in die neue modulare Architektur überführen, sicher über systemd verwalten und schrittweise zu einem verständlichen Linux-Service- und Diagnosewerkzeug ausbauen.

## Entwicklungsreihenfolge

- Erst Feature-Parität zur Legacy erreichen
- Danach D-Bus integrieren
- Danach Sicherheitsfunktionen erweitern
- Danach Diagnosefunktionen und Komfortfunktionen ausbauen
- Entwicklungsstand zuerst im privaten Lab testen
- Getestete Zwischenstände gezielt in den öffentlichen `dev-dbus`-Branch spiegeln

---

# Aktueller Fokus

## Nächster Entwicklungsschritt

- [ ] Process Inspector in das Diagnostics-GUI integrieren

### Akzeptanzkriterien

- [ ] Suchfeld für PID, Prozessname, Kommando oder Service
- [ ] Analyse über die vorhandene `diagnostics/process_inspector.py`-Logik
- [ ] Gruppierte Ergebnisse statt mehrfacher Vollausgabe derselben Unit
- [ ] Manager, Unit, Slice, Health und Restart-Policy anzeigen
- [ ] Confidence Score und Recovery Advisor darstellen
- [ ] Vorgeschlagene Kommandos kopierbar anzeigen
- [ ] Keine Recovery-Aktion automatisch ausführen
- [ ] Gefährliche Aktionen nur im Advanced Mode anbieten
- [ ] Kritische und generische Slices niemals ungeprüft als Stop-Ziel anbieten

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

# Phase 3 - D-Bus Migration

## Neues Backend

- [x] `dbus_backend.py` erstellen
- [x] Backend-Auswahl erweitern
- [x] systemctl als Fallback behalten
- [x] D-Bus vollständig testen

## Hybrid Backend

- [x] Listing über D-Bus
- [x] Details über D-Bus
- [x] Actions über systemctl-Fallback
- [x] Logs über systemctl-Fallback

---

# Phase 4 - Sicherheit & Benutzerführung

## Session-Sicherheit

- [x] Advanced Mode Session Timeout von 5 Minuten
- [x] Automatischer Wechsel zurück zu Normal Mode
- [x] Re-Authentifizierung nach Timeout

## Modusverwaltung

- [x] Normal Mode
- [x] Advanced Mode
- [x] Warning Dialog
- [x] GUI-Passwortabfrage
- [x] Buttons abhängig vom Modus sperren oder freigeben
- [ ] Passwort-Dialog optisch verbessern
- [ ] Tooltips für gefährliche Aktionen
- [ ] Sicherheitsstatus sichtbar anzeigen

## Schutzmaßnahmen

- [x] Keine automatische Ausführung von Process-Inspector-Recovery-Kommandos
- [x] Generische und kritische Slices von Stop-Vorschlägen ausschließen
- [ ] Kritische Systemdienste zusätzlich schützen
- [ ] Bestätigung vor destruktiven Recovery-Aktionen

---

# Phase 5 - Process Inspector

## Erkennung und Analyse

- [x] Orphaned Prozesse beziehungsweise nicht geladene Units erkennen
- [x] Parent Chain erkennen
- [x] Systemdienste erkennen
- [x] User-Services erkennen
- [x] App-managed Prozesse erkennen
- [x] Process Ownership analysieren
- [x] Unit aus cgroup erkennen
- [x] Slice aus cgroup erkennen
- [x] Stale oder fehlende systemd Unit aus cgroup erkennen
- [x] Restart-Policy erkennen
- [x] Respawn-Risiko erkennen

## Diagnose und Recovery

- [x] `systemd-cgls`, `list-units` und `list-unit-files` vorschlagen
- [x] Manuellen Respawn-Test erzeugen
- [x] Sichere Slice-Recovery-Kommandos vorschlagen
- [x] Recovery Advisor
- [x] Confidence Score
- [x] Umgebungsneutrale Respawn-Suchbegriffe
- [x] Wiederholte Analyse derselben Unit vermeiden
- [x] Prozesse nach Manager und Unit gruppieren
- [x] Related Processes anzeigen

## Offene Inspector-Erweiterungen

- [ ] Vollständigen Parent- und Child-Prozessbaum anzeigen
- [ ] Tatsächliche Respawn-Quelle erkennen, wenn die Unit nicht geladen ist
- [ ] Timer Units als Respawn-Quelle erkennen
- [ ] Path Units als Respawn-Quelle erkennen
- [ ] Socket Units als Respawn-Quelle erkennen
- [ ] Cronjobs als Respawn-Quelle erkennen
- [ ] Desktop-Autostart erkennen
- [ ] Launcher- und Watchdog-Skripte erkennen
- [ ] Final Diagnosis beziehungsweise Verdict erzeugen
- [ ] Primäre empfohlene Aktion hervorheben
- [ ] Diagnosebericht exportieren
- [ ] Process Inspector in das Diagnostics-GUI integrieren

---

# Phase 6 - Settings

## Konfiguration

- [ ] Settings-Fenster
- [ ] Einstellungen zentral und validiert speichern

## Optionen

- [ ] Normal-Mode-Verhalten konfigurieren
- [ ] Auto-Refresh konfigurieren
- [ ] Favoriten dauerhaft speichern
- [ ] Systemdienste ausblenden
- [ ] Temperaturanzeige umschalten
- [ ] Compact Mode
- [ ] Dark / Light Theme

---

# Phase 7 - Dashboard & Komfortfunktionen

## Dashboard 2.0

- [ ] Aktive Services
- [ ] Fehlgeschlagene Services
- [ ] Activating Services
- [ ] CPU Übersicht
- [ ] Temperatur Übersicht
- [ ] RAM Übersicht
- [ ] Favoriten Übersicht

## Weitere Komfortfunktionen

- [x] Favoriten
- [ ] Benachrichtigungen
- [ ] Exportfunktionen

---

# Phase 8 - Testing & Release Quality

## Automatisierte Tests

- [ ] Unit Tests für Backend Selector
- [ ] Unit Tests für systemctl Backend
- [ ] Unit Tests für D-Bus Backend
- [ ] Unit Tests für Process Inspector
- [ ] systemctl- und D-Bus-Antworten mocken
- [ ] Headless GUI Smoke Tests
- [ ] GitHub Actions für Compile- und Testläufe

## Öffentlicher Release

- [x] `dev-dbus` als Work in Progress kennzeichnen
- [x] Private Entwicklungsdateien aus öffentlichem Branch entfernen
- [x] Unsichere persönliche Screenshots entfernen
- [x] `.gitignore` gegen Zugangsdaten und lokalen Zustand härten
- [ ] Bereinigte Screenshots ergänzen
- [ ] Kurzes Demo-Video oder GIF erstellen
- [ ] Installation auf frischem Raspberry Pi OS testen
- [ ] Stable-Release-Checkliste erstellen
- [ ] Getesteten Entwicklungsstand in `main` mergen

---

# Phase 9 - Langfristige Erweiterungen

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

# Repository-Workflow

- `Python-XP1/pythonxp-lab`, Branch `dev-dbus`: private Hauptentwicklung und Tests
- `Python-XP1/linux-service-center`, Branch `dev-dbus`: öffentlicher Entwicklungsstand, ausdrücklich keine fertige Version
- `Python-XP1/linux-service-center`, Branch `main`: stabiler öffentlicher Stand
- Sicherheits- und Bugfixes aus dem öffentlichen Entwicklungsbranch müssen zurück ins private Lab synchronisiert werden
- Vor einem öffentlichen Push lokale Zustände, Zugangsdaten, Pfade, IP-Adressen und Screenshots prüfen

---

# Regeln

Neue größere Features erst beginnen, wenn:

- [x] Legacy-Funktion vorhanden
- [x] Architektur sauber
- [x] D-Bus integriert
- [x] Kritische Advanced-Mode-Sicherheitsfunktionen implementiert
- [ ] Tests für den betroffenen Bereich vorhanden

Sicherheitskritische Funktionen werden niemals still oder automatisch ausgeführt. Diagnose und Vorschläge bleiben zunächst read-only.