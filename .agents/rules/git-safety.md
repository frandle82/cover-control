---
trigger: always_on
---

Git-Sicherheitsregeln – Cover Control

Verbindliche Verhaltens- und Sicherheitsregeln für die Versionsverwaltung im Repository cover-control.

1. Grundprinzipien & Arbeitsfreigabe

Arbeitsauftrag ist Handlungsfreigabe: Wenn Andreas eine Änderung, Fehlerbehebung, Fertigstellung oder einen Release beauftragt, darf Codex die zur vollständigen Erledigung notwendigen Git- und GitHub-Schritte selbstständig ausführen. Dazu gehören – soweit für den Auftrag erforderlich – Branch verwenden/erstellen, Dateien ändern, testen, committen, pushen, Pull Request erstellen/aktualisieren, CI auswerten, mergefähige Fehler beheben und den freigegebenen Release-Workflow starten.
Keine Zwischenfreigaben für Routineaktionen: Nach einem eindeutigen Auftrag nicht vor Commit, Push, PR-Erstellung, Merge oder Workflow-Dispatch erneut um Bestätigung bitten. Status berichten, aber den Ablauf nicht für Routinefreigaben unterbrechen.
Release-Auftrag: Formulierungen wie „Release erstellen“, „veröffentlichen“, „fertigstellen und releasen“ oder gleichbedeutende Anweisungen gelten als Freigabe für die komplette Release-Kette bis zur Verifikation des veröffentlichten Releases.
Änderungsschutz: Im Arbeitsverzeichnis vorhandene, nicht zum Auftrag gehörende Änderungen des Benutzers müssen erhalten bleiben. Nur auftragsbezogene Dateien committen.
Kein direktes Arbeiten auf main: Normale Entwicklungsarbeiten erfolgen auf einem dedizierten Feature-/Bugfix-Branch. Änderungen gelangen über Pull Request/Merge nach main. Der Release-Workflow darf anschließend den vorgesehenen automatischen Versions-Commit auf main erzeugen.
Sauberer Arbeitsbaum: Keine temporären Dateien, Virtualenvs, Debug-Logs, Test-Dumps oder erzeugte Archive (cover_control.zip) im Arbeitsbaum hinterlassen.
2. Wann Rückfragen wirklich erforderlich sind

Codex soll selbstständig entscheiden und fortfahren. Eine Rückfrage ist nur erforderlich, wenn mindestens einer dieser Fälle vorliegt:

eine destruktive Git-Aktion wäre nötig, insbesondere Force-Push, History-Rewrite, Hard-Reset oder das Verwerfen fremder Änderungen;
ein Merge-Konflikt lässt mehrere fachlich unterschiedliche Lösungen zu;
Tests oder Release-Gates schlagen fehl und die Ursache kann nicht sicher ohne Produktentscheidung behoben werden;
ein Secret, Token, eine Berechtigung oder ein externer manueller Schritt fehlt;
eine Breaking-Change-/Major-Entscheidung ist fachlich uneindeutig;
eine Aktion würde nicht zum Auftrag gehörende Benutzeränderungen überschreiben oder committen;
GitHub/Branch-Protection verhindert die vorgesehene Aktion und es gibt keinen sicheren alternativen Standardweg.
Nicht nachfragen bei:

eindeutig behebbaren Test-, Lint-, Format-, Translation- oder CI-Fehlern;
notwendigem Commit/Push auf dem Arbeitsbranch;
Erstellen/Aktualisieren eines PRs;
erneutem Ausführen fehlgeschlagener, nachweislich transienter Checks;
Starten des freigegebenen Release-Workflows nach bestandenem Release-Gate.
3. Commit-Standards: Caveman-Commit

Für auftragsbezogene Commits ist der Skill caveman-commit anzuwenden:

Logische Trennung: Unabhängige Änderungen in separate Commits aufteilen, sofern dies den Ablauf nicht unnötig fragmentiert.
Conventional Commits:
Gültige Typen: feat, fix, docs, refactor, test, ci, build, chore, style, perf, revert.
Scopes: In Kleinbuchstaben mit Bindestrich/Unterstrich (z. B. runtime, config, shading, events).
Format: <type>(<scope>): <kurze beschreibung> (imperativer Stil, kein Punkt am Ende, maximal 72 Zeichen).
Beispiel: feat(runtime): improve solar azimuth calculation
Body: Nur bei Breaking Changes oder Migrationen; kein Fülltext.
Validierung: Vor jedem Commit die Commit-Message validieren:
.venv/bin/python scripts/validate_commit.py --message "<subject>"
Range-Validierung: Vor Merge oder Release:
.venv/bin/python scripts/validate_commit.py --range origin/main..HEAD
4. Pull Request & Merge

