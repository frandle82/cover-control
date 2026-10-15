---
name: token-budget
description: Best Practices zur Schonung des Kontextfensters und Reduzierung von Tool-Overhead bei Code-Inspektion und Ausführung.
---

# Token Budget & Context Optimizer Skill

Verhindert Context-Rot und schont das Token-Budget bei umfangreichen Repositories.

## 1. Gezielte Suche statt Komplettauslese

* **Niemals ganze Großdateien lesen:** Dateien mit hunderten Zeilen nicht ungeschnitten in den Kontext laden.
* **Grep vor View:** Relevante Stellen mit `grep_search` oder `rg` lokalisieren.
* **Slice-Notation nutzen:** Bei `view_file` immer `StartLine` und `EndLine` einschränken (z. B. auf 30–50 relevante Zeilen).

## 2. Testläufe budgetieren

* **Nicht sofort die Gesamttestsuite starten:** Bei Änderungen zunächst nur den spezifischen Test aufrufen:
  ```sh
  .venv/bin/pytest -q tests/test_config_flow.py -k test_my_feature --asyncio-mode=auto
  ```
* **Ausgabe kurz halten:** Immer `-q` (quiet) nutzen. Fehlerausgaben mit `--tb=short` begrenzen, falls Stacktraces den Kontext fluten.
* **Volle Testsuite nur als Gate:** Gesamtlauf (`.venv/bin/pytest -q --asyncio-mode=auto`) erst ausführen, wenn die Einzelfunktion grün ist.

## 3. Tool-Aufrufe minimieren

* Mehrere zusammengehörige Lese- oder Prüfschritte vorbereiten und unnötige Zwischenschritte vermeiden.
* Vor dem Editieren sicherstellen, dass die Zielstelle eindeutig ist.
