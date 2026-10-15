---
name: caveman-commit
description: Ultra-kompakter Conventional-Commit-Generator für Codex. Erzeugt präzise, fluff-freie Commit-Nachrichten nach Conventional Commits ohne überflüssige Tokens.
---

# Caveman Commit Skill

Generiert prägnante, normgerechte Commit-Nachrichten nach Conventional Commits ohne jeglichen Fülltext.
*"Focus on why, not what. Diff show what."*

## 1. Format & Regeln

```
<type>(<scope>): <prägnante beschreibung>

[optionaler body - nur wenn begründung nicht offensichtlich]
```

### Strikte Formatregeln
* **Imperativer Stil:** `add`, `fix`, `refactor`, `remove` (nicht: `added`, `fixes`, `refactoring`).
* **Länge:** Betreff ideal $\le 50$ Zeichen, maximal 72 Zeichen.
* **Kein Punkt:** Niemals ein Satzzeichen (`.`) am Ende der Betreffzeile.
* **Scopes kleingeschrieben:** Z. B. `runtime`, `config`, `shading`, `events`, `test`.
* **Kein Fluff:** Keine Einleitung, kein "This commit does...", keine AI-Attribution.
* **Zulässige Typen:** `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`, `style`, `perf`, `revert`.
* **Body nur bei Bedarf:** Wenn der Betreff selbsterklärend ist, KEINEN Body anfügen. Body nur für Breaking Changes (`BREAKING CHANGE: ...`), Migrationen oder Issue-Referenzen (`Closes #123`).

## 2. Validierung im Projekt

Vor der Erstellung immer mit dem internen Validator prüfen:
```sh
.venv/bin/python scripts/validate_commit.py --message "<subject>"
```

Vor Abschluss eines Branches den gesamten Commit-Range validieren:
```sh
.venv/bin/python scripts/validate_commit.py --range origin/main..HEAD
```

## 3. Beispiele

* ❌ `feat(runtime): I have updated the azimuth calculation to fix the edge case where sun is low.`
* ✅ `feat(runtime): fix azimuth calculation for low sun elevation`
* ❌ `fix: bug fixes in config flow.`
* ✅ `fix(config): prevent abort on room profile re-assignment`
* ❌ `refactor(tests): clean up test cases.`
* ✅ `refactor(tests): consolidate duplicate mock config entries`
