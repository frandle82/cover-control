---
title: "ADR-004: Background- und Effective-Target trennen"
type: adr
status: accepted
date: 2026-11-12
tags:
  - architecture
  - runtime
  - targets
  - ventilation
---

# ADR-004: Background- und Effective-Target trennen

## Kontext / Problem

`_target` und `_reason` dienten gleichzeitig als Fahrziel, Persistenzzustand,
Manual-Detection-Referenz und indirekter Restore-Zustand. Fensterlüftung hielt
zusätzlich eine physische Restore-Position und grobe Open/Close/Shading-Flags.
Dadurch konnte eine temporäre Überlagerung einen neueren normalen Sollzustand,
insbesondere Final Close nach Intermediate Close, verlieren.

## Entscheidung / Lösung

Jeder Cover-Controller führt drei getrennte Ebenen:

- `background_target` / `background_reason`: zuletzt gültige normale
  Automationsentscheidung; wird auch unter Safety, Manual Override und Fenster
  kontinuierlich aktualisiert und persistiert.
- `effective_target` / `effective_reason`: vom zentralen Resolver tatsächlich
  ausgewähltes Ziel mit der Priorität Safety > Manual > Window > Background.
- `actual_position`: ausschließlich die aktuelle Home-Assistant-Coverposition.

Temporäre Overrides verändern niemals den Background. Nach ihrem Ende wird der
aktuelle Background direkt angewandt; eine Fensterfahrt besitzt keinen eigenen
persistierten Restore-Zustand. `ventilation.restore_position` wird ausschließlich
beim Laden alter Daten gelesen und danach aus dem gespeicherten Status entfernt.
Top-Level-`target`/`reason` werden ebenso nur einmalig normalisiert; neu
persistiert werden ausschließlich `background` und `effective`. `_target` und
`_reason` bleiben vorerst schmale Runtime-Kompatibilitätsalias für die
Manuell-Erkennung, bilden aber keinen separaten Zustand.

Persistierte Altstände ohne `background` übernehmen einmalig das bisherige
Top-Level-`target`/`reason`. Startup hydriert den Zustand, evaluiert aktuelle
Bedingungen neu und unterdrückt die ungeprüfte erste Fahrt.

## Konsequenzen / Wichtige Hinweise

- Zeit, Sonne, Helligkeit, Kalender, Resident, Shading und Heat Protection
  schreiben ausschließlich den Background.
- Fensterziele sind cover-lokal; gruppenweite Background-Entscheidungen dürfen
  Effective-State anderer Covers nicht vermischen.
- Effective-Fahrten bleiben durch Istposition und Toleranz dedupliziert.
- Neue Restore-Sonderlogik oder parallele Background-Flags sind unzulässig.
- Background-Reasons werden über eine zentrale explizite Klassifikation
  (`BACKGROUND_REASON_KIND`) kategorisiert; keine Stringteiltreffer als
  Steuerungsgrundlage.

---
Verwandte Notizen:
* [`../domain/priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../domain/manual-override-vs-automation.md`](../domain/manual-override-vs-automation.md)
* [`adr-001-mixin-architecture.md`](adr-001-mixin-architecture.md)
