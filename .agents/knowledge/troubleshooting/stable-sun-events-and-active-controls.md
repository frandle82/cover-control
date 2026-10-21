---
title: Stable Sun Events and Active Decision Controls
type: troubleshooting
status: active
tags:
  - troubleshooting
  - schedule
  - sun
  - runtime
  - diagnostics
---

# Stable Sun Events and Active Decision Controls

## Bestätigte Root Causes

Bei wiederholten Aktualisierungen der nächsten Sun-Duration-Ereignisse wurde ein nicht initialisiertes `_condition_since`-Mapping über `getattr(..., {})` nur temporär erzeugt. Dadurch begann die Dauerprüfung bei jedem Refresh neu und der Zielzeitpunkt verschob sich fortlaufend.

Zusätzlich leitete der Activity-/Control-Status aktive Controls ausschließlich aus `_reason` ab. Nach einer bereits erreichten Zielposition konnte eine weiterhin entscheidungsrelevante Zeit-, Sun- oder andere Profilbedingung deshalb als `idle` erscheinen.

## Invarianten

- `_condition_since` speichert den Beginn einer weiterhin erfüllten Bedingung stabil im Runtime-Objekt.
- Wird die Schwelle ungültig, wird der gespeicherte Beginn entfernt; beim nächsten gültigen Durchlauf beginnt die Dauer erneut.
- `_reason` bleibt die Semantik für die zuletzt ausgeführte Aktion bzw. Bewegungsbegründung.
- Aktive Entscheidungs-Controls werden separat erfasst und im Entry-Snapshot mit reason-basierten Controls vereinigt.
- `active_controls` und `control_state` dürfen nicht davon abhängen, ob im aktuellen Evaluierungslauf ein neuer Cover-Befehl gesendet wurde.

## Absicherung

Die Regressionstests prüfen wiederholte Refreshes ohne gleitenden Zielzeitpunkt sowie Entry-Snapshots mit aktiven Entscheidungs-Controls ohne neue Aktion. Die vollständige Testsuite bestätigt diese Regeln.

Verwandte Notizen:
* [`../domain/shading-and-solar-geometry.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/shading-and-solar-geometry.md)
* [`home-assistant-async-guidelines.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/home-assistant-async-guidelines.md)
