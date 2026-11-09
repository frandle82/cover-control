---
title: Prioritätenhierarchie und Aussperrschutz (Lockout)
type: domain
status: active
tags:
  - domain
  - priorities
  - lockout
  - safety
---

# Prioritätenhierarchie und Aussperrschutz

## Zweck
Festlegung der unumstößlichen Rangfolge konkurrierender Fahrbefehle in `custom_components/cover_control/runtime/evaluation.py` und `actuator.py`.

---

## 1. Die Prioritätenhierarchie

Im Falle gleichzeitiger Anforderungen gewinnt immer die Funktion mit der höheren Priorität:

```
[1. Safety (Fire > Rain > Wind 2 > Wind 1 > Frost)]
       ↓
[2. Lockout (Aussperrschutz)]
       ↓
[3. Force (Erzwingung)]
       ↓
[4. Manual Override (Benutzereingriff)]
       ↓
[5. Ventilation (Lüftung bei gekipptem/geöffnetem Fenster)]
       ↓
[6. Shading (Sonnenschutz / Beschattung)]
       ↓
[7. Resident / Time / Sun / Brightness]
```

---

## 2. Detaillierte Ebenen

### 1. Safety (Höchste Priorität)
* **Zweck:** Feuer-, Regen-, Wind- und Frostschutz mit deterministischer Alarmrangfolge.
* **Verhalten:** Übersteuert Lockout, Force, manuelle und normale Automationszustände. Fire bleibt nach Sensorende persistent verriegelt, bis ein bewusster Reset bei inaktivem Sensor erfolgt.

### 2. Lockout
* **Zweck:** Verhindert das Aussperren von Personen (z. B. auf Balkon/Terrasse) bei geöffneter Tür.
* **Verhalten:** Wenn der Türkontakt offen ist und Aussperrschutz konfiguriert ist, darf der Behang unter keinen Umständen unter die Lockout-Position fahren. Alle Schließbefehle werden blockiert oder auf die Lockout-Position limitiert.

### 3. Force Actions
* **Zweck:** Bewusst erzwungene Benutzer- oder externe Aktionen außerhalb des Safety-Alarmmodells.
* **Verhalten:** Übersteuert normale Automationszustände, aber keinen aktiven Safety-Zustand.

### 4. Manual Override
* **Zweck:** Respektiert den Willen des Bewohners, der manuell per Taster oder HA-UI gefahren hat.
* **Verhalten:** Blockiert automatische Fahrten für die konfigurierte Override-Dauer oder bis zum nächsten Zeitplan-Ereignis.

### 5. Ventilation
* **Zweck:** Ermöglicht Luftzirkulation bei gekipptem Fenster.
* **Verhalten:** Ein vollständig offener Kontakt verwendet fest die Lockout-Position, ein gekippter Kontakt die Lüftungsposition. Beim Wechsel `open → tilted` wird die Lüftungsposition angefahren. Nach dem Schließen wertet die Runtime den gespeicherten Hintergrund erneut aus.

### 6. Shading
* **Zweck:** Überhitzungsschutz bei direkter Sonneneinstrahlung.
* **Verhalten:** Fährt auf die Beschattungsposition, sofern Sonnengeometrie, Innen-/Außentemperatur und Helligkeit die Schwellen überschreiten.

### 7. Resident / Time / Sun / Brightness (Grundautomation)
* **Zweck:** Reguläres Öffnen am Morgen und Schließen am Abend basierend auf Zeit, Helligkeit oder Sonnenuntergang.

## Vereinfachtes Verhaltensmodell

Cover Control besitzt keine generischen Additional Conditions und keine CCA-spezifischen `prevent_*`, Ventilation- oder Lockout/Tilt-Override-Schalter. Fenster-, Lüftungs- und Beschattungskonflikte werden ausschließlich durch die feste Priorität gelöst. Identische effektive Ziele werden im Aktorpfad anhand Positionstoleranz und laufendem Ziel dedupliziert. Resident und Recalibrate bleiben bewusst zusätzliche Cover-Control-Funktionen.

---
Verwandte Notizen:
* [`../architecture/adr-001-mixin-architecture.md`](../architecture/adr-001-mixin-architecture.md)
* [`manual-override-vs-automation.md`](../domain/manual-override-vs-automation.md)
* [`shading-and-solar-geometry.md`](../domain/shading-and-solar-geometry.md)
