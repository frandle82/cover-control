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

## 1. Geometrische Bedingungen

Damit die Beschattung aktiviert wird, muss die Sonne in das Fenster scheinen:

1. **Azimut-Bereich:**
   * Der Sonnen-Azimut muss innerhalb des konfigurierten Fensterausschnitts liegen:
     $$\text{azimuth\_min} \le \text{sun\_azimuth} \le \text{azimuth\_max}$$
2. **Elevations-Bereich:**
   * Die Sonnen-Elevation muss über der Mindestelevation (über Nachbargebäuden/Horizont) und unter der Höchstelevation (über Fenstersturz) liegen:
     $$\text{elevation\_min} \le \text{sun\_elevation} \le \text{elevation\_max}$$

---

## 2. Umgebungsbedingungen (Schwellenwerte)

Zusätzlich zur Sonnenposition müssen Umwelt-Sensoren die Notwendigkeit von Beschattung bestätigen:
* **Helligkeit/Strahlung:** Lux-Wert über Schwellenwert.
* **Außentemperatur:** Über Mindestwert (verhindert Beschattung im tiefen Winter, wenn solare Gewinne erwünscht sind).
* **Raumtemperatur:** Innenraum über Komforttemperatur.
* **Wetterkonditionen:** Kein dichter Regen oder Bewölkung (falls Wetter-Entität angebunden).

---

## 3. Hysterese & Wartezeiten

* **Einschaltverzögerung (`delay_in`):** Bedingung muss ununterbrochen für z. B. 5 Minuten erfüllt sein, um Klappern bei vorbeiziehenden Wolken zu vermeiden.
* **Ausschaltverzögerung (`delay_out`):** Bedingung muss ununterbrochen für z. B. 15 Minuten unterschritten sein, bevor der Behang wieder öffnet.
* **Sofort-Ende:** Fällt die Sonne aus dem geometrischen Azimut-/Elevationsfenster, endet die Beschattung ohne Verzögerung (Sicherheit/Plausibilität).

---
Verwandte Notizen:
* [`priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../architecture/adr-001-mixin-architecture.md`](../architecture/adr-001-mixin-architecture.md)
