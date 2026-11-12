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

## 1. Die drei Konzepte

Es muss strikt zwischen drei Zuständen und Mechanismen unterschieden werden:

1. **Manuelle Bewegungserkennung (`manual movement detection`):**
   * Erkennt, wenn sich ein Behang bewegt hat, ohne dass Cover Control im selben Zeitfenster einen Fahrbefehl abgesetzt hat.
2. **Manueller Override-Zustand (`manual override state`):**
   * Der Zustand, in dem ein Raum als "manuell übersteuert" markiert ist und automatische Fahrten blockiert werden.
3. **Geplante Aktionshistorie (`scheduled action history`):**
   * Zeitstempel und Zielpositionen kürzlich von Cover Control versendeter Befehle.

---

## 2. Kritische Regeln zur Vermeidung von Fehlinterpretationen

* **Selbsterkennung:** Wenn Cover Control einen Fahrbefehl (`cover.set_cover_position`) absendet, wird dies im Speicher registriert. Nachfolgende Zwischenzustände (`opening`, `closing`) und das Erreichen der Zielposition dürfen **niemals** als manuelle Bewegung interpretiert werden.
* **Toleranzgrenzen:** Fahrbefehle werden nur gesendet, wenn die Abweichung zwischen Ist- und Soll-Position größer als die konfigurierte Toleranz (z. B. ±1%) ist.
* **Beschattungsadoption:** Eine abgeschlossene manuelle Bewegung auf die effektive normale Beschattungsposition innerhalb `position_tolerance` wird vor der Override-Aktivierung als `shading` übernommen. Sie gilt nur für das betroffene Cover; Heat Protection und andere bekannte Ziele werden dadurch nicht adoptiert. Verlässt der Nutzer das Ziel anschließend erneut manuell, endet der Shading-Status und der normale Override wird aktiviert.
* **Override-Rücksetzung:** Ein aktiver manueller Override wird zurückgesetzt, wenn:
  1. Die konfigurierte Dauer verstrichen ist.
  2. Der Benutzer den Clear-Button betätigt.
  Eine Dauer von `0` bedeutet, dass der Zustand bis zum expliziten Löschen aktiv bleibt.
  Der Reset bereinigt zentral Laufzeitstatus, Ablauf-Timer und den persistierten
  `manual`-Block einschließlich `active`, `until` und `ts`, bevor er eine
  unmittelbare Reevaluation anfordert.
* **Einheitliche Wirkung:** Manual Override ist ein einzelner Bewegungs-Pausenzustand ohne richtungs- oder funktionsbezogene Blockierflags. Safety bleibt dominant. Die normale Automation wird weiter ausgewertet und aktualisiert den kanonischen Background-State, löst aber bis zum Override-Ende keine Komfortfahrt aus. Danach entscheidet der aktuelle Resolverzustand unmittelbar neu.

---
Verwandte Notizen:
* [`priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md`](../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md)
* [`../architecture/adr-004-background-effective-targets.md`](../architecture/adr-004-background-effective-targets.md)
