---
name: schedule-runtime
description: Vertiefte Richtlinien für Zeit-, Sonnen-, Kalender- und Arbeitstag-Steuerung in cover-control.
---

# Schedule-Runtime Skill – Zeit- & Sonnensteuerung

## Zweck

Dieser Skill dokumentiert die zeitbasierte und sonnenabhängige Automationslogik von `cover-control`. Er beschreibt die Berechnung von Öffnungs- und Schließzeiten, die Berücksichtigung von Arbeitstagen und Sonnenstand sowie die Vorhersage nächster Ereignisse.

---

## 1. Kernkonzepte des Zeitmanagements

Die Zeit- und Sonnenlogik ist in `custom_components/cover_control/runtime/schedule.py` und `runtime/group_evaluation.py` implementiert:

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

## 2. Explizite Öffnungs- und Schließmodi

* Öffnen: `time`, `sunrise`, `golden_hour`, `elevation`, `brightness`.
* Schließen: `time`, `sunset`, `golden_hour`, `elevation`, `brightness`.
* Sunrise/Sunset verwenden echte Astral-Ereignisse; Golden Hour verwendet morgens das Ende und abends den Beginn der Astral Golden Hour.
* `astro_open_offset_minutes` gilt für Sunrise und morgendliche Golden Hour, `astro_close_offset_minutes` für Sunset und abendliche Golden Hour.
* Elevation besitzt nur feste numerische Schwellen. Dynamic-/Hybrid-Sensoren und `sun_time_duration` sind nicht Teil des aktiven Modells.
* Early/Late begrenzen jeden Modus. Brightness besitzt keine astronomisch vorhersagbare Uhrzeit; `next_open`/`next_close` zeigt deshalb die nächste Fenstergrenze, bis ein Sensorereignis auslöst.

---

## 3. Zustandsfreie Evaluierung: `_TimeGroupProbe`

Für feste Gruppen, die von mehreren Räumen referenziert werden, wird in `runtime/group_evaluation.py` eine leichtgewichtige Probe-Klasse eingesetzt:

```python
class _TimeGroupProbe(ScheduleMixin):
    """Zustandsfreie Snapshot-Probe zur Berechnung von Zeitplan-Ereignissen."""
    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        self.hass = hass
        self.config = config
```

* **Zweck:** Ermittelt die nächsten Schaltzeitpunkte (`next_open`, `next_close`) rein aus der Gruppenkonfiguration und dem aktuellen Zustand (Workday, Sonne), ohne eine vollständige Controller-Instanz instanziieren zu müssen.
* **Ergebnis:** Wird im `CoverControlHub` im `GroupEvaluation`-Dataclass gecacht und bei Bedarf an die Räume propagiert.

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
.venv/bin/pytest -q tests/test_astro_modes.py --asyncio-mode=auto
.venv/bin/pytest -q tests/test_blueprint_parity.py -k sun --asyncio-mode=auto
```
