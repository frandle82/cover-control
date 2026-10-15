# Git-Sicherheitsregeln – Cover Control

Verbindliche Verhaltens- und Sicherheitsregeln für die Versionsverwaltung im Repository `cover-control`.

## 1. Grundprinzipien & Berechtigungen

* **Keine eigenmächtigen Aktionen:** Niemals selbstständig Commits, Pushes, Tags, Pull Requests, Releases oder Branch-Merges durchführen. Dies geschieht **ausschließlich auf ausdrückliche Anweisung von Andreas**.
* **Änderungsschutz:** Im Arbeitsverzeichnis vorhandene Änderungen des Benutzers (`git status`) müssen ausnahmslos erhalten bleiben.
* **Keine Commits auf `main`:** Normale Entwicklungsarbeiten erfolgen immer auf einem dedizierten Feature-/Bugfix-Branch.
* **Sauberer Arbeitsbaum:** Keine temporären Dateien, Virtualenvs, Debug-Logs, Test-Dumps oder erzeugte Archive (`cover_control.zip`) im Arbeitsbaum hinterlassen.

## 2. Commit-Standards: Caveman-Commit (bei Beauftragung durch Andreas)

Wenn ein Commit ausdrücklich beauftragt wird, ist der Skill `caveman-commit` anzuwenden:

* **Logische Trennung:** Unabhängige Änderungen in separate Commits aufteilen.
* **Conventional Commits:**
  * Gültige Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`, `style`, `perf`, `revert`.
  * Scopes: In Kleinbuchstaben mit Bindestrich/Unterstrich (z. B. `runtime`, `config`, `shading`, `events`).
  * Format: `<type>(<scope>): <kurze beschreibung>` (imperativer Stil, kein Punkt am Ende, maximal 72 Zeichen).
  * Beispiel: `feat(runtime): improve solar azimuth calculation`
  * Body: Nur bei Breaking Changes oder Migrationen; kein Fülltext.
* **Validierung:** Vor jedem Commit die Commit-Message validieren:
  ```sh
  .venv/bin/python scripts/validate_commit.py --message "<subject>"
  ```
* **Range-Validierung:** Vor dem Abschluss einer Verzweigung:
  ```sh
  .venv/bin/python scripts/validate_commit.py --range origin/main..HEAD
  ```

## 3. Release-Verfahren auf GitHub

* **GitHub Actions Workflow:** Releases werden ausschließlich über den GitHub Actions Workflow ("Create Release") auf GitHub erstellt.
* **Keine lokalen Releases:** Codex führt keine manuellen Versionserhöhungen in `manifest.json`, keine manuellen Tags und keine Release-Builds (`build_release.py`) im lokalen Arbeitsbaum durch.

## 4. Berichterstattung

* Nach allen Dateiänderungen, Tests oder Teilaufgaben immer den aktuellen `git status` und die ausgeführten Tests auf **Deutsch** berichten.
