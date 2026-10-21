---
name: profile-model
description: Zentrales Konfigurationsmodell für Profile und Räume. Beschreibt Vererbung, Resolver, Dreistufen-Zustände und Live-Propagation.
---

# Profile-Model Skill – Profile, Räume & Resolver

## Zweck

Dieser Skill dokumentiert das Trennungs- und Vererbungsmodell zwischen zentralen Profilen und dezentralen Räumen in `cover-control`.

---

## 1. Trennung von Zuständigkeiten

| Ebene | Speicherort | Inhalt / Verantwortung |
|---|---|---|
| **GLOBAL** | `controller.data[CONF_GLOBAL]` | Geteilte Datenquellen (Wetter, Außentemperatur, Helligkeit, Arbeitstage, globale Bedingungen). |
| **PROFILE** | `controller.data[CONF_PROFILES]` | Wiederverwendbare Automationsregeln (Zeitpläne, Helligkeitsschwellen, Hysterese, Beschattungs- und Lüftungsparameter). **Enthält niemals Hardware oder Raumpositionen.** |
| **ROOM** | `room_entry.data` | Physische Hardware (Covers, Kontakte, Sensoren, Ausrichtung, Zielpositionen) + Referenz auf Profil-ID (`CONF_ROOM_PROFILE_ID`) und aktivierte Funktionen (`CONF_PROFILE_FUNCTIONS`). |

---

## 2. Der Resolver (`config_resolver.py`)

Da ein Raum nur eine Referenz auf ein Profil speichert, berechnet der Resolver zur Laufzeit die effektive Konfiguration:

```
[System-Defaults]
       ↓ (überlagert durch)
[Global Sources (`CONF_GLOBAL`)]
       ↓ (überlagert durch)
[Profile Settings (`CONF_PROFILES[profile_id]`)]
       ↓ (überlagert durch)
[Room Source Overrides (falls konfiguriert)]
       ↓
= [Effective Profile Configuration]
```

* **Kernfunktionen:**
  * `effective_profile(controller_config, profile_id)`: Liefert das vollständige Profil-Werteobjekt.
  * `configured_functions_from_profile(profile_config)`: Ermittelt alle im Profil definierten Fähigkeiten (`time`, `sun`, `shading`, etc.).
  * `effective_room_profile_functions(room_config, profile_config)`: Schnittmenge aus im Profil vorhandenen und im Raum explizit ausgewählten Funktionen.

---

## 3. Das Dreistufen-Zustandsmodell

Jede Profilfunktion durchläuft drei Auswertungsebenen:

1. **`configured` (Konfiguriert):**
   * Die Funktion ist im zugewiesenen Profil definiert **UND** im Raumschritt `Profile & Automation` in `profile_functions` angehakt.
2. **`enabled` (Aktiviert):**
   * Der zugehörige Schalter (`switch.<raum>_<funktion>`) steht zur Laufzeit auf `on`.
   * **Wichtig:** Das Ausschalten eines Schalters ändert niemals die Konfiguration oder gelöschte Daten!
3. **`eligible` (Berechtigt):**
   * Die physikalischen und logischen Bedingungen sind aktuell erfüllt (z. B. Helligkeit > Schwelle, Sonnenazimut im Fensterwinkel, Fenster gekippt).

Erst wenn `configured AND enabled AND eligible` zutreffen, erzeugt die Funktion einen aktiven Fahrbefehl.

---

## 4. Live-Propagation

* **Kein Raum-Neustart bei Profiländerung:** Wenn ein Benutzer ein Profil im Reconfigure-Flow anpasst (z. B. Beschattungsschwelle von 40.000 Lux auf 35.000 Lux), wird der Controller-Eintrag aktualisiert.
* Der `CoverControlHub` invalidiert den Resolver-Cache und sendet `SIGNAL_HUB_STATE_UPDATED`.
* Alle Räume, die diese Profil-ID referenzieren, übernehmen die neuen Schwellenwerte sofort im nächsten Evaluierungszyklus.

---

## 5. Testen des Profilmodells

```sh
# Profilauflösung und Resolver testen:
.venv/bin/pytest -q tests/test_config_profiles.py --asyncio-mode=auto
.venv/bin/pytest -q tests/test_config_subentries.py --asyncio-mode=auto
```
