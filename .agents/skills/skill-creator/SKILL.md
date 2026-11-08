---
name: skill-creator
description: Workflow-Automatisierung und Standardisierung. Überführt bewährte Praktiken und einmalige Sitzungen in wiederverwendbare SKILL.md-Dateien.
---

# Skill-Creator Skill – Workflow-Standardisierung

## Zweck

Analysiert erfolgreiche Arbeitsabläufe, Problemlösungen oder wiederkehrende Entwickler-Routinen und überführt sie in eine strukturierte, wiederverwendbare `SKILL.md`-Datei im Verzeichnis `.agents/skills/<skill-name>/`.

**Vorteil:** Verhindert Wissensverlust, standardisiert Best Practices für das Projektteam und sorgt dafür, dass KI-Agenten konsistent nach denselben Mustern agieren.

---

## Wann anwenden?

* Wenn ein komplexer Workflow (z. B. eine neue Testmethode, ein Deployment-Schritt oder ein API-Integrationsmuster) erfolgreich gemeistert wurde.
* Wenn wiederkehrende Fehler durch einen klaren Prozess vermieden werden sollen.
* Wenn Andreas oder das Team neue Richtlinien etablieren möchten.

---

## Aufbau einer SKILL.md-Datei

Jeder Skill in `.agents/skills/<skill-name>/SKILL.md` folgt diesem Standardaufbau:

```markdown
---
name: <kebab-case-name>
description: <Ein- bis zweisätzige prägnante Beschreibung des Zwecks und Einsatzgebiets.>
---

# <Name> Skill – <Untertitel>

## Zweck
<!-- Warum existiert dieser Skill? Welcher Nutzen entsteht? -->

## Wann anwenden?
<!-- Konkrete Trigger und Szenarien für den Einsatz dieses Skills. -->

## Kern-Workflow
<!-- Schritt-für-Schritt-Anleitung mit exakten CLI-Befehlen und Code-Mustern. -->

## Checkliste / Kriterien
<!-- Eindeutig überprüfbare Kriterien für Erfolg und Qualität. -->

## Anti-Patterns / Häufige Fehler
<!-- Was darf NICHT getan werden? Typische Stolperfallen. -->
```

---

## Der 4-Schritte-Erstellungsprozess

### 1. Workflow isolieren & Scope definieren
* Welches Problem hat die Sitzung gelöst?
* Welche CLI-Befehle oder Codemuster waren entscheidend?
* Was ist projektspezifisch für `cover-control` (z. B. Mixin-Architektur, pytest-homeassistant) und was ist allgemein?

### 2. Skill-Datei anlegen
* Verzeichnis erstellen: `.agents/skills/<skill-name>/`
* Datei erstellen: `.agents/skills/<skill-name>/SKILL.md`
* YAML Frontmatter mit eindeutigem Namen und prägnanter Beschreibung versehen.
* Konkrete Befehle angeben (immer `.venv/bin/...` für lokale Virtualenv-Befehle nutzen).

### 3. Konsistenz & Qualität prüfen
* [ ] Frontmatter valide (`name`, `description`).
* [ ] Sprache ist Deutsch (für Anweisungen und Erklärungen) bzw. Englisch für standardisierte Code-Begriffe.
* [ ] Keine redundanten Überschneidungen mit bestehenden Skills; stattdessen auf verwandte Skills verweisen.
* [ ] Befehle sind copy-paste-fähig und direkt ausführbar.

### 4. Integration in AGENTS.md und Rules
* Den neuen Skill in `AGENTS.md` in der Liste der verfügbaren Skills eintragen.
* Falls relevant: In `.agents/rules/` referenzieren (z. B. in `quality.md` oder `project.md`).
