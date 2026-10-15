# Git-Sicherheitsregeln – Cover Control

Verbindliche Verhaltens- und Sicherheitsregeln für die Versionsverwaltung im Repository `cover-control`.

## 1. Grundprinzipien & Berechtigungen

* **Keine eigenmächtigen Aktionen:** Niemals selbstständig Commits, Pushes, Tags, Pull Requests, Releases oder Branch-Merges durchführen. Dies geschieht **ausschließlich auf ausdrückliche Anweisung von Andreas**.
* **Änderungsschutz:** Im Arbeitsverzeichnis vorhandene Änderungen des Benutzers (`git status`) müssen ausnahmslos erhalten bleiben.
* **Keine Commits auf `main`:** Normale Entwicklungsarbeiten erfolgen immer auf einem dedizierten Feature-/Bugfix-Branch.
* **Sauberer Arbeitsbaum:** Keine temporären Dateien, Virtualenvs, Debug-Logs, Test-Dumps oder erzeugte Archive (`cover_control.zip`) im Arbeitsbaum hinterlassen.

## 2. Commit-Standards (bei Beauftragung durch Andreas)

Wenn ein Commit ausdrücklich beauftragt wird, müssen folgende Regeln eingehalten werden:

* **Logische Trennung:** Unabhängige Änderungen in separate Commits aufteilen.
* **Conventional Commits:**
  * Gültige Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`, `style`, `perf`, `revert`.
  * Scopes: In Kleinbuchstaben mit Bindestrich/Unterstrich (z. B. `runtime`, `config`, `release`, `shading`).
  * Format: `<type>(<scope>): <kurze beschreibung>` (kein Punkt am Ende).
  * Beispiel: `feat(runtime): improve solar azimuth calculation`
* **Validierung:** Vor jedem Commit die Commit-Message validieren:
  ```sh
  .venv/bin/python scripts/validate_commit.py --message "<subject>"
  ```
* **Range-Validierung:** Vor dem Abschluss einer Verzweigung:
  ```sh
  .venv/bin/python scripts/validate_commit.py --range origin/main..HEAD
  ```

## 3. Release-Verfahren (bei Beauftragung durch Andreas)

* **Keine manuellen Version-Bumps:** Versionsnummern in `manifest.json` oder anderen Dateien niemals manuell für normale Features/Fixes erhöhen.
* **Keine manuellen Tags:** Release-Tags werden nicht manuell erstellt.
* **Prüfung und Build:**
  ```sh
  .venv/bin/python scripts/verify_release.py --skip-tag
  .venv/bin/python scripts/build_release.py
  .venv/bin/python scripts/verify_release.py --archive --skip-tag
  rm -f cover_control.zip
  ```

## 4. Berichterstattung

* Nach allen Dateiänderungen, Tests oder Teilaufgaben immer den aktuellen `git status` und die ausgeführten Tests auf **Deutsch** berichten.
