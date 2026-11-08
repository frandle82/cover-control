---
title: Manuelle Fahrten vs. Automatische Steuerung
type: domain
status: active
tags:
  - domain
  - manual-override
  - actuator
  - events
---

# Manuelle Fahrten vs. Automatische Steuerung

## Zweck
Präzise Unterscheidung zwischen Positionsänderungen, die von `cover-control` selbst ausgelöst wurden, und solchen, die durch den Benutzer (Wandtaster, HA-App) initiiert wurden.

---

## 1. Die vier Konzepte

Es muss strikt zwischen vier Zuständen und Mechanismen unterschieden werden:

1. **Manuelle Bewegungserkennung (`manual movement detection`):**
   * Erkennt, wenn sich ein Behang bewegt hat, ohne dass Cover Control im selben Zeitfenster einen Fahrbefehl abgesetzt hat.
2. **Manueller Override-Zustand (`manual override state`):**
   * Der Zustand, in dem ein Raum als "manuell übersteuert" markiert ist und automatische Fahrten blockiert werden.
3. **Geplante Aktionshistorie (`scheduled action history`):**
   * Zeitstempel und Zielpositionen kürzlich von Cover Control versendeter Befehle.
4. **Erzwingungsaktionen (`force actions`):**
   * Aktionen von übergeordneter Priorität (z. B. Windalarm), die auch den manuellen Override aufheben oder überstimmen können.

---

## 2. Kritische Regeln zur Vermeidung von Fehlinterpretationen

* **Selbsterkennung:** Wenn Cover Control einen Fahrbefehl (`cover.set_cover_position`) absendet, wird dies im Speicher registriert. Nachfolgende Zwischenzustände (`opening`, `closing`) und das Erreichen der Zielposition dürfen **niemals** als manuelle Bewegung interpretiert werden.
* **Toleranzgrenzen:** Fahrbefehle werden nur gesendet, wenn die Abweichung zwischen Ist- und Soll-Position größer als die konfigurierte Toleranz (z. B. ±1%) ist.
* **Beschattungsadoption:** Eine abgeschlossene manuelle Bewegung auf die effektive normale Beschattungsposition innerhalb `position_tolerance` wird vor der Override-Aktivierung als `shading` übernommen. Sie gilt nur für das betroffene Cover; Heat Protection und andere bekannte Ziele werden dadurch nicht adoptiert. Verlässt der Nutzer das Ziel anschließend erneut manuell, endet der Shading-Status und der normale Override wird aktiviert.
* **Override-Rücksetzung:** Ein aktiver manueller Override wird zurückgesetzt, wenn:
  1. Die konfigurierte Ablaufzeit (Timeout) verstrichen ist.
  2. Der nächste geplante Zeitplan-Trigger (z. B. morgendliches Öffnen) eintritt.
  3. Der Benutzer den Override-Schalter manuell deaktiviert.

---
Verwandte Notizen:
* [`priorities-and-lockout.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/priorities-and-lockout.md)
* [`../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/architecture/adr-003-state-hierarchy-configured-enabled-eligible.md)
