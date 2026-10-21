---
title: Map of Content (MOC) – Cover Control Knowledge Base
type: index
updated: 2026-10-21
tags:
  - moc
  - index
  - knowledge-base
---

# 🧠 Cover Control Knowledge Base (Local Obsidian Vault)

Willkommen in der internen Wissensdatenbank von `cover-control`. Dieser Ordner dient als lokales „Second Brain“ des Projekts und hält Architekturentscheidungen, Domänenkonzepte, Troubleshooting-Leitfäden und Workflows fest und vernetzt sie.

---

## 🗺️ Inhaltsverzeichnis (Map of Content)

### 1. Architektur & Designentscheidungen (ADRs)
Grundsatzentscheidungen zur Struktur, Datenhaltung und Integration:
* 📄 [`architecture/adr-001-mixin-architecture.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/architecture/adr-001-mixin-architecture.md) – Aufteilung der Controller-Verantwortlichkeiten auf spezialisierte Mixins.
* 📄 [`architecture/adr-002-config-entry-vs-subentry.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/architecture/adr-002-config-entry-vs-subentry.md) – Single Config Entry Modell vs. Subentries und Reconfigure Flow.
* 📄 [`architecture/adr-003-state-hierarchy-configured-enabled-eligible.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/architecture/adr-003-state-hierarchy-configured-enabled-eligible.md) – Das dreistufige Zustandsmodell für Profilfunktionen.

### 2. Domänenwissen & Steuerungslogik
Fachliche Regeln für Beschattung, Fahrbefehle und Prioritäten:
* 📄 [`domain/priorities-and-lockout.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/priorities-and-lockout.md) – Die Prioritätenhierarchie: Lockout > Force > Manual Override > Ventilation > Shading > Resident.
* 📄 [`domain/shading-and-solar-geometry.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/shading-and-solar-geometry.md) – Sonnenberechnung (Azimut, Elevation), Hysterese und Wetterbewertung.
* 📄 [`domain/manual-override-vs-automation.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/manual-override-vs-automation.md) – Erkennung manueller Fahrten vs. automatischer Steuerung.

### 3. Troubleshooting, Fallstricke & Lessons Learned
Dokumentierte Lösungen für knifflige Bugs und HA-Spezifika:
* 📄 [`troubleshooting/entity-registry-cleanup.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/entity-registry-cleanup.md) – Lifecycle-Bereinigung verwaister Entitäten bei Raum- und Profiländerungen.
* 📄 [`troubleshooting/home-assistant-async-guidelines.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/home-assistant-async-guidelines.md) – Vermeidung blockierender I/O im Event-Loop und sauberes Unload.
* 📄 [`troubleshooting/stable-sun-events-and-active-controls.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/stable-sun-events-and-active-controls.md) – Stabile Sun-Duration-Ereignisse und getrennte Erfassung aktiver Entscheidungs-Controls.

---

## 🔄 Wie dieses Wissen genutzt und erweitert wird

1. **Vor Beginn einer Aufgabe (Retrieval):**
   * Prüfe dieses Inhaltsverzeichnis und die relevanten Notizen nach bestehenden Mustern und Entscheidungen (Skill [`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md)).
2. **Nach Lösung eines Problems oder neuer Architekturentscheidung (Capture):**
   * Halte neues Wissen sofort als Markdown-Notiz in der passenden Kategorie fest.
   * Verlinke die neue Notiz hier im `INDEX.md`.
   * Verwende Querverweise zwischen Notizen für ein vernetztes Wissensnetz.
