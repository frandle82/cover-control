---
title: Map of Content (MOC) – Cover Control Knowledge Base
type: index
updated: 2026-11-12
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
* 📄 [`architecture/adr-002-config-entry-vs-subentry.md`](architecture/adr-002-config-entry-vs-subentry.md) – Zentraler Controller mit drei festen Gruppen plus eigenständige Room-ConfigEntries; Subentries bleiben deaktiviert.
* 📄 [`architecture/adr-003-state-hierarchy-configured-enabled-eligible.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/architecture/adr-003-state-hierarchy-configured-enabled-eligible.md) – Das dreistufige Zustandsmodell für Gruppenfunktionen.
* 📄 [`architecture/adr-004-background-effective-targets.md`](architecture/adr-004-background-effective-targets.md) – Kanonischer Background-State, zentraler Effective-Resolver und direkter Restore nach temporären Overrides.

### 2. Domänenwissen & Steuerungslogik
Fachliche Regeln für Beschattung, Fahrbefehle und Prioritäten:
* 📄 [`ioBroker-shuttercontrol.md`](ioBroker-shuttercontrol.md) – Fixierte Quellcodeanalyse von ioBroker.shuttercontrol 2.1.2 einschließlich reduzierter Runtime-Invarianten, Safety, No-Go-Time, gestuftem und saisonalem Schließen, Heat Protection und Fenster-Lüftungsfahrt.
* 📄 [`domain/priorities-and-lockout.md`](domain/priorities-and-lockout.md) – Feste Prioritäten mit Safety und Window/Lockout vor Komfortautomation; keine generischen CCA-Overrides.
* 📄 [`domain/shading-and-solar-geometry.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/shading-and-solar-geometry.md) – Feste Shuttercontrol-Sonnenschutzmodi, Direction-Geometrie und prozentuale Endhysterese.
* 📄 [`domain/manual-override-vs-automation.md`](domain/manual-override-vs-automation.md) – Einheitliche Automatikpause, Restart-/Ablaufsemantik und toleranzbasierte Adoption der effektiven Beschattungsposition.
* 📄 [`domain/tilt-and-raffstore.md`](domain/tilt-and-raffstore.md) – Capability-gesteuertes Tilt-Modell mit vier physischen Raumzielen und fester Aktorsequenz.
* 📄 [`domain/final-close-and-switches.md`](domain/final-close-and-switches.md) – Unabhängige Final-Close-Auslöser, astronomische Fallrichtung und funktionsabhängige Laufzeitschalter.

### 3. Troubleshooting, Fallstricke & Lessons Learned
Dokumentierte Lösungen für knifflige Bugs und HA-Spezifika:
* 📄 [`troubleshooting/entity-registry-cleanup.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/entity-registry-cleanup.md) – Lifecycle-Bereinigung verwaister Entitäten bei Raumänderungen.
* 📄 [`troubleshooting/home-assistant-async-guidelines.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/home-assistant-async-guidelines.md) – Vermeidung blockierender I/O im Event-Loop und sauberes Unload.
* 📄 [`troubleshooting/stable-sun-events-and-active-controls.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/troubleshooting/stable-sun-events-and-active-controls.md) – Deterministische Astro-Ereignisse und getrennte Erfassung aktiver Entscheidungs-Controls.
* 📄 [`troubleshooting/contact-runtime-path.md`](troubleshooting/contact-runtime-path.md) – Cover-lokale Contact-Maps, Ventilation-Feature-Erkennung und Listener-Rebinding.

---

## 🔄 Wie dieses Wissen genutzt und erweitert wird

1. **Vor Beginn einer Aufgabe (Retrieval):**
   * Prüfe dieses Inhaltsverzeichnis und die relevanten Notizen nach bestehenden Mustern und Entscheidungen (Skill [`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md)).
2. **Nach Lösung eines Problems oder neuer Architekturentscheidung (Capture):**
   * Halte neues Wissen sofort als Markdown-Notiz in der passenden Kategorie fest.
   * Verlinke die neue Notiz hier im `INDEX.md`.
   * Verwende Querverweise zwischen Notizen für ein vernetztes Wissensnetz.
