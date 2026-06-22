# Linux Service Center - Roadmap

Ziel:

Die Legacy-Version vollständig in die neue modulare Architektur überführen und anschließend auf DBus umstellen.

Regel:

- Erst Feature-Parität zur Legacy erreichen
- Danach DBus integrieren
- Danach neue Features entwickeln

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
- [ ] Remove Service
- [x] Auto-Refresh

## Diagnostics

- [ ] Diagnostics Fenster migrieren

## Monitoring

- [ ] CPU Monitoring
- [ ] RAM Monitoring
- [ ] Temperatur Monitoring
- [ ] Speicherplatz Monitoring

## URL Shortcuts

- [ ] URL Shortcuts migrieren

---

# Phase 3 - DBus Migration

## Neues Backend

- [ ] dbus_backend.py erstellen
- [ ] Backend-Auswahl erweitern
- [ ] systemctl als Fallback behalten
- [ ] DBus vollständig testen

---

# Phase 4 - PythonXP Erweiterungen

## Komfortfunktionen

- [ ] Favoriten
- [ ] Dashboard
- [ ] Benachrichtigungen
- [ ] Dark / Light Theme
- [ ] Export Funktionen

---

# Regeln

Neue Features erst beginnen, wenn:

☑ Legacy Funktion vorhanden

☑ Architektur sauber

☑ DBus integriert

Erst danach neue Ideen ergänzen.