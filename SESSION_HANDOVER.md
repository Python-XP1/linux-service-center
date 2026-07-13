# Linux Service Center - Session Handover

Stand: 13.07.2026

Dieses Dokument ist der Einstiegspunkt für eine neue Chat-Session. Vor neuen Vorschlägen zuerst den aktuellen Code im Repository lesen und anschließend die `ROADMAP.md` prüfen.

---

# Projekt

Linux Service Center ist ein Python/Tkinter-Tool für Raspberry Pi und andere systemd-basierte Linux-Systeme.

Ziel ist eine verständliche Oberfläche für:

- Services anzeigen
- Services starten, stoppen und neu starten
- Autostart aktivieren oder deaktivieren
- Logs anzeigen
- eigene Services hinzufügen oder entfernen
- Systemzustand überwachen
- Prozesse und deren tatsächlichen Manager analysieren

Die Anwendung besteht aus GUI und CLI und verwendet ein hybrides Backend aus D-Bus und systemctl.

---

# Repositories und Branches

## Private Hauptentwicklung

- Repository: `Python-XP1/pythonxp-lab`
- Branch: `dev-dbus`
- Remote im lokalen Repository: `lab`
- Zweck: Hauptentwicklung, Tests und unfertige Änderungen

## Öffentlicher Entwicklungsstand

- Repository: `Python-XP1/linux-service-center`
- Branch: `dev-dbus`
- Remote im lokalen Repository: `origin`
- Zweck: öffentlicher Work-in-Progress-Stand
- Dieser Branch ist ausdrücklich keine fertige oder stabile Version

## Stabiler öffentlicher Stand

- Repository: `Python-XP1/linux-service-center`
- Branch: `main`
- Zweck: getestete öffentliche Version

---

# Git-Workflow

Normaler Entwicklungsablauf:

1. Auf lokalem Branch `dev-dbus` entwickeln.
2. Änderungen lokal testen.
3. In das private Lab pushen:

```bash
git push lab dev-dbus
```

4. Nur geprüfte Zwischenstände öffentlich spiegeln:

```bash
git push origin dev-dbus:dev-dbus
```

Kein `--set-upstream` beim öffentlichen Push verwenden. Der normale Upstream soll beim privaten Lab bleiben.

Vor jedem öffentlichen Push prüfen:

```bash
git status
git grep -n -i -E "password|token|secret|api[_-]?key"
```

Außerdem auf lokale Pfade, IP-Adressen, Hostnamen, Screenshots und persönliche Servicenamen achten.

---

# Startbefehle

GUI:

```bash
python -m ui.app
```

CLI:

```bash
python -m cli.app
```

Process Inspector:

```bash
python diagnostics/process_inspector.py <query>
```

Beispiele:

```bash
python diagnostics/process_inspector.py budget
python diagnostics/process_inspector.py code-server
python diagnostics/process_inspector.py python
```

---

# Aktuelle Architektur

Wichtige Bereiche:

```text
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
```

Wichtige Dateien:

- `ui/main_window.py`: Hauptfenster und Service-Tabelle
- `ui/app.py`: GUI-Entrypoint
- `cli/menu.py`: CLI-Menü
- `cli/app.py`: CLI-Entrypoint
- `core/backend_selector.py`: aktive Backend-Auswahl
- `core/service_manager.py`: zentrale Service-Aktionen
- `backends/dbus_backend.py`: D-Bus-Listing und Details
- `backends/systemctl_backend.py`: systemctl-Aktionen und Fallback
- `core/app_settings.py`: Normal-/Advanced-Mode-Einstellungen
- `diagnostics/process_inspector.py`: Prozess-, cgroup- und Recovery-Analyse
- `ROADMAP.md`: aktueller Entwicklungsplan

---

# Backend-Status

Aktiver Stand ist ein Hybrid-Backend:

- Listing über D-Bus
- Details über D-Bus
- Aktionen über systemctl-Fallback
- Logs über systemctl-Fallback

D-Bus wurde auf dem Raspberry Pi erfolgreich getestet.

---

# Sicherheitsmodell

## Normal Mode

- sichere Standardansicht
- gefährliche Aktionen eingeschränkt

## Advanced Mode

- englischer Warnhinweis
- GUI-Passwortabfrage
- Session-Timeout nach 5 Minuten
- automatischer Wechsel zurück zu Normal Mode
- erneute Authentifizierung nach Timeout

Wichtige Regel:

> Sicherheitskritische Aktionen niemals still oder automatisch ausführen.

Recovery-Kommandos des Process Inspectors sind derzeit ausschließlich Vorschläge.

Generische und kritische Slices wie `system.slice`, `user.slice`, `machine.slice` oder `-.slice` dürfen nicht als Stop-Ziel vorgeschlagen werden.

---

# Process Inspector - aktueller Stand

Der Inspector kann bereits:

