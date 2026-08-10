# Cover Control für Home Assistant

[![Release](https://img.shields.io/github/v/release/frandle82/cover-control?sort=semver&color=E8920C)](https://github.com/frandle82/cover-control/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2A3540.svg)](LICENSE)

![Cover Control – Rollladensteuerung für Home Assistant](custom_components/cover_control/brand/icon.png)

Cover Control ist eine benutzerfreundlich konfigurierbare Home-Assistant-Integration zur automatischen Steuerung von Rollläden, Jalousien und Markisen. Sie koordiniert mehrere Cover eines Raums und verbindet Zeitpläne, Helligkeit, Sonnenstand, Beschattung, Fensterkontakte und Bewohnerstatus mit frei wählbaren Zielpositionen und Sicherheitsregeln.

## Funktionen

### Zentrale Steuerung mehrerer Cover

- Eine Konfigurationsinstanz steuert ein oder mehrere Cover gemeinsam.
- Öffnen, Schließen und Beschatten werden innerhalb einer Instanz koordiniert ausgeführt.
- Lüftung kann je nach Fensterstatus für einzelne Cover abweichend gesteuert werden.
- Unterstützt Rollläden und Jalousien sowie ein angepasstes Verhalten für Markisen.
- Verwendet wahlweise `current_position`, `position` oder einen eigenen Positionssensor als Positionsquelle.
- Cover ohne freie Positionssteuerung werden an den Endlagen über `open_cover` und `close_cover` angesteuert.

### Positionen und Lamellen

- Separate Zielpositionen für vollständig geöffnet, geschlossen, Lüftung, Aussperrschutz und Beschattung.
- Alternative Beschattungsposition, die über eine zusätzliche Entität aktiviert werden kann.
- Eigene Lamellenpositionen für Öffnen, Schließen, Lüften und Beschatten.
- Vierstufige, vom Sonnenstand abhängige Lamellenposition für die Beschattung.
- Einstellbare Positionstoleranz und Fahrzeit zur Erkennung eigener beziehungsweise manueller Bewegungen.
- Wahlweise feste Wartezeit, Warten auf Stillstand oder Lamellenausrichtung vor der Cover-Bewegung.

### Zeitsteuerung

- Getrennte Öffnungs- und Schließzeitfenster für Arbeits- und Nichtarbeitstage.
- Frühe und späte Zeitgrenzen ermöglichen eine Berechnung innerhalb eines zulässigen Zeitfensters.
- Optionaler Arbeitstag-Sensor für heute und morgen.
- Kalenderereignisse können über frei definierbare Titel das Öffnen oder Schließen auslösen.
- Zeitsteuerung lässt sich während des Betriebs über eine eigene Schalter-Entität aktivieren oder deaktivieren.

### Helligkeits- und Sonnensteuerung

- Öffnen oberhalb und Schließen unterhalb frei wählbarer Helligkeitswerte.
- Hysterese und Mindestdauer verhindern häufige Aktionen bei schwankenden Sensorwerten.
- Sonnenhöhen-Grenzen für Öffnen und Schließen mit separater Mindestdauer.
- Feste Sonnenhöhen oder dynamische Grenzwerte aus eigenen Sensoren.
- Separate Offsets für die dynamischen Öffnungs- und Schließwerte.
- Helligkeit und Sonnenstand lassen sich per UND- oder ODER-Verknüpfung kombinieren.
- Beide Funktionen besitzen eigene Laufzeitschalter.

### Beschattung

- Beschattung anhand von Sonnenazimut und Sonnenhöhe.
- Optional zusätzliche Bedingungen aus Helligkeit, zwei Temperatursensoren, Wettervorhersage, Vorhersagetemperatur und frei konfigurierbaren Home-Assistant-Bedingungen.
- UND- und ODER-Gruppen für Start- und Endbedingungen.
- Separate Start- und Endschwellen sowie Hysteresen für Helligkeit und Temperatur.
- Wettervorhersage wahlweise aus Wetterattributen oder eigenen Sensoren.
- Einstellbare Wartezeiten und maximale Wartezeiten für Start und Ende.
- Sofortiges Beschattungsende, wenn die Sonne den konfigurierten Bereich verlässt.
- Regeln für das Zusammenspiel mit geöffneten Fenstern, Lüftung und anschließendem Öffnen.
- Optional temperaturunabhängige Beschattung sowie Vergleich von Vorhersage- und Messwerten.
- Eigener Laufzeitschalter für die komplette Beschattungsfunktion.

### Fensterkontakte, Lüftung und Aussperrschutz

- Pro Cover getrennte Kontakte für gekippte und vollständig geöffnete Fenster.
- Ein gekipptes Fenster kann das Cover auf eine Lüftungsposition fahren.
- Ein vollständig geöffnetes Fenster kann eine Aussperrschutzposition erzwingen.
- Konfigurierbare Trigger-, Status- und Nachlaufverzögerungen vermeiden Reaktionen auf kurze Zustandswechsel.
- Optionale sofortige Lüftung sowie Beibehaltung der geöffneten Position beim Wechsel von vollständig geöffnet zu gekippt.
- Wahlweise höhere Cover-Positionen während der Lüftung zulassen.
- Die Position vor Beginn der Lüftung wird gespeichert und kann anschließend wiederhergestellt werden.
- Einstellbare Sperren verhindern Schließen sowie Beginn oder Ende der Beschattung bei bestimmten Kontaktzuständen.
- Beschattung kann bei Bedarf Vorrang vor der Lüftung erhalten.
- Eigener Laufzeitschalter für Kontakt- und Lüftungssteuerung.

### Bewohnerstatus

- Optionaler Bewohner-, Schlaf- oder Ruhemodus über `binary_sensor`, `input_boolean` oder `switch`.
- Aktivierung kann ein sofortiges Schließen auslösen.
- Deaktivierung kann das normale Öffnen erneut prüfen.
- Öffnen, Lüften und Beschatten können während des aktiven Bewohnerstatus getrennt erlaubt werden.
- Optionaler Diagnosesensor zeigt den aktuellen Bewohnerstatus und die verwendete Entität.

### Zusätzliche Bedingungen

Home-Assistant-Bedingungen können für folgende Ebenen hinterlegt werden:

- gesamte Automatisierung,
- Öffnen und Schließen,
- Beginn und Ende der Lüftung,
- Beginn und Ende der Beschattung,
- Lamellensteuerung während der Beschattung.

Eine Aktion wird nur ausgeführt, wenn ihre jeweilige Bedingung erfüllt ist und alle übrigen Schutzregeln sie zulassen.

### Manueller Override

- Manuelle Cover-Bewegungen werden erkannt und pausieren die betroffenen Automatikfunktionen.
- Während eines erkannten manuellen Eingriffs werden automatische Fahrbefehle blockiert.
- Der Override endet wahlweise nach einer Dauer, zu einer festen Uhrzeit oder nur durch manuelles Löschen.
- Die konfigurierte Fahrzeit verhindert, dass Rückmeldungen einer eigenen Fahrt als manueller Eingriff gewertet werden.
- Der Button **Manuellen Override löschen** entfernt den Override für alle Cover der Instanz und wertet die Steuerung sofort neu aus. Dadurch wird die aktuell erforderliche Zielposition wieder angefahren.

### Verhaltens- und Sicherheitsregeln

- Verhindern einer höheren Zielposition beim Schließen.
- Ein beschattetes Cover muss beim Schließen nicht weiter abgesenkt werden.
- Beschattungsende kann bei bereits geschlossenem Cover unterdrückt werden.
- Öffnen nach Beschattungs- oder Lüftungsende kann verhindert werden.
- Mehrfaches Öffnen, Schließen oder Beschatten am selben Tag kann blockiert werden.
- Standardmäßige Cover-Serviceaufrufe lassen sich zu Diagnosezwecken unterdrücken.
- Nicht verfügbare Cover oder entscheidungsrelevante Sensoren führen zu einem sicheren Abbruch statt zu einer unkontrollierten Fahrt.

### Rekalibrierung

Der optionale Button **Cover neu kalibrieren** öffnet alle Cover der Instanz vollständig, wartet auf die Zielposition und stellt anschließend die vorherige Position wieder her. Die vollständig geöffnete Position kann separat konfiguriert werden.

## Erzeugte Entitäten

Nur aktivierte Funktionen erzeugen ihre optionalen Entitäten.

| Entität | Funktion |
| --- | --- |
| **Nächste Öffnung** | Frühester berechneter Öffnungszeitpunkt und zugehöriges Cover |
| **Nächste Schließung** | Frühester berechneter Schließzeitpunkt und zugehöriges Cover |
| **Aktive Steuerung** | Aktueller Grund sowie Position, Ziel, Override-, Beschattungs- und Lüftungsstatus aller Cover |
| **Bewohnerstatus** | Zustand und Quellentität des optionalen Bewohnermodus |
| **Zeitsteuerung** | Laufzeitumschaltung für zeitgesteuertes Öffnen und Schließen |
| **Helligkeitsautomatik** | Laufzeitumschaltung für die Helligkeitssteuerung |
| **Sonnenautomatik** | Laufzeitumschaltung für die Sonnenhöhensteuerung |
| **Kontaktsensoren** | Laufzeitumschaltung für Lüftung und Aussperrschutz |
| **Beschattung** | Laufzeitumschaltung für die Beschattungsautomatik |
| **Cover neu kalibrieren** | Startet die Rekalibrierung aller Cover der Instanz |
| **Manuellen Override löschen** | Löscht den Override und startet sofort eine neue Steuerungsauswertung |

Die Laufzeitschalter ändern die gespeicherte Konfiguration nicht. Nach einem Neustart gelten wieder die Einstellungen aus dem Konfigurationsdialog.

## Ereignisse

Die Integration sendet `cover_control_event` auf dem Home-Assistant-Event-Bus. Ereignisse enthalten unter anderem:

- `kind`: beispielsweise `evaluate` oder `command`,
- `entry_id` und `cover`,
- Auslöser und Aktionsgrund,
- Zielposition beziehungsweise Lamellenposition,
- verwendeten Cover-Service,
- Zeitstempel und gegebenenfalls den Grund einer übersprungenen Aktion.

Das Ereignis kann für Diagnose, Protokollierung und eigene Automationen verwendet werden.

## Voraussetzungen

- Home Assistant 2024.10.0 oder neuer.
- Mindestens eine Cover-Entität.
- Für Positionsziele wird ein Cover mit Positionsunterstützung empfohlen.
- Sensoren, Kontakte, Kalender, Arbeitstag- und Bedingungsentitäten sind optional.

## Installation

### HACS (empfohlen)

1. In HACS **Integrationen** öffnen.
2. Über das Menü **Benutzerdefinierte Repositories** auswählen.
3. `https://github.com/frandle82/cover-control` als Repository der Kategorie **Integration** hinzufügen.
4. **Cover Control** installieren und Home Assistant neu starten.

Veröffentlichte Versionen werden als `cover_control.zip` bereitgestellt und von HACS automatisch verarbeitet.

### Manuell

1. `cover_control.zip` aus dem neuesten [GitHub-Release](https://github.com/frandle82/cover-control/releases) herunterladen.
2. Den Ordner `config/custom_components/cover_control` anlegen.
3. Den Inhalt des ZIP-Archivs direkt in diesen Ordner entpacken. `manifest.json` muss danach unmittelbar in `cover_control` liegen.
4. Home Assistant neu starten.

## Konfiguration

1. In Home Assistant **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen.
2. Nach **Cover Control** suchen.
3. Namen, Raum und die gemeinsam zu steuernden Cover auswählen.
4. Die benötigten Automatikfunktionen aktivieren.
5. Über **Konfigurieren** die eingeblendeten Funktionsbereiche einrichten.

Der Optionsdialog zeigt nur Bereiche für aktivierte Funktionen. Änderungen werden durch ein sauberes Neuladen des Konfigurationseintrags übernommen.

## Fehlersuche

- Im Sensor **Aktive Steuerung** Zielposition, Grund, Override und abhängige Cover prüfen.
- Kontrollieren, ob alle verwendeten Cover, Kontakte und Entscheidungssensoren verfügbar sind.
- Zusätzliche Bedingungen müssen für die jeweilige Aktion erfüllt sein.
- Prüfen, ob ein manueller Override, Bewohnerstatus oder eine Kontaktregel die Aktion blockiert.
- Die Laufzeitschalter müssen eingeschaltet sein; ihre Zustände können von den gespeicherten Optionen abweichen.
- Für eine detaillierte Analyse `custom_components.cover_control` auf Debug-Protokollierung setzen oder `cover_control_event` unter **Entwicklerwerkzeuge → Ereignisse** beobachten.

## Entwicklung und Tests

Die Tests verwenden Home Assistant 2026.8 und `pytest-homeassistant-custom-component`.

```sh
python -m venv .venv
source .venv/bin/activate
pip install pytest-homeassistant-custom-component==0.13.355
python -m pytest -q --asyncio-mode=auto
python -m compileall -q custom_components tests scripts
git diff --check
```

## Releases

Release Please erstellt aus Conventional-Commit-Titeln automatisch einen Release-PR, aktualisiert `CHANGELOG.md`, `version.txt` und `manifest.json` und veröffentlicht nach dem Merge das GitHub-Release. Anschließend baut der Release-Workflow `cover_control.zip`, prüft Version und Archivstruktur und hängt das Paket an das Release an.

- `fix:` erzeugt eine Patch-Version.
- `feat:` erzeugt eine Minor-Version.
- Breaking Changes erzeugen eine Major-Version.
- Release-Versionen und Tags werden nicht manuell angelegt.

Weitere verbindliche Entwicklungs- und Release-Regeln stehen in [AGENTS.md](AGENTS.md).
