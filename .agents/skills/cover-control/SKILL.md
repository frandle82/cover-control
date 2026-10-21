---
name: cover-control
description: Domänenübersicht für cover-control. Verweist auf spezialisierte Skills für Mixins, Zeitpläne, Profile und Lebenszyklus.
---

# Cover Control Domain Skill – Systemübersicht

## Zweck

Dieser Skill bietet die zentrale Domänenübersicht über die Architektur, Mixin-Struktur und Fahrbefehlshierarchie von `cover-control`. Detailfragen werden an spezialisierte Skills delegiert.

---

## 1. Spezialisierte Domänen-Skills

Für Detailthemen sind die spezialisierten Skills heranzuziehen:

* **Konfiguration & Profile:**
  * [`config-flow`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/config-flow/SKILL.md) – Reconfigure Flows, Standalone Room Entries (`ENTRY_TYPE_ROOM`), Schema-Definitionen.
  * [`profile-model`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/profile-model/SKILL.md) – Zentrale Profile im Controller, Resolver, `configured/enabled/eligible`, Live-Propagation.
* **Laufzeit, Steuerung & Lifecycle:**
  * [`schedule-runtime`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/schedule-runtime/SKILL.md) – Zeitfenster (Early/Late), Workday, Fixed/Dynamic/Hybrid Sun, `_TimeProfileProbe`.
  * [`runtime-lifecycle`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/runtime-lifecycle/SKILL.md) – Datenfluss Controller → Hub → Room Manager → Controller → Snapshot → Entity, Setup/Unload.
* **Blueprint-Parität & Release:**
  * [`cca-parity`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cca-parity/SKILL.md) – Vollständigkeitskette UI → Persistenz → Resolver → Runtime → Tests.
  * [`release`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/release/SKILL.md) – Release-Kette via PR, Release Drafter und GitHub Actions Workflow.

---

## 2. Mixin-Zuständigkeiten (`custom_components/cover_control/runtime/`)

Die Geschäftslogik ist strikt in die Controller-Mixins aufgeteilt:
* `actuator.py`: Fahrbefehle senden, Positionstoleranz auswerten, Lamellenkippung (Tilt), Verzögerungen.
* `evaluation.py`: Berechnung der Zielposition, Bedingungsauswertung (`configured`, `enabled`, `eligible`).
* `events.py`: Home Assistant Event- und State-Subscriptions.
* `schedule.py`: Zeitpläne, Arbeitstage, Astral-/Sonnen- und Kalenderevents.
* `shading.py`: Sonnengeometrie (Azimut, Elevation), Wetter- und Temperaturbedingungen.
* `status.py`: Sensoren für nächste Fahrtermine, Diagnosedaten und Steuerungsgründe.

Die Fassade `runtime/controller.py` bündelt diese Mixins. Logik gehört niemals direkt in die Fassade.

---

## 3. Prioritätenhierarchie bei Fahrbefehlen

Bei konkurrierenden Bedingungen gewinnt ausnahmslos die höhere Priorität:
1. **Lockout (Aussperrschutz):** Tür offen = Schließen blockieren.
2. **Force (Erzwingung / Notfall):** Manuell oder sensorbasiert (Wind, Rauch, Frost).
3. **Manual Override (Manuelle Übersteuerung):** Eingriff des Bewohners blockiert automatische Fahrten.
4. **Ventilation (Lüftung):** Fenster gekippt/geöffnet.
5. **Shading (Beschattung):** Überhitzungsschutz bei Sonneneinstrahlung.
6. **Resident (Anwesenheit / Nachtmodus):** Schlafsensor / Resident-Modus.
7. **Schedule & Sun (Grundautomation):** Reguläre zeit- oder sonnenbasierte Fahrten.

---

## 4. Testausführung

```sh
# Kern-Regressionstests:
.venv/bin/pytest -q tests/test_blueprint_parity.py --asyncio-mode=auto
.venv/bin/pytest -q tests/test_runtime_evaluation.py --asyncio-mode=auto
```
