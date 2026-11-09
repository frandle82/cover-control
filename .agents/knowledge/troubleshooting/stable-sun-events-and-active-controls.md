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

Die frühere konfigurierbare Sun-Duration wurde mit der Dynamic-/Hybrid-Elevation-Architektur entfernt. Astronomische Ereignisse werden jetzt direkt für Datum, HA-Standort und HA-Zeitzone berechnet und erst danach auf volle Sekunden normalisiert.

Zusätzlich leitete der Activity-/Control-Status aktive Controls ausschließlich aus `_reason` ab. Nach einer bereits erreichten Zielposition konnte eine weiterhin entscheidungsrelevante Zeit-, Sun- oder andere Gruppenbedingung deshalb als `idle` erscheinen.

## Invarianten

- Sunrise, Sunset und Golden Hour liefern bei unveränderten Eingaben deterministische Zeitpunkte mit `microsecond == 0`.
- Elevation verwendet eine feste Schwelle ohne konfigurierbare Sun-Duration.
- Brightness-Duration bleibt als eigene Sensorstabilisierung bestehen.
- `_reason` bleibt die Semantik für die zuletzt ausgeführte Aktion bzw. Bewegungsbegründung.
- Aktive Entscheidungs-Controls werden separat erfasst und im Entry-Snapshot mit reason-basierten Controls vereinigt.
- `active_controls` und `control_state` dürfen nicht davon abhängen, ob im aktuellen Evaluierungslauf ein neuer Cover-Befehl gesendet wurde.

## Absicherung

Die Regressionstests prüfen Jahreszeiten, DST, Jahreswechsel, wiederholte Berechnung sowie Entry-Snapshots mit aktiven Entscheidungs-Controls ohne neue Aktion.

Verwandte Notizen:
* [`../domain/shading-and-solar-geometry.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/shading-and-solar-geometry.md)
* [`home-assistant-async-guidelines.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/home-assistant-async-guidelines.md)
