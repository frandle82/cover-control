---
name: grill-me
description: Anforderungsanalyse vor Implementierungsbeginn. Interviewt den Entwickler intensiv, um unklare Anforderungen, Edge Cases und Architekturentscheidungen aufzudecken.
---

# Grill-Me Skill – Anforderungsanalyse & Scoping

## Zweck

Bevor überhaupt eine Zeile Code geschrieben wird, interviewt dieser Skill den Entwickler intensiv, um unklare Anforderungen, versteckte Annahmen und Edge Cases aufzudecken.

**Vorteil:** Verhindert, dass die KI voreilig Code generiert, der am eigentlichen Ziel vorbeigeht oder etablierte Architekturprinzipien verletzt.

---

## Wann anwenden?

* Bei neuen Features, Erweiterungen oder Verhaltensänderungen.
* Bei Änderungen an Zustandsautomaten, Prioritäten oder Timing-Logik.
* Bei Erweiterungen des Konfigurationsmodells (Global, Gruppe, Raum).
* Wenn eine Benutzeranforderung vage oder mehrdeutig formuliert ist.
* Vor großen Refactorings oder Änderungen an Schnittstellen.

---

## Das 5-Phasen-Interview

Vor Implementierungsbeginn strukturiert folgende Fragen durchgehen und klären:

### 1. Problemverständnis & Scope
* Welches konkrete Problem wird gelöst und wer profitiert davon?
* Was gehört **explizit zum Scope** und was **explizit NICHT**?
* Handelt es sich um eine Erweiterung bestehender Logik oder eine komplett neue Funktion?

### 2. Architektureinordnung (Cover Control Architektur)
* **Zuständigkeitsebene:**
  * Ist es eine geteilte Datenquelle? → `GLOBAL`
  * Ist es ein Automationsverhalten / Schwellenwert? → `GROUP`
  * Betrifft es Hardware, physische Positionen oder Raumsensoren? → `ROOM`
  * Gehört dazu ein manueller Ein-/Ausschalter? → `SWITCH` (`group`)
* **Mixin-Zuordnung (`custom_components/cover_control/runtime/`):**
  * `actuator.py`: Fahrbefehle, Positionstoleranz, Tilt, Verzögerung.
  * `evaluation.py`: Zielpositionsberechnung, Bedingungsauswertung.
  * `events.py`: State-Listener, Event-Subscriptions.
  * `schedule.py`: Zeitpläne, Kalender, Arbeitstage.
  * `shading.py`: Sonnengeometrie, Beschattungssensoren.
  * `status.py`: Zustände, Diagnosesensoren, Reasons.
* **Persistenz:**
  * Config Entry (persistent) vs. Runtime State (in-memory).

### 3. Zustandsmodell & Prioritäten
* Wie interagiert die Funktion mit dem Dreistufen-Modell?
  * `configured` (im Gruppe vorhanden UND vom Raum selektiert)
  * `enabled` (Laufzeitschalter ON)
  * `eligible` (Bedingungen zur Laufzeit erfüllt)
* Welche Priorität gilt bei Konflikten?
  * Standard: `Lockout` > `Force` > `Manual Override` > `Ventilation` > `Shading` > `Resident`.
* Was passiert bei manuellen Eingriffen des Benutzers?

### 4. Edge Cases & Resilienz
* Was passiert, wenn Sensoren `unavailable`, `unknown` oder noch nicht initialisiert sind?
* Was geschieht bei Home Assistant Neustart oder Integration Reload?
* Welche Hysterese-, Wartezeit- oder Entprellungslogik ist erforderlich?
* Gibt es Race Conditions zwischen Fahrbefehlen und Positionsmeldungen?

### 5. Verifikation & Testbarkeit
* Wie lässt sich die Änderung deterministisch und offline testen?
* Welche Testfälle sind für `configured`, `enabled` und `eligible` nötig?
* Sind Übersetzungen (`strings.json`, `en.json`, `de.json`) betroffen?

---

## Verhaltensregeln während des Interviews

1. **Präzise, zielgerichtete Fragen:** Maximal 3 bis 5 fokussierte Fragen pro Runde stellen; keine Textwände.
2. **Konkrete Optionen anbieten:** Statt offener Fragen ("Wie soll das sein?") Vorschläge mit Trade-offs präsentieren ("Option A vs. Option B").
3. **Kein Code vor Freigabe:** Keine Dateien editieren oder Code generieren, solange Kernanforderungen ungeklärt sind.
4. **Ergebnis festhalten:** Die getroffenen Entscheidungen kurz zusammenfassen, bevor in die Implementierungsphase gewechselt wird.
