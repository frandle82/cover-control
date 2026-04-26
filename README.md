# Cover Control

<p align="center">
  <img src="img/icon.png" width="180" alt="Cover Control Logo">
</p>

<p align="center">
  Intelligente Steuerung von Rollläden, Jalousien und Cover-Entitäten für <a href="https://www.home-assistant.io/">Home Assistant</a>
</p>

---

# Funktionen

## Automatische Cover-Steuerung

Die Integration ermöglicht eine flexible und intelligente Steuerung von:

- Rollläden
- Jalousien
- Raffstores
- Markisen
- allgemeinen Cover-Entitäten

---

## Unterstützte Automationen

### Sonnenstand-Steuerung

Automatisches Öffnen oder Schließen anhand von:

- Sonnenaufgang
- Sonnenuntergang
- Sonnenhöhe
- Azimut

---

### Zeitbasierte Steuerung

Steuerung nach:

- festen Uhrzeiten
- Wochentagen
- individuellen Zeitfenstern
- Verzögerungen

---

### Wetterabhängige Steuerung

Reaktionen auf:

- hohe Temperaturen
- direkte Sonneneinstrahlung
- Bewölkung
- Wind
- Regen

---

### Anwesenheitssteuerung

Optionale Bedingungen:

- Personen zuhause
- Abwesenheit
- Schlafmodus
- Urlaubsmodus

---

### Helligkeitssteuerung

Automatische Steuerung anhand von:

- Lux-Sensoren
- Sonnenintensität
- Raumhelligkeit

---

### Sicherheitsfunktionen

Mögliche Schutzfunktionen:

- Windschutz
- Frostschutz
- Regenschutz
- Hitzeschutz

---

## Home Assistant Integration

Die Integration unterstützt:

- Geräte & Dienste
- UI-Konfiguration
- HACS
- automatische Entitätserkennung
- moderne Home-Assistant-Brandings

---

# Installation

## Installation über HACS

1. HACS öffnen
2. „Benutzerdefinierte Repositories“ auswählen
3. Dieses Repository hinzufügen:

```text
https://github.com/frandle82/cover-control
```

4. Kategorie: `Integration`
5. Installation starten
6. Home Assistant neu starten

---

## Manuelle Installation

Repository nach:

```text
config/custom_components/cover_control/
```

kopieren.

Danach Home Assistant neu starten.

---

# Voraussetzungen

- Home Assistant
- aktuelle Core-Version empfohlen
- HACS optional

---

# Screenshots

## Integration

<p align="center">
  <img src="img/icon.png" width="120">
</p>

---

# Lizenz

Dieses Projekt basiert teilweise auf dem Blueprint-Projekt von hvorragend:

- Repository: https://github.com/hvorragend/ha-blueprints
- Blueprint README: https://github.com/hvorragend/ha-blueprints/blob/main/blueprints/automation/README.md

Vielen Dank an hvorragend für die ursprüngliche Struktur und Inspiration.

---

## Lizenzhinweise

Sofern Teile der ursprünglichen Struktur oder Inhalte übernommen wurden, gelten die jeweiligen Lizenzbedingungen des Originalprojekts.

Bitte beachte zusätzlich die Lizenzdateien dieses Repositories.

---

# Credits

- Home Assistant Community
- hvorragend Blueprint-Projekt
- HACS Community

---

# Support

Fehler oder Wünsche bitte über GitHub Issues melden.

---

# Disclaimer

Die Nutzung erfolgt auf eigene Verantwortung. Vor allem bei automatisierten Cover-Steuerungen sollten Sicherheitsbedingungen sorgfältig geprüft werden.


### Quick start
1. Create a virtual environment:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
2. Install test dependencies:
   - `pip install -r requirements_test.txt`
3. Run tests:
   - `pytest`

### Tox
- Run all configured environments: `tox`
- Run only pytest env: `tox -e py310`
- Run lint env: `tox -e lint`

> Note: Full config/options-flow assertions require Home Assistant >= 2023.9. In older runtimes, these tests are skipped automatically.
