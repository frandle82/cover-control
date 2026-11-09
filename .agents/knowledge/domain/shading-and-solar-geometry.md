---
title: Sonnengeometrie und Beschattungslogik
type: domain
status: active
tags:
  - domain
  - shading
  - sun
  - solar-geometry
---

# Sonnengeometrie und Beschattungslogik

## Zweck
Berechnung des Sonnenstands relativ zur Fensterausrichtung in `custom_components/cover_control/runtime/shading.py` und Steuerung der Hysterese.

---

## 1. Feste Modi

Unterstützt werden ausschließlich `off`, `inside_outside`, `direction`, `inside_outside_direction`, `outside_direction`, `outside` und `inside`. Die erforderlichen Bedingungen sind je Modus fest per AND verknüpft. Eine freie Start-/End-Regelengine und Forecast-Beschattung existieren nicht.

## 2. Geometrische Bedingungen

1. **Azimut-Bereich:**
   * Gespeichert werden Fensterausrichtung und ± Bereich. Die kürzeste Winkeldistanz entscheidet, einschließlich 0°-Übergang.
2. **Elevations-Bereich:**
   * Die Sonnen-Elevation muss über der Mindestelevation (über Nachbargebäuden/Horizont) und unter der Höchstelevation (über Fenstersturz) liegen:
     $$\text{elevation\_min} \le \text{sun\_elevation} \le \text{elevation\_max}$$

---

## 3. Umgebungsbedingungen

Zusätzlich zur Sonnenposition müssen Umwelt-Sensoren die Notwendigkeit von Beschattung bestätigen:
* **Helligkeit/Strahlung:** Lux-Wert über Schwellenwert.
* **Außentemperatur:** Über Mindestwert (verhindert Beschattung im tiefen Winter, wenn solare Gewinne erwünscht sind).
* **Raumtemperatur:** Innenraum über Komforttemperatur.
* **Helligkeit:** In temperaturbasierten Modi nur dann zusätzliche AND-Bedingung, wenn `shading_brightness_sensor` gesetzt ist.

---

## 4. Hysterese & Wartezeiten

* **Ausschaltverzögerung:** Eine ungültige erforderliche Bedingung muss für die konfigurierte Referenz-Endwartezeit bestehen bleiben.
* Temperatur und Helligkeit starten strikt oberhalb der Schwelle. Während aktiver Beschattung gilt als Endgrenze `threshold × (1 − hysteresis / 100)`.
* Sobald eine erforderliche Modusbedingung nicht mehr gilt, beginnt die Referenz-Endwartezeit. Separate Maximum- oder Immediate-End-Sonderoptionen existieren nicht.

---
Verwandte Notizen:
* [`priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../architecture/adr-001-mixin-architecture.md`](../architecture/adr-001-mixin-architecture.md)
