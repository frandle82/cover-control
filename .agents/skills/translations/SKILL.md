---
name: translations
description: Vorgaben zur Pflege und Synchronisation von Übersetzungsschlüsseln und Texten in cover-control.
---

# Translations Skill – Cover Control

Anleitung zur konsistenten Pflege von Übersetzungen in `cover-control`.

## 1. Betroffene Dateien

Jede Text- oder Schemaänderung betrifft drei Dateien:
* `custom_components/cover_control/strings.json` (Basis-Schema / Englisch)
* `custom_components/cover_control/translations/en.json` (Englische Übersetzung)
* `custom_components/cover_control/translations/de.json` (Deutsche Übersetzung)

## 2. Struktur-Synchronität

* Alle drei Dateien müssen exakt dieselbe JSON-Schlüsselhierarchie besitzen.
* Ein neuer Schlüssel in `strings.json` muss zeitgleich in `en.json` und `de.json` ergänzt werden.

## 3. Selektor-Optionen & Fehlermeldungen

* Optionen in `selector.SelectSelectorConfig` erhalten `translation_key`. Die Werte stehen unter:
  ```json
  "selector": {
    "my_key": {
      "options": {
        "opt1": "Option 1 Text",
        "opt2": "Option 2 Text"
      }
    }
  }
  ```
* Validierungsfehler gehören unter `config.error` oder `options.error`.
* Abbrüche gehören unter `config.abort`.

## 4. Tests zur Übersetzung

```sh
.venv/bin/pytest -q tests/test_config_flow.py -k translation --asyncio-mode=auto
```
