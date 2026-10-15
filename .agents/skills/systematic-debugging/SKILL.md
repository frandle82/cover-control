---
name: systematic-debugging
description: Strukturierte, hypothesenbasierte Fehlerdiagnose ohne spekulatives Ausprobieren zur Vermeidung von Token- und Zeitschleifen.
---

# Systematic Debugging Skill

Verhindert "Trial-and-Error"-Schleifen und spekulative Änderungen durch rigorose Ursachenanalyse.

## 1. Das 4-Schritte-Verfahren

```
[1. Reproduzieren] -> [2. Hypothese] -> [3. Minimaler Fix] -> [4. Regressionstest]
```

1. **Reproduzieren:**
   * Fehler zuerst mit einem fokussierten Testbefehl gezielt isolieren.
   * Exakten Assertion-Fehler oder Stacktrace erfassen.
2. **Hypothese bilden:**
   * Vor jedem Code-Edit: Warum schlägt der Test fehl? Welche Codezeile ist ursächlich?
   * Nicht auf Verdacht Dateien editieren.
3. **Minimaler Fix:**
   * Nur die exakt notwendige Zeile/Bedingung anpassen.
   * Keine unaufgeforderten Refactorings oder Umbenennungen im selben Schritt.
4. **Verifizieren:**
   * Fokussierten Test erneut ausführen.
   * Prüfen, ob keine Nebeneffekte aufgetreten sind.

## 2. Anti-Patterns vermeiden

* ❌ *Trial-and-Error:* Variablen ändern, Test starten, hoffen, dass es klappt.
* ❌ *Shotgun Debugging:* Gleichzeitig in fünf Dateien Änderungen vornehmen.
* ❌ *Symptom-Fixing:* Assertions im Test abschwächen, statt die Ursache im Runtime-Code zu beheben.
