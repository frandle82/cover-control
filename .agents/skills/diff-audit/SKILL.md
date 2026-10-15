---
name: diff-audit
description: Schnelles, automatisiertes Auditieren von Änderungen vor Abschluss einer Aufgabe zur Vermeidung von Fehlern und Nacharbeiten.
---

# Diff Audit Skill

Stellt sicher, dass Änderungen sauber, vollständig und frei von unerwünschten Seiteneffekten sind.

## 1. Audit-Checkliste vor Fertigstellung

* [ ] **Scope-Prüfung:** `git diff` prüfen. Wurden ausschließlich Dateien geändert, die zur Aufgabenstellung gehören?
* [ ] **Schutz des Nutzerstands:** Wurden unbeteiligte Änderungen des Benutzers im Arbeitsbaum unangetastet gelassen?
* [ ] **Whitespace & Syntax:**
  ```sh
  git diff --check
  .venv/bin/python -m compileall -q custom_components tests scripts
  ```
* [ ] **Keine Artefakte:** Wurden temporäre Testdateien, ZIP-Dateien oder Debug-Prints (`print(...)`) restlos entfernt?
* [ ] **Tests grün:** Vollständige Testsuite ohne Regressionen bestanden:
  ```sh
  .venv/bin/pytest -q --asyncio-mode=auto
  ```
* [ ] **Übersetzungssynchronität:** Falls Texte geändert wurden: `strings.json`, `en.json` und `de.json` synchron?
