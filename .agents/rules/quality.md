# Qualitäts- & Testregeln – Cover Control

Verbindliche Qualitätsstandards, Testanforderungen und Verifikationsprozesse für `cover-control`.

## 1. Verbindliche Teststrategie

* **Vollständige Abdeckung:** Jede Verhaltensänderung (behavioral change) muss durch Regressionstests abgedeckt werden.
* **Integrations-Testsuite:** Vor dem Abschluss einer Änderung immer die vollständige Integrationstestsuite ausführen.
* **Umfassende Prüfung:** Tests niemals nur auf das aktuell bearbeitete Modul beschränken.
* **Relevante Funktionsbereiche:** Änderungen an Config Flows, Migrationen, Entitäten, Attributen, Discovery, Events, Services, Diagnosen, Umgebungsbewertungen oder Release-Verhalten erfordern spezifische Regressionstests.
* **Authoritative Release Gate:** Die stabile Home Assistant Testsuite (`pytest-homeassistant-custom-component`) ist das verbindliche Freigabekriterium.

## 2. Testausführung & Testprinzipien

* **Virtuelle Umgebung:** Tests in der isolierten virtuellen Umgebung ausführen:
  ```sh
  .venv/bin/pytest -q tests/test_config_flow.py --asyncio-mode=auto
  .venv/bin/pytest -q --asyncio-mode=auto
  ```
* **Deterministisch & Offline:** Keine echten Netzwerkverbindungen in Tests. Parität zum Blueprint (CCA) lokal in `tests/test_blueprint_parity.py` ohne Abhängigkeit vom Live-Repository abbilden.
* **Zustandstrennung testen:** `configured`, `enabled` und `eligible` als eigenständige Zustände separat abtesten.
* **Lifecycle & Cleanup:** Entity-Registry-Cleanup testen, wenn Profilfunktionen abgewählt oder Profile aus einem Raum entfernt werden.

## 3. Code-Qualität & Home Assistant Standards

* **Nicht-blockierende Callbacks:** Callbacks dürfen niemals blockieren. `async_`-APIs von Home Assistant nutzen; blocking I/O über `async_add_executor_job` ausführen.
* **Sauberes Ressourcen-Management:** State-Listener beim Unload restlos entfernen. Hintergrund-Tasks an den Config Entry binden und beim Unload terminieren.
* **Resilienz:** Nicht voraussetzen, dass Entitäten existieren; fehlende oder nicht verfügbare Entitäten defensiv abfangen.
* **Python-Kompilierung & Whitespace:**
  ```sh
  .venv/bin/python -m compileall -q custom_components tests scripts
  git diff --check
  ```

## 4. UI, Lokalisierung & Diagnose

* **Synchronität der Übersetzungen:** `strings.json`, `translations/en.json` und `translations/de.json` müssen immer strukturell synchron gehalten werden.
* **Übersetzungsschlüssel:** Für Selektor-Optionen im UI immer Übersetzungsschlüssel verwenden, keine hartkodierten englischen Strings.
* **Diagnostik:** Python-Logging für Entwickler; HA-Events/Logbook für Benutzer. Wiederholte Log-Einträge bei zyklischer Evaluierung zwingend deduplizieren.
