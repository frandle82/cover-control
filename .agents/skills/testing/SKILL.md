---
name: testing
description: Anweisungen und Best Practices zur Testausführung und Testentwicklung in cover-control.
---

# Testing Skill – Cover Control

Dieser Skill ermöglicht effizientes und fehlerfreies Testen im Projekt `cover-control`.

## 1. Python- und Test-Umgebung

* **Wichtig:** Immer die isolierte virtuelle Umgebung `.venv` verwenden!
* **Pytest-Binary:** `.venv/bin/pytest`
* **Python-Binary:** `.venv/bin/python`

## 2. Schnelle Testbefehle (Fokussiert)

```sh
# Einzelne Testdatei ausführen (z. B. Config Flow):
.venv/bin/pytest -q tests/test_config_flow.py --asyncio-mode=auto

# Einzelnen Test gezielt ausführen:
.venv/bin/pytest -q tests/test_config_flow.py -k test_parent_reconfigure_loads_for_existing_entry --asyncio-mode=auto

# Blueprint-Parität (CCA) testen:
.venv/bin/pytest -q tests/test_blueprint_parity.py --asyncio-mode=auto

# Subentries & Datenmodell testen:
.venv/bin/pytest -q tests/test_config_subentries.py --asyncio-mode=auto
```

## 3. Vollständige Verifikation vor Aufgabenabschluss

```sh
# 1. Vollständige Testsuite:
.venv/bin/pytest -q --asyncio-mode=auto

# 2. Syntax- & Bytecode-Kompilierung:
.venv/bin/python -m compileall -q custom_components tests scripts

# 3. Git Diff & Whitespace-Prüfung:
git diff --check
```

## 4. Häufige Fehler & Best Practices

* **Lingering Timers / Tasks:** Wenn `pytest_homeassistant_custom_component` Fehler wegen lingering timers wirft (z. B. `_TrackPointUTCTime`), stelle sicher, dass gestartete Config Entries im Test über `await entry.async_unload(hass)` bzw. `await hass.async_block_till_done()` sauber abgeräumt werden.
* **Deterministische Zeit:** Niemals echte `time.sleep` oder `asyncio.sleep` verwenden. Nutze Home Assistant Zeitreise-Helfer (`async_fire_time_changed`).
* **Offline-Prinzip:** Tests dürfen niemals externe Netzwerkverbindungen aufbauen.
