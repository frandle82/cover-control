---
name: knowledge
description: Verwaltet das interne Second Brain (.agents/knowledge/) im Obsidian-Stil. Wissensabruf vor Aufgaben und strukturierte Wissensaufnahme nach Erkenntnissen oder Architekturentscheidungen.
---

# Knowledge Skill – Internes Wissenssystem (Obsidian-Vault)

## Zweck

Dieser Skill verwandelt das Verzeichnis `.agents/knowledge/` in ein vernetztes, lokales „Second Brain“ (analog zu einem Obsidian-Vault). Es stellt sicher, dass wertvolles Projektwissen, architektonische Grundsatzentscheidungen (ADRs), Domänenlogik und Troubleshooting-Lösungen persistent festgehalten, verlinkt und vor jeder Aufgabe aktiv abgefragt werden.

**Vorteil:** Verhindert das Wiederholen von Fehlern, bewahrt Architekturprinzipien über Sitzungen hinweg und macht externes Wissen lokal und offline sofort nutzbar – ohne externe MCP- oder Cloud-Abhängigkeiten.

---

## 1. Verzeichnisstruktur des Wissenssystems

```
.agents/knowledge/
├── INDEX.md               # Map of Content (MOC): Zentraler Einstiegspunkt und Themenverzeichnis
├── architecture/          # Architekturentscheidungen (ADR-001, ADR-002, ...)
├── domain/                # Fachliches Domänenwissen (Prioritäten, Geometrie, Override)
└── troubleshooting/       # Gelöste Bugs, HA-Eigenarten, Async-Best-Practices
```

---

## 2. Der Retrieval-Workflow (Wissensabruf)

**Wann:** Vor Beginn von Anforderungsanalysen (`grill-me`), Konzeptionen, Code-Änderungen oder Bug-Diagnosen.

1. **Index konsultieren:**
   Lies zuerst [`.agents/knowledge/INDEX.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/INDEX.md), um einen Überblick über vorhandene Themen und ADRs zu erhalten.
2. **Relevante Notizen öffnen:**
   Lies die für deine Aufgabe relevanten Notizen (z. B. bei Beschattungsfragen `domain/shading-and-solar-geometry.md` oder bei Lifecycle-Fragen `troubleshooting/entity-registry-cleanup.md`).
3. **Erkenntnisse einbinden:**
   Nutze das dokumentierte Wissen, um bestehende Muster wiederzuverwenden und Architekturbrüche zu vermeiden.

---

## 3. Der Capture-Workflow (Wissensaufnahme)

**Wann:**
* Nach dem Treffen einer neuen Architekturentscheidung (z. B. Aufteilung eines neuen Moduls, Migration).
* Nach dem Beheben eines vertrackten Fehlers oder einer Home Assistant Eigenheit.
* Nach dem Hinzufügen oder Verändern komplexer Domänenlogik (z. B. neue Hystereseregeln, Berechnungen).

### Schritt-für-Schritt-Aufnahme:

1. **Kategorie wählen:**
   * Architekturentscheidung / Grundsatzfrage → `.agents/knowledge/architecture/adr-XXX-<titel>.md`
   * Fachliche Logik, Berechnungen, Schwellenwerte → `.agents/knowledge/domain/<titel>.md`
   * Gelöstes Problem, Bug-Analyse, Fallstrick → `.agents/knowledge/troubleshooting/<titel>.md`
2. **Notiz nach Obsidian-Standard erstellen:**
   Jede Notiz enthält YAML-Frontmatter und Querverweise:
   ```markdown
   ---
   title: <Prägnanter Titel>
   type: adr | domain | troubleshooting | workflow
   status: active | accepted | superseded
   tags:
     - tag1
     - tag2
   ---

   # <Titel>

   ## Kontext / Problem
   <!-- Was war die Ausgangslage? Welches Problem wurde gelöst? -->

   ## Entscheidung / Lösung
   <!-- Wie wurde es gelöst? Welche Regeln gelten ab jetzt? -->

   ## Konsequenzen / Wichtige Hinweise
   <!-- Was muss bei künftigen Änderungen beachtet werden? -->

   ---
   Verwandte Notizen:
   * [`../domain/<andere-notiz>.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/<andere-notiz>.md)
   ```
3. **Im Index verlinken:**
   Öffne [`.agents/knowledge/INDEX.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/INDEX.md) und trage die neue Notiz mit Kurzbeschreibung in den passenden Abschnitt ein.

---

## 4. Qualitätsregeln für das Wissensnetzwerk

* **Vernetzung statt Inseln:** Jede Notiz sollte mindestens eine Querverlinkung zu einer verwandten Notiz enthalten.
* **Prägnant & Umsetzbar:** Keine ausufernden Essays; Fokus auf konkrete Regeln, Code-Snippets und nachvollziehbare Rationale.
* **Aktualität:** Wenn sich Architekturregeln ändern, Notiz aktualisieren oder mit `status: superseded` kennzeichnen und auf die neue verlinken.
* **Reines Markdown:** Alle Notizen sind 100% standardkonformes GitHub-Flavored-Markdown.
