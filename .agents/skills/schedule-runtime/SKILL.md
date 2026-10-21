---
name: schedule-runtime
description: Vertiefte Richtlinien für Zeit-, Sonnen-, Kalender- und Arbeitstag-Steuerung in cover-control.
---

# Schedule-Runtime Skill – Zeit- & Sonnensteuerung

## Zweck

Dieser Skill dokumentiert die zeitbasierte und sonnenabhängige Automationslogik von `cover-control`. Er beschreibt die Berechnung von Öffnungs- und Schließzeiten, die Berücksichtigung von Arbeitstagen und Sonnenstand sowie die Vorhersage nächster Ereignisse.

---

## 1. Kernkonzepte des Zeitmanagements

Die Zeit- und Sonnenlogik ist in `custom_components/cover_control/runtime/schedule.py` und `runtime/profile_evaluation.py` implementiert:

### Time Early & Time Late (Zeitfenster)
* **`open_time_early` / `open_time_late`:** Frühester und spätester erlaubter Öffnungszeitpunkt am Morgen.
* **`close_time_early` / `close_time_late`:** Frühester und spätester erlaubter Schließzeitpunkt am Abend.
* Verhindert z. B., dass der Rollladen im Hochsommer bei Sonnenaufgang um 04:30 Uhr öffnet oder im Winter vor 16:30 Uhr schließt.

### Workday vs. Non-Workday
* Unterscheidung zwischen Werktagen (Mo–Fr bzw. nach HA-Workday-Sensor) und Wochenenden/Feiertagen.
* Eigene Zeitfenster für Arbeitstage (`workday`) und freie Tage (`non-workday`).

### Astral & Sonnenberechnung
* Berechnung von Sonnenaufgang (`sunrise`), Sonnenuntergang (`sunset`), Dämmerungsphasen (Dawn/Dusk) sowie aktuellem Sonnenstand (Azimut und Elevation) über HA Core Astral-Helfer.
* Konfigurierbare Offsets (z. B. 15 Minuten vor Sonnenuntergang).

---

## 2. Modi für Sonnenereignisse: Fixed, Dynamic & Hybrid Sun

| Modus | Verhalten | Logik |
|---|---|---|
| **Fixed** | Feste Uhrzeit | Rollladen fährt strikt zu der konfigurierten Uhrzeit (z. B. 07:00 Uhr öffnen, 21:00 Uhr schließen). |
| **Dynamic Sun** | Reiner Sonnenstand | Rollladen folgt exakt dem Sonnenaufgang/-untergang (inklusive Offset). |
| **Hybrid Sun** | Sonnenstand gekoppelt an Zeitfenster | Rollladen folgt der Sonne, wird aber durch `Time Early` und `Time Late` begrenzt: $$\text{target\_time} = \max(\text{time\_early}, \min(\text{sun\_event} + \text{offset}, \text{time\_late}))$$ |

### `sun_time_duration`
* Berechnet die dynamische Dauer zwischen relevanten Sonnenereignissen (z. B. Dauer des Tageslichts) und dient als Basis für Dämmerungsverzögerungen.

---

## 3. Zustandsfreie Evaluierung: `_TimeProfileProbe`

Für wiederverwendbare Profile, die von mehreren Räumen referenziert werden, wird in `runtime/profile_evaluation.py` eine leichtgewichtige Probe-Klasse eingesetzt:

```python
class _TimeProfileProbe(ScheduleMixin):
    """Zustandsfreie Snapshot-Probe zur Berechnung von Zeitplan-Ereignissen."""
    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        self.hass = hass
        self.config = config
```

* **Zweck:** Ermittelt die nächsten Schaltzeitpunkte (`next_open`, `next_close`) rein aus der Profilkonfiguration und dem aktuellen Zustand (Workday, Sonne), ohne eine vollständige Controller-Instanz instanziieren zu müssen.
* **Ergebnis:** Wird im `CoverControlHub` im `ProfileEvaluation`-Dataclass gecacht und bei Bedarf an die Räume propagiert.

---

## 4. Diagnosesensoren: `next_open` & `next_close`

* Jede Cover-Instanz exponiert über `runtime/status.py` und `sensor.py` die Attribute und Sensoren:
  * `next_open`: Nächster geplanter Öffnungszeitpunkt (ISO-8601).
  * `next_close`: Nächster geplanter Schließzeitpunkt (ISO-8601).
* Berücksichtigt Kalender, Workday, früheste/späteste Grenzen und Sonnen-Offsets.
* Zeitzonen-Hygiene: Im Speicher als UTC (`datetime` mit `timezone.utc`), für Benutzeranzeige in lokaler Home Assistant Zeit.

---

## 5. Testen von Schedule- und Sonnenlogik

```sh
# Schedule- und Zeittests fokussiert ausführen:
.venv/bin/pytest -q tests/test_runtime_schedule.py --asyncio-mode=auto
.venv/bin/pytest -q tests/test_blueprint_parity.py -k sun --asyncio-mode=auto
```