Bei Arbeiten außerhalb von main darf Codex nach erfolgreicher Validierung selbstständig einen Pull Request nach main erstellen oder aktualisieren.
Titel und Beschreibung aus den tatsächlichen Änderungen und Testergebnissen ableiten; keine Rückfrage für Standardformulierungen.
Erforderliche Labels gemäß Release-Drafter-Konfiguration setzen bzw. vorhandene automatische Labels prüfen.
Wenn alle erforderlichen Checks erfolgreich sind und der PR konfliktfrei/mergefähig ist, darf Codex den PR im Rahmen eines freigegebenen Release-Auftrags selbstständig mergen.
Kein Bypass von Branch-Protection oder fehlgeschlagenen Required Checks.
Bei einem reinen Entwicklungsauftrag ohne Release/Abschlussauftrag nicht automatisch nach main mergen, sofern Andreas dies nicht erkennbar als Ziel verlangt hat.
5. Release-Verfahren auf GitHub

Authoritativer Weg: Releases werden ausschließlich über den GitHub Actions Workflow Create Release (.github/workflows/release.yml) auf main erstellt.
Keine lokalen Releases: Keine manuellen Tags, keine manuelle Versionsänderung in manifest.json und kein lokales Veröffentlichen eines Releases. Der Workflow übernimmt Versions-Commit, Tag/Release und HACS-Archiv.
Version ohne Rückfrage bestimmen: Wenn Andreas einen Release ohne Versionsnummer beauftragt, die nächste SemVer-Version anhand der vorhandenen Release-Drafter-Regeln bestimmen:
Breaking/Major → Major;
Feature/Enhancement/Minor → Minor;
Fix/Hotfix/Bug/Dependencies sowie sonstige nicht-brechende Wartungsänderungen → Patch.
Bei gemischten Änderungen gewinnt die höchste erforderliche Stufe.
Nur bei fachlich uneindeutigem Breaking Change nachfragen.
Release-Typ: Bei einer normalen Anweisung „Release“ standardmäßig release verwenden. draft oder prerelease nur verwenden, wenn Andreas dies ausdrücklich verlangt oder der aktuelle Versions-/Branchkontext eindeutig ein Prerelease ist.
Vor dem Dispatch: Sicherstellen, dass der relevante Stand auf main gemergt ist und die Release-Gates bestanden sind.
Nach dem Dispatch: Workflow bis zum Abschluss prüfen. Bei eindeutig behebbaren Fehlern selbstständig korrigieren, erneut validieren und den Workflow erneut starten. Bei transienten GitHub-Fehlern darf ohne Rückfrage erneut ausgeführt werden.
Release-Verifikation: Nach Erfolg Version, Tag/Release-Status und das angehängte cover_control.zip prüfen. Erst danach den Release als abgeschlossen melden.
6. Berichterstattung

Nach Dateiänderungen, Tests, Commits, PR/Merge und Release den relevanten Status auf Deutsch berichten.
Berichte kompakt halten: Ergebnis, Commit/PR/Release, Teststatus und echte Blocker.
Routineentscheidungen nicht als Rückfrage formulieren, wenn sie durch diese Regeln eindeutig vorgegeben sind.

## Release-Changelog und Pull-Request-Beschreibungen

Jeder Pull Request, der in einen Release eingeht, muss eine ausführliche,
benutzerorientierte Beschreibung besitzen.

Die PR-Beschreibung enthält mindestens:

- Zusammenfassung aus Anwendersicht
- Neue Funktionen
- Fehlerbehebungen
- relevante Verhaltensänderungen
- Migration/Kompatibilität, falls relevant
- wichtige technische Änderungen nur soweit für Nutzer/Betreiber relevant
- Teststatus

Keine reine Commit-Liste als PR-Beschreibung verwenden.

Release Notes werden automatisch durch Release Drafter aus den PR-Beschreibungen
erzeugt. Daher müssen PR-Bodies auch ohne Kenntnis der Commit-Historie
verständlich sein.

Vor einem Release den erzeugten Draft prüfen:
- Changelog vollständig
- keine leeren oder nichtssagenden PR-Beschreibungen
- keine internen Debug-/Arbeitsnotizen
- Breaking Changes klar hervorgehoben
- Migrationen und notwendige Nutzeraktionen genannt