---
title: ADR-003: Dreistufiges Funktions-Zustandsmodell (configured / enabled / eligible)
type: adr
status: accepted
date: 2026-10-16
tags:
  - architecture
  - state-machine
  - runtime
  - entities
---

# ADR-003: Dreistufiges Funktions-Zustandsmodell

## Kontext
In einer flexiblen Automationslösung für Rollläden muss klar getrennt werden zwischen:
1. Was hat der Benutzer eingerichtet?
2. Was ist aktuell vom Benutzer scharfgeschaltet?
3. Welche Aktion ist unter den aktuellen Umweltbedingungen (Helligkeit, Sonnenstand, Fensterstatus) ausführbar?

Das Vermischen dieser Ebenen führt zu Fehlern, bei denen das Ausschalten eines Schalters fälschlicherweise die Konfiguration löscht oder inaktive Funktionen Fahrbefehle auslösen.

## Entscheidung
Wir etablieren ein striktes Dreistufen-Modell:

| Zustand | Bedeutung | Steuerungsebene |
|---|---|---|
| **`configured`** | Funktion existiert im zugewiesenen Profil **UND** wurde vom Raum explizit in `profile_functions` gewählt. | Konfiguration (Config Entry) |
| **`enabled`** | Der zugehörige Schalter (`switch.<raum>_<funktion>`) steht auf `on`. | Benutzer-Laufzeitsteuerung |
| **`eligible`** | Die physikalischen & logischen Bedingungen (z. B. Helligkeit über Schwelle, Sonnenwinkel im Fenster) sind erfüllt. | Runtime-Evaluierung (`evaluation.py`) |

## Konsequenzen
* **Ein Schalter ändert niemals die Konfiguration:** Schaltet der Nutzer einen Schalter aus, bleibt die Konfiguration vollständig intakt.
* **Separates Testen:** Jede der drei Stufen wird in Tests unabhängig validiert.
* **Diagnoseklarheit:** Diagnose-Sensoren können präzise melden, warum eine Funktion nicht aktiv ist (nicht konfiguriert vs. per Schalter deaktiviert vs. Bedingung nicht erfüllt).

---
Verwandte Notizen:
* [`../domain/priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../domain/manual-override-vs-automation.md`](../domain/manual-override-vs-automation.md)