- Prozesse über PID, Name, Kommando, Pfad und cgroup finden
- Parent Chain anzeigen
- systemd Systemdienste erkennen
- systemd User-Services erkennen
- User-Sessions erkennen
- app-managed und child processes erkennen
- Unit und Slice aus cgroups lesen
- prüfen, ob eine Unit geladen ist
- orphaned beziehungsweise stale Units erkennen
- Restart-Policy erkennen
- Respawn-Risiko anzeigen
- manuelle Respawn-Tests erzeugen
- sichere Slice-Recovery-Vorschläge erzeugen
- Suggested Commands anzeigen
- Recovery Advisor erzeugen
- Confidence Score berechnen
- gleiche Units gruppieren
- doppelte Vollanalysen vermeiden
- Related Processes anzeigen

Der öffentliche `dev-dbus`-Stand enthielt zwei wichtige Sicherheitsverbesserungen, die am 13.07.2026 zurück ins private Lab synchronisiert wurden:

- umgebungsneutrale Respawn-Suchbegriffe statt fest eingebauter lokaler Pfade
- keine Stop-Vorschläge für generische oder kritische Slices

---

# Nächster Entwicklungsschritt

## Process Inspector in das Diagnostics-GUI integrieren

Noch nicht direkt loscodieren, bevor die aktuelle GUI-Struktur gelesen wurde.

Akzeptanzkriterien:

- Suchfeld für PID, Prozessname, Kommando oder Service
- vorhandene Analysefunktionen aus `diagnostics/process_inspector.py` wiederverwenden
- keine zweite Inspector-Logik in der GUI duplizieren
- gruppierte Ergebnisse darstellen
- Manager, Unit, Slice, Health und Restart-Policy anzeigen
- Confidence Score anzeigen
- Recovery Advisor anzeigen
- Suggested Commands kopierbar machen
- keine Kommandos automatisch ausführen
- potenziell gefährliche Aktionen nur im Advanced Mode anbieten
- kritische Services und generische Slices schützen
- lange Analyse darf die Tkinter-GUI nicht einfrieren

Empfohlene technische Richtung:

1. Inspector-Logik importierbar halten.
2. Analyse in einem Worker-Thread ausführen.
3. UI-Updates ausschließlich über `root.after(...)` in den Tkinter-Hauptthread zurückgeben.
4. Ergebnisdaten strukturiert darstellen, nicht die CLI-Textausgabe parsen.
5. Zunächst read-only implementieren.

---

# Offene Process-Inspector-Erweiterungen

- vollständiger Parent-/Child-Prozessbaum
- tatsächliche Respawn-Quelle erkennen
- Timer Units erkennen
- Path Units erkennen
- Socket Units erkennen
- Cronjobs erkennen
- Desktop-Autostart erkennen
- Launcher- und Watchdog-Skripte erkennen
- Final Diagnosis beziehungsweise Verdict
- primäre empfohlene Aktion
- Diagnosebericht exportieren

---

# Tests nach Inspector-Änderungen

Syntaxprüfung:

```bash
python -m py_compile diagnostics/process_inspector.py
```

Funktionstests:

```bash
python diagnostics/process_inspector.py budget
python diagnostics/process_inspector.py code-server
python diagnostics/process_inspector.py python
```

Erwartung:

- kein Crash
- Process Groups werden angezeigt
- Confidence Score wird angezeigt
- Recovery Advisor bleibt vorhanden
- gleiche systemd Unit wird nicht vollständig mehrfach ausgegeben
- `system.slice` und andere generische Slices erhalten keinen Stop-Vorschlag

---

# Zusammenarbeit mit Codex

Workflow:

1. Nova liest zuerst den aktuellen GitHub-Code.
2. Nova erstellt einen präzisen Codex-Prompt oder übernimmt kleine GitHub-Änderungen direkt.
3. Codex bearbeitet den Code.
4. Johannes testet auf dem echten Raspberry Pi mit Display und systemd.
5. Nova prüft den gepushten Code erneut auf GitHub.

Codex kann Tkinter meist nicht vollständig testen, weil in seiner Umgebung kein GUI-Display vorhanden ist. Die echten GUI-Tests erfolgen deshalb auf dem Raspberry Pi.

---

# Kommunikationsstil

- Nutzer heißt Johannes.
- Assistent wird Nova genannt.
- Antworten auf Deutsch, Code und UI-Texte je nach Projektstandard auf Englisch.
- Direkt, praktisch und mit kopierbaren Befehlen arbeiten.
- Vor Codevorschlägen immer den aktuellen Stand im Repository prüfen.
- Keine bereits vorhandenen Features erneut vorschlagen.
- Keine unnötige neue Modularisierung erzwingen.
- Keine Gedankenstriche als Stilmittel verwenden.

---

# Startpunkt für die nächste Session

Der erste Schritt der neuen Session lautet:

> Öffne `Python-XP1/pythonxp-lab`, Branch `dev-dbus`, lies `SESSION_HANDOVER.md`, `ROADMAP.md`, `ui/main_window.py`, das aktuelle Diagnostics-Fenster und `diagnostics/process_inspector.py`. Erstelle danach einen konkreten Plan für die read-only GUI-Integration des Process Inspectors, ohne bestehende Funktionen zu duplizieren.
