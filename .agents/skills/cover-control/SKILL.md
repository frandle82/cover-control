---
name: cover-control
description: Domänenübersicht für cover-control. Verweist auf spezialisierte Skills für Mixins, Zeitpläne, Gruppen und Lebenszyklus.
---

# Cover Control Domain Skill – Systemübersicht

## Zweck

Dieser Skill bietet die zentrale Domänenübersicht über die Architektur, Mixin-Struktur und Fahrbefehlshierarchie von `cover-control`. Detailfragen werden an spezialisierte Skills delegiert.

---

## 1. Spezialisierte Domänen-Skills

Für Detailthemen sind die spezialisierten Skills heranzuziehen:

* **Konfiguration & Gruppen:**
  * [`config-flow`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/config-flow/SKILL.md) – Reconfigure Flows, Standalone Room Entries (`ENTRY_TYPE_ROOM`), Schema-Definitionen.
  * [`profile-model`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/profile-model/SKILL.md) – Drei feste Gruppen im Controller, Resolver, `configured/enabled/eligible`, Live-Propagation.
* **Laufzeit, Steuerung & Lifecycle:**
  * [`schedule-runtime`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/schedule-runtime/SKILL.md) – Explizite Öffnungs-/Schließmodi, Early/Late, Workday, Astro-Ereignisse und `_TimeGroupProbe`.
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
* `shading.py`: Sieben feste Shuttercontrol-Sonnenschutzmodi, Direction-Geometrie, Temperatur und optionale Helligkeit; keine freie Regelengine oder Forecast-Beschattung.
* `status.py`: Sensoren für nächste Fahrtermine, Diagnosedaten und Steuerungsgründe.

Die Fassade `runtime/controller.py` bündelt diese Mixins. Logik gehört niemals direkt in die Fassade.

---

## 3. Prioritätenhierarchie bei Fahrbefehlen

Bei konkurrierenden Bedingungen gewinnt ausnahmslos die höhere Priorität:
1. **Safety:** Feuer, Regen, Wind und Frost.
2. **Manual Override:** Eingriff des Bewohners blockiert automatische Fahrten.
3. **Window / Ventilation / Lockout:** Fensterzustand bestimmt das sichere Ziel.
4. **Shading / Heat Protection:** Sonnenschutz und Überhitzungsschutz.
5. **Resident:** Anwesenheit und Nachtmodus.
6. **Time / Astro / Brightness:** Reguläre Grundautomation.

Fenster- und Lüftungsentscheidungen sind fest: offen verwendet die Lockout-Position, gekippt die Lüftungsposition, und beide haben Vorrang vor Beschattung. Externe Force-Entities werden nicht angeboten. Die Position stammt ausschließlich aus `current_position` des HA-Cover-Entity; ohne Attribut gilt sie als nicht verfügbar. Recovery erfolgt fest nur nach echten Laufzeitausfällen, und die Fahrstaffelung verwendet ausschließlich `drive_delay_fixed`. Resident und Recalibrate bleiben bewusste Cover-Control-Erweiterungen.

Manual Override ist ein einzelner Automatik-Pausenzustand. Er besitzt nur Aktivierung und Dauer, blockiert keine Aktion selektiv und bleibt bei Dauer `0` bis zum Clear-Button aktiv. Safety wird davor ausgewertet. Die manuelle Shading-Adoption bleibt davon getrennt.

---

## 4. Testausführung

```sh
# Kern-Regressionstests:
.venv/bin/pytest -q tests/test_blueprint_parity.py --asyncio-mode=auto
.venv/bin/pytest -q tests/test_runtime_evaluation.py --asyncio-mode=auto
```
