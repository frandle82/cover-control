---
name: cover-control
description: Domänenspezifischer Skill für Laufzeitlogik, Mixin-Architektur, Prioritäten und Fahrbefehle in cover-control.
---

# Cover Control Domain Skill

Leitfaden für die Laufzeitsteuerung, Mixins und Automationslogik von `cover-control`.

## 1. Mixin-Architektur (`custom_components/cover_control/runtime/`)

Jede Logik hat ihren festen Platz:
* `actuator.py`: Fahrbefehle senden, Positionstoleranz auswerten, Lamellenkippung (Tilt), Verzögerungen.
* `evaluation.py`: Zielpositionsberechnung, Prüfung aller Bedingungen (`configured`, `enabled`, `eligible`).
* `events.py`: Home Assistant Event- und State-Subscriptions.
* `schedule.py`: Zeitpläne, Arbeitstage, Kalenderevents.
* `shading.py`: Sonnengeometrie (Azimut, Elevation), Wetter- und Beschattungsbedingungen.
* `status.py`: Sensoren für nächsten Fahrtermin, Steuerungsgründe, Diagnosedaten.

Controller-Fassade: `controller.py` exportiert die Mixins gebündelt. Keine Logik direkt in der Fassade ablegen.

## 2. Prioritätenhierarchie bei Fahrbefehlen

Bei der Zielpositionsfindung gilt ausnahmslos folgende Priorität:
1. **Lockout (Aussperrschutz):** Höchste Priorität (Tür offen = Fahrt blockieren).
2. **Force (Erzwingung):** Manuell oder über Schalter ausgelöst.
3. **Manual Override (Manuelle Übersteuerung):** Nutzer hat den Rollladen von Hand verstellt.
4. **Ventilation (Lüftung):** Fenster gekippt/geöffnet.
5. **Shading (Beschattung):** Sonnenschutz aktiv.
6. **Resident (Anwesenheit/Schlaf):** Schlafsensor / Resident-Modus.
7. **Schedule / Brightness (Standard-Automation):** Zeit- oder helligkeitsbasierte Fahrt.

## 3. Fahrbefehle & Toleranz

* Vor jedem Fahrbefehl prüfen, ob die aktuelle Rollladenposition bereits innerhalb der konfigurierten Toleranz (`tolerance`) liegt.
* Keine doppelten Befehle senden.
* Zwischenzustände (`opening`, `closing`) dürfen nicht fälschlich als manuelle Bedienung gewertet werden.

## 4. Testen von Steuerungslogik

```sh
.venv/bin/pytest -q tests/test_blueprint_parity.py --asyncio-mode=auto
```
