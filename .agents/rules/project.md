# Projekt- & Architekturregeln – Cover Control

Verbindliche Architektur- und Implementierungsrichtlinien für die Home Assistant Custom Integration `cover-control`.

## 1. Projektstruktur & Runtime-Architektur

* **Laufzeit-Code:** `custom_components/cover_control/`
* **Regressionstests:** `tests/`
* **Skripte & Werkzeuge:** `scripts/`

### Mixin-Zuständigkeiten (`custom_components/cover_control/runtime/`)
Logik gehört in das zuständige Mixin, nicht in die Controller-Fassade:
* `actuator.py`: Fahrbefehle, Positionstoleranz, Lamellenkippung (Tilt) und Verzögerungslogik.
* `evaluation.py`: Berechnung der Zielposition und Auswertung der Bedingungen.
* `events.py`: Home Assistant State-Listener und Event-Subscriptions.
* `schedule.py`: Zeitpläne, Arbeitstag-Sensoren und Kalender-Ereignisse.
* `shading.py`: Sonnengeometrie (Azimut/Elevation), Wetterbedingungen und Beschattungsregeln.
* `status.py`: Zustände der Steuerungsentitäten, Diagnosesensoren und Statusgründe.

Controller-Imports bleiben stabil über `controller.py`. Logik nicht ohne klaren architektonischen Grund zwischen Mixins verschieben.

## 2. Source of Truth

* **Konstanten & Defaults:** Gehören zentral nach `const.py`.
* **Persistente Konfiguration:** Gehört ausschließlich in den Home Assistant Config Entry.
* **Laufzeit-Status:** Bleibt im Arbeitsspeicher (in-memory), sofern keine Persistenz über Neustarts/Reloads hinweg erforderlich ist.
* **Shared Logic:** Gemeinsame Normalisierung und Validierung für Config Flow und Options Flow verwenden. Keine redundanten Konfigurationsschlüssel für denselben logischen Parameter.

## 3. Konfigurationsarchitektur (Native v6 / v7)

Strikte Grenzen der Verantwortlichkeit:
* **GLOBAL:** Besitzt geteilte HA-Datenquellen (Arbeitstage, Kalender, Helligkeit, Außentemperatur, Wetter/Vorhersage, globale Bedingungen).
* **PROFILE:** Besitzt Automationsverhalten und Schwellenwerte (Zeitpläne, Helligkeitsschwellen, Hysterese, Wartezeiten, Beschattungs- und Lüftungsregeln). Profile besitzen niemals raumeigene Entitäten oder Positionen.
* **ROOM:** Besitzt Hardware, Cover-Entitäten, physische Positionen (Offen, Geschlossen, Beschattung, Kippung, Lüftung, Lockout), Fenstersensoren, Geometrie, Raumschalter und die Profilzuweisung.
* **SWITCH:** Steuert, ob eine konfigurierte Raumfunktion zur Laufzeit aktiv (enabled) ist.
* **RUNTIME:** Entscheidet, ob eine aktive Funktion unter den aktuellen Bedingungen ausführungsberechtigt (eligible) ist.

### Zustandsmodell
* **`configured`**: Funktion ist im gewählten Profil vorhanden **UND** vom Raum explizit ausgewählt (`profile_functions`).
* **`enabled`**: Der zugehörige Laufzeitschalter steht auf **ON**.
* **`eligible`**: Die aktuellen Bedingungen erlauben der Funktion eine Aktion.

Ein Schalterzustand ändert niemals die Konfiguration. Das Ausschalten eines Schalters löscht keine Raum-/Profilkonfiguration.

### Native Profilfunktionen & Schalter
* Autonom schaltbare Profilfunktionen mit Laufzeitschalter: `time`, `brightness`, `sun`, `shading`, `ventilation`, `resident`.
* Automationsverhalten ohne eigenständigen Laufzeitschalter: `behavior`.

### UI-Struktur für Räume & Profile
* **Raum-UI:** General, Cover & Hardware, Positions, Window contacts, Room sensors, Geometry, Profile & Automation, Local data sources, Controls, Diagnostics.
* **Profil-UI:** General, Time, Brightness, Sun, Shading, Ventilation, Resident, Manual behavior.
* Im Raum-Schritt `Profile & Automation` zuerst das Profil wählen und danach die gewünschten Profilfunktionen explizit selektieren (niemals automatisch alle Funktionen aktivieren).
* Klare Trennung im UI: `Room name` (Konfigurationsobjekt) vs. `Home Assistant area` (zugeordnete physische HA-Area).

## 4. Fahrbefehle, Beschattung & Manuelle Steuerung

* **Fahrbefehle (`actuator.py`):** Sämtliche automatischen Fahrbefehle laufen über den Controller und `actuator.py`.
* **Prioritätenhierarchie:** Lockout > Force > Manual Override > Ventilation > Shading > Resident.
* **Toleranz:** Keine doppelten Fahrbefehle senden, wenn sich die Position bereits innerhalb der konfigurierten Toleranz befindet.
* **Manuelle Steuerung:** Strikt trennen zwischen:
  1. Manueller Bewegungserkennung (`manual movement detection`)
  2. Manuellem Override-Zustand (`manual override state`)
  3. Geplanter Aktionshistorie (`scheduled action history`)
  4. Erzwingungsaktionen (`force actions`)
* Durch Cover Control initiierte Fahrten (auch Zwischenzustände wie `opening`/`closing`) dürfen niemals als manuelle Bedienung gewertet werden.
* **Beschattungsregeln:** Sonnengeometrie in `shading.py`, Zielposition/Auswertung in `evaluation.py`. Hysterese und Wartezeiten zustandsbehaftet führen und zurücksetzen, sobald die Bedingung ungültig wird. Sofort-Ende- und Sicherheitslogik wahren.
