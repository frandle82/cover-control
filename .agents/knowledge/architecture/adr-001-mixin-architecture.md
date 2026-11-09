---
title: ADR-001: Mixin-Architektur im Runtime-Controller
type: adr
status: accepted
date: 2026-10-15
tags:
  - architecture
  - runtime
  - controller
  - mixins
---

# ADR-001: Mixin-Architektur im Runtime-Controller

## Kontext
Der Controller für Rollläden und Jalousien muss zahlreiche asynchrone Aufgaben bewältigen: Ereignisabonnements, Zeitpläne, Sonnenstandsberechnung, Bedingungsauswertung, Stellgliedansteuerung und Diagnosestatus. Eine monolithische Controller-Klasse führt schnell zu unübersichtlichem, schwer testbarem Code ("God Object").

## Entscheidung
Die Controller-Logik ist strikt nach funktionalen Domänen auf spezialisierte Mixin-Klassen in `custom_components/cover_control/runtime/` aufgeteilt:
* `actuator.py`: Fahrbefehle, Positionstoleranz, Lamellenkippung (Tilt) und Verzögerungslogik.
* `evaluation.py`: Berechnung der Zielposition und Auswertung der Bedingungen.
* `events.py`: Home Assistant State-Listener und Event-Subscriptions.
* `schedule.py`: Zeitpläne, Arbeitstag-Sensoren und Kalender-Ereignisse.
* `shading.py`: Feste Shuttercontrol-Sonnenschutzmodi, Direction-Geometrie, Temperatur und optionale Helligkeit.
* `status.py`: Zustände der Steuerungsentitäten, Diagnosesensoren und Statusgründe.

Die Hauptklasse `CoverController` in `controller.py` erbt von diesen Mixins und dient als koordinierende Fassade.

## Konsequenzen
* **Strikte Grenzen:** Keine Geschäftslogik in `controller.py` direkt implementieren, sondern im jeweiligen Mixin.
* **Testbarkeit:** Einzelne Mixins können isoliert unit-getestet werden.
* **Stabilität:** Externe Module importieren stabil über `controller.py`, interne Aufteilung bleibt refactorbar.

---
Verwandte Notizen:
* [`../domain/priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../domain/shading-and-solar-geometry.md`](../domain/shading-and-solar-geometry.md)
