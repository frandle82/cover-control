---
title: Tilt- und Raffstore-Modell
type: domain
updated: 2026-11-09
status: confirmed
tags:
  - tilt
  - raffstore
  - actuator
---

# Tilt- und Raffstore-Modell

Tilt ist eine bewusste Home-Assistant-Erweiterung und keine Lücke zur Shuttercontrol-Referenz.

## Invarianten

* Die UI erkennt Tilt ausschließlich über `CoverEntityFeature.SET_TILT_POSITION`; ein manueller Capability-Schalter existiert nicht.
* Physische Tilt-Ziele gehören dem Room: Öffnen, Schließen, Lüften und Beschatten.
* Mehrstufige, sonnenhöhenabhängige Tilt-Konfiguration ist kein Kernmodell. Beschattung verwendet genau `shading_tilt_position`.
* Die Aktorsequenz ist fest: Cover-Position fahren, bis Idle oder zum internen Timeout warten, danach Tilt fahren.
* Tilt-Toleranz und Timeout sind interne Runtime-Werte. Befehle innerhalb der festen Tilt-Toleranz werden dedupliziert.
* Automatische Tilt-Servicecalls tragen den eigenen HA-Kontext und lösen dadurch keinen Manual Override aus. Echte externe Tilt-Servicecalls bleiben Teil der bestehenden manuellen Erkennung.
* Safety bleibt dominant. Nur Gründe mit einem bestehenden Tilt-Ziel erzeugen einen Tilt-Befehl; reine Safety-Ziele erfinden kein neues Tilt-Verhalten.

## Migration

Legacy-Warteoptionen, Tilt-Toleranz, vier Shading-Tilt-Stufen und drei Elevationsgrenzen werden entfernt. Benutzerdefinierte Mehrstufenwerte werden deterministisch über die bisherige mittlere Stufe 2 auf `shading_tilt_position` abgebildet und erzeugen einmalig einen Repair-Hinweis. Reine Defaultwerte werden still bereinigt.

Verwandt: [`priorities-and-lockout.md`](priorities-and-lockout.md), [`manual-override-vs-automation.md`](manual-override-vs-automation.md), [`../ioBroker-shuttercontrol.md`](../ioBroker-shuttercontrol.md).
