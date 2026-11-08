---
name: playwright-interactive
description: End-to-End-Tests und Web-App-Testing via Browser. Ermöglicht interaktive Belastungstests, UI-Workflow-Verifikation und visuelle Fehleranalyse in Home Assistant Oberflächen.
---

# Playwright-Interactive Skill – E2E & Web-App-Testing

## Zweck

Ermöglicht automatisierte und interaktive Browser-Tests für Frontend-Komponenten, Config Flows, Options Flows und Lovelace-Integrationen in Home Assistant.

**Vorteil:** Verifiziert Benutzeroberflächen unter realistischen Bedingungen, deckt Rendering-Fehler, Validierungsabbrüche und Übersetzungsprobleme auf, die in reinen Backend-Unit-Tests verborgen bleiben.

---

## Wann anwenden?

* Bei Änderungen an Config-Flow-Schritten oder Options-Flow-Formularen.
* Zur visuellen Prüfung von UI-Übersetzungen (Deutsch/Englisch) in echten Dialogen.
* Zur Verifikation von dynamischen Selektoren (z. B. Filterung nach Entity-Domains oder Geräteklassen).
* Bei Dashboard- und Lovelace-UI-Integrationen.
* Zum Nachstellen komplexer UI-Bedienfolgen (Edge Cases bei Mehrfachklicks, Zurück-Buttons).

---

## Kern-Testbereiche in Cover Control

### 1. Config Flow & Reconfigure Flow
* Start des Flows über Home Assistant Integrationen.
* Durchklicken der Schritte:
  * Raum-UI: General → Cover & Hardware → Positions → Window contacts → Room sensors → Geometry → Group → Local data sources → Controls → Diagnostics.
  * Gruppen-UI: General → Time → Brightness → Sun → Shading → Ventilation → Resident → Manual behavior.
* Prüfung: Werden Validierungsfehler (z. B. ungültige Positionen, fehlende Pflichtfelder) verständlich und an der richtigen Stelle angezeigt?

### 2. Dynamische Selektoren & Dropdowns
* Werden nur gültige `cover`-Entitäten im Cover-Selektor angezeigt?
* Funktionieren Filter für Fensterkontakte (`binary_sensor` mit Geräteklasse `window` / `door`)?
* Werden Gruppenfunktions-Checkboxen korrekt aktiviert/deaktiviert?

### 3. Visuelle Lokalisierung & Layout
* Keine unübersetzten Keys (`component.cover_control.config.step...`).
* Kein Textüberlauf bei langen Beschreibungen im modalen Dialog.
* Saubere Darstellung sowohl im Light- als auch im Dark-Mode von Home Assistant.

---

## Browser-Test-Methodik

### Interaktive Browser-Inspektion
1. **URL aufrufen:** Lokale Home Assistant Entwicklungsinstanz oder Testserver ansteuern.
2. **DOM inspizieren:** Eindeutige Selektoren (`data-testid`, `name`, `id` oder Rollen) verwenden.
3. **Aktionen ausführen:** Klicks, Texteingaben, Dropdown-Auswahl simulieren.
4. **Zustand verifizieren:** Erfolgsmeldungen prüfen, Fehlermeldungen abfangen, DOM-Änderungen validieren.
5. **Visueller Snapshot:** Screenshot erfassen, um Layout und Darstellung zu überprüfen.

---

## Typische UI-Fehlerszenarien

| Fehlersymptom | Ursache | Lösung |
|---|---|---|
| Unübersetzter Text (`config.step...`) | Fehlender Schlüssel in `strings.json` oder Translation-Cache nicht neu geladen | Translation-Key prüfen, HA-Cache invalidieren |
| Dialog schließt unerwartet | Unhandled Exception im `async_step_*` Callback | Backend-Logs prüfen, Exceptions in Flows abfangen |
| Pflichtfeld blockiert ohne Anzeige | Schema-Definition verlangt Parameter, der im UI ausgeblendet ist | `vol.Required` vs. `vol.Optional` im Step-Schema abgleichen |
| Doppelter Submit erzeugt Duplikate | Fehlende Entprellung oder Idempotenz im Flow | `_async_abort_entries_match` oder eindeutigen Identifier prüfen |

---

## Qualitätskriterien für UI-Verifikation

* Jeder interaktive Testlauf muss reproduzierbare Schritte dokumentieren.
* Bei visuellen Fehlern immer die Bildschirmauflösung und das Theme dokumentieren.
* UI-Tests ergänzen die Backend-Regressionstests (`tests/test_config_flow.py`), ersetzen sie jedoch nicht.
