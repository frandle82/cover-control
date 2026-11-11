---
title: Final Close und funktionsabhängige Schalter
type: domain
status: active
tags:
  - schedule
  - solar-elevation
  - entities
  - translations
---

# Final Close und funktionsabhängige Schalter

## Bestätigte Invarianten

- Automationsschalter existieren nur, wenn die zugehörige Funktion durch Gruppen-, Raum- oder Override-Schlüssel konfiguriert ist. Ein zur Laufzeit ausgeschalteter Schalter entfernt die Konfiguration nicht.
- Bei Sonne und Helligkeit bestimmen die gewählten Öffnungs-/Schließmodi die konfigurierte Funktion. Abgeleitete `auto_sun = false`- oder `auto_brightness = false`-Werte allein konfigurieren keine zusätzliche Funktion.
- Das vollständige Schließen unterstützt unabhängige Auslöser für Uhrzeit und fallende Sonnenhöhe. Der früheste gültige Auslöser gewinnt.
- Die Sonnenrichtung wird astronomisch aus der aktuellen Sonnenhöhe und ihrer unmittelbar folgenden Entwicklung bestimmt. Lokale Uhrzeiten sind kein Richtungsersatz.
- Beim Start wertet Cover Control den aktuellen Sonnenzustand aus. Liegt die Sonne abends bereits unter der Schwelle und fällt weiter, erfolgt das vollständige Schließen ohne vorheriges State-Change-Ereignis.
- Ein vollständiges Schließen wird pro Kalendertag nur einmal ausgelöst. Sommer-, Weihnachts-, Fenster- und Sicherheitsregeln bleiben im normalen Auswertungspfad erhalten.
- Nach einem vollständigen Schließen zeigen Zeitplan und `Next Close` erst wieder einen Kandidaten des Folgetags; ein zweiter Auslöser desselben Tags bleibt unsichtbar und wirkungslos.
- Die Werte für Uhrzeit und Sonnenhöhe erscheinen im Config Flow nur bei aktiviertem Auslöser. Sonnenhöhe verwendet einen Grad-Zahlen-Selector, keine Zeiteingabe.
- `final_close_elevation` ist über Persistenz, Modell, Resolver und Runtime immer ein `float` in Grad zwischen `-90.0` und `90.0`; der Wert gehört ausschließlich zur Sonnenhöhenkonfiguration, niemals zur Zeitkonfiguration.
- Historische Zeit- oder Textwerte wie `"00:00:00"` werden beim Upgrade auf `DEFAULT_FINAL_CLOSE_ELEVATION` repariert; numerische Strings einschließlich Dezimalkomma werden als `float` normalisiert.
- Menüpunkte benennen eine Funktion; ihre Beschreibungen erklären den konfigurierbaren Inhalt und dürfen den Titel nicht nur wiederholen.
- Home Assistant erwartet kurze Bezeichnungen unter `menu_options` und erklärende Texte unter `menu_option_descriptions`; vertauschte Inhalte machen das Menü unlesbar.
- Sichtbare deutsche Texte verwenden einheitlich „Arbeitstag“, „Bewohnerstatus“ und „manuelle Übersteuerung“. Technische Config-Keys dürfen nicht als UI-Bezeichnungen erscheinen.

---
Verwandte Notizen:
* [`shading-and-solar-geometry.md`](shading-and-solar-geometry.md)
* [`../troubleshooting/entity-registry-cleanup.md`](../troubleshooting/entity-registry-cleanup.md)
