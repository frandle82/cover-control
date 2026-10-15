---
name: migrations
description: Richtlinien für Konfigurationsmigrationen und Version-Upgrades in cover-control.
---

# Migrations Skill – Cover Control

Vorgaben für sichere Schema-Migrationen und Abwärtskompatibilität in `cover-control`.

## 1. Migrationsprinzipien

* **Persistenz vs. Memory:** Nur persistierte Daten in Config Entries benötigen Migrationen. Laufzeit-Zustände im Speicher werden nicht migriert.
* **Kein Datenverlust:** Bestehende Benutzereinstellungen müssen bei Schema-Änderungen erhalten bleiben.
* **Versionierung:** `ENTRY_VERSION` in `const.py` nur dann erhöhen, wenn sich das persistente Schema tatsächlich inkompatibel ändert.
* **Aufräumen:** Veraltete Schlüssel werden nach erfolgreicher Migration aus dem Eintrag entfernt.

## 2. Zentrale Migrationslogik

* `custom_components/cover_control/config_migration.py`: Enthält `async_migrate_entry` und Normalisierungshelfer.
* `normalize_legacy_config`: Übersetzt alte Konfigurationsstrukturen in das native Modell.

## 3. Testen von Migrationen

* Für jede neue Migration muss mindestens ein Regressionstest existieren, der einen alten Stand erfolgreich auf das neue Schema migriert.
* Ausführung:
  ```sh
  .venv/bin/pytest -q tests/test_config_migration.py --asyncio-mode=auto
  ```
