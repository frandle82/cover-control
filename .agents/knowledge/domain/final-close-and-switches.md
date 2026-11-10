---
title: Final Close und funktionsabhängige Schalter
type: domain
status: active
tags:
  - schedule
  - solar-elevation
  - entities
  - translations
---

# Final Close und funktionsabhängige Schalter

## Bestätigte Invarianten

- Automationsschalter existieren nur, wenn die zugehörige Funktion durch Gruppen-, Raum- oder Override-Schlüssel konfiguriert ist. Ein zur Laufzeit ausgeschalteter Schalter entfernt die Konfiguration nicht.
- Das vollständige Schließen unterstützt unabhängige Auslöser für Uhrzeit und fallende Sonnenhöhe. Der früheste gültige Auslöser gewinnt.
- Die Sonnenrichtung wird astronomisch aus der aktuellen Sonnenhöhe und ihrer unmittelbar folgenden Entwicklung bestimmt. Lokale Uhrzeiten sind kein Richtungsersatz.
- Beim Start wertet Cover Control den aktuellen Sonnenzustand aus. Liegt die Sonne abends bereits unter der Schwelle und fällt weiter, erfolgt das vollständige Schließen ohne vorheriges State-Change-Ereignis.
- Ein vollständiges Schließen wird pro Kalendertag nur einmal ausgelöst. Sommer-, Weihnachts-, Fenster- und Sicherheitsregeln bleiben im normalen Auswertungspfad erhalten.
- Menüpunkte benennen eine Funktion; ihre Beschreibungen erklären den konfigurierbaren Inhalt und dürfen den Titel nicht nur wiederholen.

---
Verwandte Notizen:
* [`shading-and-solar-geometry.md`](shading-and-solar-geometry.md)
* [`../troubleshooting/entity-registry-cleanup.md`](../troubleshooting/entity-registry-cleanup.md)
