---
name: cca-parity
description: Richtlinien für die Parität mit dem CCA-Blueprint. Definiert die Kriterien für vollständige funktionale Integration von Steuerungsfunktionen.
---

# CCA-Parity Skill – Blueprint-Referenz & Vollständigkeitskette

## Zweck

Der CCA-Blueprint (Cover Control Automation) dient als funktionale Referenz für `cover-control`. Dieser Skill stellt sicher, dass portierte oder synchronisierte Verhaltensweisen nicht isoliert implementiert, sondern über die gesamte Systemkette hinweg lückenlos und rückwirkungsfrei integriert werden.

---

## 1. Das Prinzip: FULL-Parität

Ein Blueprint-Feature gilt **ausschließlich dann als vollständig implementiert (FULL)**, wenn die gesamte Kette von der Benutzeroberfläche bis zur physikalischen Fahrbewegung und Verifikation geschlossen ist:

```
[1. UI & Schema] 
       ↓
[2. Persistenz & Defaults] 
       ↓
[3. Resolver & Modell] 
       ↓
[4. Listener & Subscriptions] 
       ↓
[5. Runtime-Logik] 
       ↓
[6. Bewegung & Toleranz] 
       ↓
[7. Deterministische Tests]
```

Das bloße Kopieren einer mathematischen Formel oder Bedingung in ein Mixin ohne Durchstich dieser Kette ist unvollständig.

---

## 2. Die 7 Glieder der Kette

### 1. UI & Schema (`config_flow.py`, `config_profile_schema.py`)
* Alle Konfigurationsparameter müssen im passenden Flow-Schritt (Global, Profil oder Raum) über Voluptuous-Schemata und HA-Selektoren exponiert sein.
* Übersetzungsschlüssel in `strings.json`, `en.json` und `de.json` hinterlegt.

### 2. Persistenz & Defaults (`const.py`)
* Eindeutige Konfigurationsschlüssel (`CONF_*`).
* Sinnvolle, mit dem Blueprint übereinstimmende Defaultwerte in `const.py` bzw. `system_defaults()`.
* Bei Schema-Erweiterungen Migrationspfad in `config_migration.py` beachten.

### 3. Resolver & Modell (`config_resolver.py`, `config_profiles.py`)
* Auflösung über Vererbungshierarchie: `System-Defaults` → `Global Sources` → `Profile Settings` → `Room Overrides`.
* Die Funktion `effective_profile()` und `resolve_config_model()` müssen neue Parameter fehlerfrei propagieren.

### 4. Listener & Subscriptions (`runtime/events.py`, `hub.py`)
* Wenn ein Parameter auf Entity-Zustände (z. B. Helligkeitssensor, Kalender, Arbeitstag, Wetter) reagiert, muss er im State-Listener registriert sein.
* Keine "toten" Konfigurationswerte, die bei Zustandsänderungen nicht neu evaluieren.

### 5. Runtime-Logik (`runtime/`)
* Logik gehört in das jeweilige Mixin (`schedule.py`, `shading.py`, `evaluation.py`, `actuator.py`).
* Strikte Einhaltung der Prioritätenhierarchie (Lockout > Force > Manual Override > Ventilation > Shading > Resident).

### 6. Bewegung, Toleranz & Lamelle (`runtime/actuator.py`)
* Prüfung auf Positionstoleranz (`CONF_POSITION_TOLERANCE`): Kein Fahrbefehl, wenn der Rollladen bereits am Ziel steht.
* Lamellenkippung (Tilt) bei Jalousien mitberücksichtigen (`CONF_DRIVE_DELAY_FIXED`, `CONF_DRIVE_DELAY_RANDOM`).
* Zwischenzustände (`opening`, `closing`) dürfen nicht als manuelle Bedienung gewertet werden.

### 7. Deterministische Regressionstests (`tests/test_blueprint_parity.py`)
* Testen ohne echte Netzwerkaufrufe.
* Zeitreisen über `async_fire_time_changed`.
* Tests für Randfälle: Sonnenwende, Mitternachtsüberschreitung, Ausfall von Sensoren (`STATE_UNAVAILABLE`).

---

## 3. Testausführung für Parität

```sh
# Blueprint-Parität fokussiert testen:
.venv/bin/pytest -q tests/test_blueprint_parity.py --asyncio-mode=auto
```
