---
name: gh-fix-ci
description: Automatisiertes Debugging von fehlgeschlagenen GitHub CI-Checks. Analysiert Workflow-Logs, isoliert Fehlerursachen und leitet gezielte Korrekturen ab.
---

# GH-Fix-CI Skill – Automatisiertes CI-Debugging

## Zweck

Klinkt sich in fehlgeschlagene GitHub Actions CI-Läufe ein, extrahiert die relevanten Fehler-Logs, isoliert die exakte Fehlerursache und führt eine zielgerichtete lokale Reproduktion und Behebung durch.

**Vorteil:** Schnelle, systematische Pipeline-Reparatur ohne manuelles Suchen in GitHub-Web-Logs.

---

## Wann anwenden?

* Sobald ein PR-Check oder GitHub Actions Workflow (`ci.yml`, `validate.yml`, `release.yml`) fehlschlägt.
* Wenn Remote-CI-Tests ein Verhalten zeigen, das lokal nicht sofort sichtbar war (z. B. Python-Versionsmatrix, GitHub-Runner-Unterschiede).

---

## 4-Schritte-Workflow

### 1. CI-Status & fehlerhaften Lauf ermitteln

```sh
# Letzte Workflow-Läufe anzeigen
gh run list --limit 5

# Status des aktuellen PRs anzeigen
gh pr checks
```

Notiere die `RUN_ID` des fehlgeschlagenen Laufs.

### 2. Fehler-Logs extrahieren

```sh
# Nur die fehlgeschlagenen Schritte und Logs ausgeben
gh run view <RUN_ID> --log-failed

# Alternativ: Details zu einem bestimmten Job anzeigen
gh run view <RUN_ID> --job <JOB_ID> --log
```

### 3. Fehlerursache klassifizieren

Die häufigsten CI-Fehlerkategorien in Home Assistant Integrationen:

| Kategorie | Typische Symptome | Prüfpfad |
|---|---|---|
| **Test-Regression** | `FAILED tests/test_... - AssertionError` | Betroffenen Test lokal fokussiert ausführen |
| **Lint / Format** | `flake8`, `ruff`, `black` oder `git diff --check` schlägt fehl | Whitespace, trailing lines, ungenutzte Imports prüfen |
| **Typisierung** | `mypy` Fehler oder `compileall` SyntaxError | `.venv/bin/python -m compileall -q custom_components tests scripts` |
| **Übersetzung** | Missing translation key, JSON-Syntax-Fehler | `strings.json`, `en.json`, `de.json` validieren |
| **Matrix-Konflikt** | Test grün auf Python 3.12, rot auf 3.13 (oder HA stable vs. dev) | Deprecations oder API-Drift in neueren Versionen prüfen |
| **Commit-Validierung** | `validate_commit.py` scheitert | Commit-Message nach Conventional Commits korrigieren |

### 4. Lokal isolieren, beheben & verifizieren

1. **Lokal reproduzieren:**
   ```sh
   # Exakten Testbefehl ausführen, der im CI gescheitert ist
   .venv/bin/pytest -q tests/test_<name>.py::<test_func> --asyncio-mode=auto
   ```
2. **Minimalen Fix anwenden:**
   * Ursache im Code beheben (kein Symptom-Fixing, keine Abschwächung von Tests).
   * Falls CI-spezifisch: Runner-Eigenheiten oder Zeitabhängigkeiten (Timezone, UTC) absichern.
3. **Lokale Release-Gates verifizieren:**
   ```sh
   .venv/bin/pytest -q --asyncio-mode=auto
   .venv/bin/python -m compileall -q custom_components tests scripts
   git diff --check
   ```
4. **Fix pushen und CI erneut prüfen:**
   ```sh
   git commit -m "fix(ci): <beschreibung>"
   git push
   gh pr checks --watch
   ```

---

## Anti-Patterns

* ❌ *Blindes Raten:* Commits ins CI "werfen", um zu sehen, ob es grün wird.
* ❌ *Tests auskommentieren:* Fehlgeschlagene Tests deaktivieren oder `@pytest.mark.skip` setzen, ohne die Ursache zu verstehen.
* ❌ *Log-Überflutung:* Riesige Logfiles unstrukturiert durchgehen, statt `--log-failed` zu filtern.
