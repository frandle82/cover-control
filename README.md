# Cover Control für Home Assistant

[![Release](https://img.shields.io/github/v/release/frandle82/cover-control?sort=semver&color=E8920C)](https://github.com/frandle82/cover-control/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2A3540.svg)](LICENSE)

![Cover Control – Rollladensteuerung für Home Assistant](custom_components/cover_control/brand/icon.png)

Cover Control automatisiert Rollläden, Jalousien und Markisen in Home Assistant. Eine zentrale Instanz verwaltet gemeinsam genutzte Datenquellen und drei feste Gruppen. Jeder Raum bleibt ein eigenständiger Konfigurationseintrag mit seinen Covern, Fensterkontakten, Sensoren und physischen Zielpositionen.

## Funktionen

### Räume und feste Gruppen

- Genau drei wiederverwendbare Gruppen: **Wohnbereich**, **Schlafbereich** und **Kinderbereich**.
- Gruppen enthalten Zeit-, Helligkeits-, Sonnen-, Sonnenschutz-, Lüftungs-, Bewohner- und Verhaltensregeln.
- Räume enthalten Hardware, Fensterkontakte, Geometrie, lokale Sensoren und Zielpositionen.
- Ein Raum gehört genau einer Gruppe.
- Laufzeitschalter werden nur für tatsächlich konfigurierte Funktionen angelegt. Ein ausgeschalteter Schalter entfernt die Konfiguration nicht.

### Öffnen und Schließen

- Separate Zeitfenster für Arbeits- und Nichtarbeitstage.
- Optionaler Home-Assistant-Arbeitstag-Sensor für heute und morgen.
- Öffnen nach Uhrzeit, Sonnenaufgang, Golden Hour, Sonnenhöhe oder Helligkeit.
- Schließen nach Uhrzeit, Sonnenuntergang, Golden Hour, Sonnenhöhe oder Helligkeit.
- Früheste und späteste Zeit begrenzen auch sonnen- und helligkeitsabhängige Fahrten.
- Kalenderereignisse können anhand konfigurierter Titel Öffnen oder Schließen auslösen.

Die späteste Öffnungszeit hebt Schutz- und Sperrbedingungen nicht auf. Blockieren Bewohnerstatus, manuelle Übersteuerung, Fensterzustand oder eine Sicherheitsregel die Öffnung, bleibt das Cover geschlossen. Sobald sich der blockierende Zustand ändert, wertet Cover Control die Situation neu aus und öffnet nur, wenn alle Bedingungen erfüllt sind.

### Zwischenposition und vollständiges Schließen

Beim normalen Schließereignis kann das Cover zunächst eine raumeigene Zwischenposition anfahren. Das anschließende vollständige Schließen lässt sich unabhängig auslösen durch:

- eine feste Uhrzeit,
- eine fallende Sonnenhöhe.

Sind beide Auslöser aktiviert, gewinnt der zuerst erfüllte Auslöser. Morgens löst dieselbe Sonnenhöhe keine Fahrt aus. Bei einem Neustart am Abend wertet Cover Control die aktuelle Sonnenhöhe und ihre tatsächliche Fallrichtung sofort aus.

Beispiel:

```text
18:00 normales Schließereignis
→ 50 % Zwischenposition

Vollständig schließen:
→ um 22:00 Uhr oder bei Sonnenhöhe ≤ -6°

18:42 Sonnenhöhe erreicht -6° auf dem fallenden Ast
→ vollständig schließen

22:00
→ keine zweite Fahrt
```

Sommerunterdrückung, Weihnachtsposition, Fensterfolgen und die allgemeinen Prioritäten gelten auch für das vollständige Schließen.

### Sonnenschutz

- Feste Sonnenschutzmodi auf Basis von Sonnenazimut und Sonnenhöhe.
- Optionale Helligkeits- sowie Innen- und Außentemperaturschwellen.
- Hitzeschutz und Kälteschutz mit festen, nachvollziehbaren Regeln.
- Konfigurierbare Hysterese und Wartezeit für das Ende des Sonnenschutzes.
- Sofortiges Ende, sobald die Sonne den konfigurierten Geometriebereich verlässt.
- Normale und alternative raumeigene Sonnenschutzposition.

### Fenster, Lüftung und Aussperrschutz

- Pro Cover getrennte Kontakte für gekippte und vollständig geöffnete Fenster.
- Gekippte Fenster verwenden die Lüftungsposition.
- Vollständig geöffnete Fenster verwenden die Aussperrschutzposition.
- Nach dem Schließen eines Fensters wird die im Hintergrund erforderliche Position neu ausgewertet.
- Fenster- und Lüftungsentscheidungen haben Vorrang vor Komfortautomation und Sonnenschutz.

### Bewohnerstatus und manuelle Übersteuerung

- Optionaler Bewohner-, Schlaf- oder Ruhemodus über eine Home-Assistant-Entität.
- Aktivierung kann schließen; Deaktivierung kann eine erneute Öffnungsprüfung auslösen.
- Öffnen, Lüften und Sonnenschutz können während des aktiven Bewohnerstatus getrennt erlaubt werden.
- Erkannte manuelle Fahrten pausieren die normale Automatik einheitlich.
- Bei einer Dauer von `0` bleibt die manuelle Übersteuerung bis zum Betätigen des Lösch-Buttons aktiv.
- Sicherheitsaktionen bleiben auch während einer manuellen Übersteuerung wirksam.

### Positionen und Lamellen

- Raumeigene Positionen für geöffnet, geschlossen, Zwischenposition, Sonnenschutz, Lüftung und Aussperrschutz.
- Vier Lamellenziele für Öffnen, Schließen, Lüften und Sonnenschutz, sofern das Cover Tilt unterstützt.
- Positionstoleranz verhindert überflüssige Fahrbefehle.
- Cover ohne Positionssteuerung werden an den Endlagen mit `open_cover` und `close_cover` angesteuert.

### Sicherheit und Prioritäten

Die feste Prioritätsreihenfolge lautet:

1. Feuer-, Regen-, Wind- und Frostschutz
2. Manuelle Übersteuerung
3. Fenster, Lüftung und Aussperrschutz
4. Sonnenschutz und Hitzeschutz
5. Bewohnerstatus
6. Zeit-, Sonnen- und Helligkeitssteuerung

Nicht verfügbare Cover oder entscheidungsrelevante Sensoren führen zu einem sicheren Abbruch statt zu einer unkontrollierten Fahrt.

## Erzeugte Entitäten

| Entität | Funktion |
| --- | --- |
| **Nächste Öffnung** | Nächster berechneter Öffnungszeitpunkt |
| **Nächste Schließung** | Nächster normaler oder vollständiger Schließzeitpunkt |
| **Aktive Steuerung** | Aktueller Entscheidungsgrund und Laufzeitstatus |
| **Zeitsteuerung** | Zeitabhängige Automation ein- oder ausschalten |
| **Helligkeitsautomatik** | Helligkeitsabhängige Automation ein- oder ausschalten |
| **Sonnenautomatik** | Sonnenabhängige Automation ein- oder ausschalten |
| **Sonnenschutz** | Sonnenschutz ein- oder ausschalten |
| **Lüftung** | Lüftungsautomation ein- oder ausschalten |

## Installation

### HACS (empfohlen)

1. In HACS **Integrationen** öffnen.
2. **Benutzerdefinierte Repositories** auswählen.
3. `https://github.com/frandle82/cover-control` als Repository der Kategorie **Integration** hinzufügen.
4. **Cover Control** installieren und Home Assistant neu starten.

### Manuell

1. `cover_control.zip` aus dem aktuellen [GitHub-Release](https://github.com/frandle82/cover-control/releases) herunterladen.
2. Den Inhalt nach `config/custom_components/cover_control/` entpacken.
3. Home Assistant neu starten.

## Konfiguration

1. In Home Assistant **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen.
2. Nach **Cover Control** suchen und die zentrale Instanz anlegen.
3. Globale Datenquellen und die drei festen Gruppen konfigurieren.
4. Räume als eigene Einträge hinzufügen, Cover und Sensoren zuordnen und eine Gruppe auswählen.
5. Nur die benötigten Gruppenfunktionen konfigurieren.

## Voraussetzungen

- Home Assistant 2025.2.0 oder neuer.
- Mindestens eine Cover-Entität pro Raum.
- Für frei wählbare Zwischenpositionen wird ein Cover mit Positionssteuerung empfohlen.
- Arbeitstag-, Kalender-, Helligkeits-, Temperatur-, Bewohner- und Fenstersensoren sind optional.

## Entwicklung und Tests

```bash
.venv/bin/pytest -q --asyncio-mode=auto
.venv/bin/python -m compileall -q custom_components tests scripts
git diff --check
```

## Lizenz

[MIT](LICENSE)
