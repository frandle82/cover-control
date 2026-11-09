# ioBroker.shuttercontrol parity

Stand: 2026-11-09
Referenz: [`simatec/ioBroker.shuttercontrol@64ccaedc4f413f187e2a6f6d5164c83b5d6aa848`](https://github.com/simatec/ioBroker.shuttercontrol/tree/64ccaedc4f413f187e2a6f6d5164c83b5d6aa848) (`master`, Version 2.1.2)

## Statusdefinitionen

- `FULL`: UI → Persistenz → Resolver → Listener/Trigger → Runtime → Fahrentscheidung → Status/Diagnose → Regressionstest ist vollständig vorhanden.
- `MAPPED`: Referenzverhalten ist vollständig über ein anderes, bewusst passendes Cover-Control-Konzept abgebildet.
- `PARTIAL`: Ein Teil der Kette oder ein relevanter Edge Case fehlt.
- `MISSING`: Kein fachlich ausreichendes Verhalten vorhanden.
- `NOT_APPLICABLE`: Referenzspezifisches Konzept wird durch eine verbindliche Architekturentscheidung nicht übernommen.

`FULL` bewertet die komplette Kette, nicht nur vorhandene Konstanten oder ähnlich benannte Methoden.

## Paritätsmatrix

| Funktionsgruppe | Referenzverhalten | Cover-Control-Zuordnung und Evidenz | Status | Offene Lücke |
|---|---|---|---|---|
| Arbeits-/Nichtarbeitstag | Getrennte Zeitfenster; Samstag optional Werktag | Workday-Sensor plus getrennte Gruppenzeiten in `const.py`, `config_group_schema.py`, `schedule.py`; Flow-, Resolver-, Runtime- und Schedule-Tests | FULL | – |
| Urlaub/Feiertag/Schulferien | Zusätzliche Quellen klassifizieren Tage als Wochenende | Verbindlich über vorhandenen Workday-/Non-Workday-Sensor abzubilden | NOT_APPLICABLE | Keine separate Kalenderarchitektur bauen |
| Living/Sleep/Children | Drei feste Gruppen mit eigenen Zeiten | Exakt drei controller-eigene Gruppen `living`, `sleep`, `children`; jeder Standalone Room gehört genau einer Gruppe; Flow, Migration, Resolver, Runtime-Propagation, Diagnose und Reality-Test | FULL | – |
| Früheste/späteste Öffnung | Astro/Helligkeit wird durch Min/Max-Zeitfenster begrenzt | Early/Late Workday/Non-Workday, `_time_bounds()`, stabile Point-Timer und Tests | FULL | – |
| Schließfenster | Frühe/späte Schließgrenzen | Getrennte Down-Early/Down-Late-Gruppenwerte, Runtime- und Schedule-Diagnose | FULL | – |
| Sunrise/Sunset | Tägliche SunCalc-Zeitpunkte plus Offset | Explizite Modi berechnen echte Astral-Sunrise-/Sunset-Zeitpunkte aus HA-Standort und -Zeitzone, wenden Richtungsoffsets an und begrenzen durch Early/Late | FULL | – |
| Golden Hour | SunCalc berechnet täglich `goldenHourEnd` zum Öffnen und `goldenHour` zum Schließen; Early/Late begrenzen den Zeitpunkt, globale Minutenoffsets verschieben ihn | Astral Golden Hour ist ein eigener Modus: morgens Ende, abends Beginn; Offsets, Early/Late, Next Events, Saison/DST und Runtime-Kette sind getestet | FULL | – |
| Elevation öffnen/schließen | Per-Rollladen Elevationsschließen; globales Ende für Beschattung | Expliziter Modus mit festen Gruppen-Schwellen, HA-Sonnenhöhe, Early/Late, Runtime, Diagnose und Tests | FULL | Referenzfeld liegt pro Rollladen, Ziel bewusst in der Gruppe; Dynamic/Hybrid gehört nicht zur Zielparität |
| Astro-Offsets | Minutenoffset auf Sunrise/Sunset/Golden Hour | `astro_open_offset_minutes` wirkt auf Sunrise/morgendliche Golden Hour; `astro_close_offset_minutes` auf Sunset/abendliche Golden Hour | FULL | – |
| Helligkeit öffnen/schließen | Separate Schwellen und früheste Zeiten | Gruppen-Schwellen, Hysterese, Dauer, Listener, Runtime, Status und Tests | FULL | – |
| Versetztes Fahren | Bereichs-/Astro-Verzögerung zwischen Rollläden | Fester plus zufälliger Fahrdelay pro Raum; Aktor prüft Gates nach Delay erneut | FULL | – |
| Spätes Schließen | `LateAllDownTime` fährt nur Covers mit `LateDown`; unabhängig von Zwischenfahrt, Sommer und Christmas | Down-Late-/Final-Close-Zeit und normale Gruppen-/Room-Auswahl; Safety, Frost, Fenster und Recovery bleiben im gemeinsamen Pfad | MAPPED | Keine unabhängige `LateDown`-Teilnahme je Cover; Räume benötigen bei abweichender Teilnahme ein eigene Gruppe |
| Zwischenposition, später komplett schließen | Normale Abfahrt fährt bei aktiviertem `betweenPosition` zuerst `betweenPositionLevel`; `betweenPositionTime` löst für Covers im Zustand `middle` die vollständige Fahrt auf `heightDown` aus. `LateAllDown`/`LateDown` ist davon unabhängig | Gruppenzeit aktiviert die Zwischenfahrt und besitzt `final_close_time`; die Room-Position `intermediate_close_position` bleibt physisch raumeigen. Der vorhandene Scheduler verwendet getrennte Reasons/Trigger, die Schlussfahrt läuft durch Safety-, Frost- und Fenstersequenz, und „Nächste Schließung“ zeigt das tatsächlich frühere Ereignis | FULL | Covers unterhalb der Zwischenposition werden bewusst nicht wieder geöffnet; sicherere Cover-Control-Invariante gegenüber der Referenz |
| No-Go-Time / letzte Bewegung | `noGoTime` wird ausschließlich in den zeitgesteuerten `shutterUpLiving/Sleep/Children`-Callbacks geprüft. Maßgeblich ist pro Cover `state.lc`, also jede manuelle oder automatische echte Zustandsänderung; `0` deaktiviert, es gibt keinen Retry-Timer | Gruppenverhalten `no_go_time_minutes`; die Runtime verwendet pro Cover Home Assistants `State.last_changed`, blockiert nur `scheduled_open`, setzt keinen Manual Override und meldet `blocked_by=no_go_time`. Safety und Force laufen vorher und bleiben unbeeinflusst | FULL | Sunrise/Golden Hour/Helligkeit werden entsprechend dem Referenzcode nicht gesperrt |
| Getrenntes Auto-Up/Auto-Down | Richtung je Rollladen schaltbar | Room-Schalter/Entities für Auto-Up und Auto-Down, Feature-State-Tests | FULL | – |
| Manuelle Gruppenbuttons | Open/Close/SunProtect/Auto für alle oder Bereiche | Force-Entities und Room-Koordination bilden Aktionen ab | MAPPED | Keine festen Bereichsbuttons gewünscht |
| Positionsinversion | `heightDown > heightUp` kehrt Vergleiche um | HA standardisiert `0 = geschlossen`, `100 = offen`; `cover_type=awning` passt Bewegungsrichtung an, alle Safety-/Saison-/Lüftungsziele bleiben kanonische HA-Positionen | MAPPED | Keine freie Inversion zweier beliebiger Endwerte; nicht HA-konforme Aktoren benötigen eine Template-/Adapter-Normalisierung |
| Manuelle Bewegungserkennung | Unerwartete Endposition setzt `Manu_Mode`; eigene Fahrten ausgenommen | Service-Kontext, Ziel/Fahrfenster, Zwischenzustände, persistenter Override und Regressionstests | FULL | – |
| Manuelle bekannte Zielposition | Nach `shutterStateRound`-Rundung setzt eine exakt erreichte `heightDownSun` `currentAction` und `triggerAction` auf `sunProtect`; dadurch wird erneutes Beschatten unterdrückt und das reguläre Beschattungsende darf später öffnen, sofern `KeepSunProtect` nicht gilt. Andere Zwischenpositionen werden `Manu_Mode`; der Zustand endet durch die normalen Sun-Protection-End-/Resetpfade | Optionale Schedule-Adoption erkennt finale Open-/Close-Ziele. Eine abgeschlossene manuelle Fahrt auf die effektive normale Beschattungsposition wird innerhalb `position_tolerance` pro Cover als `shading` adoptiert, erzeugt keinen Override oder Doppelbefehl, erscheint als aktive Steuerung und läuft durch Safety, Fensterpriorität und den normalen Shading-End-Pfad; Heat Protection wird nicht adoptiert | FULL | – |
| Restart-Zustand | Aktions-/Zielzustände persistiert; tägliche Initialisierung | HA `Store`, Status-Hydration, Recovery-Modi, Unload-Save und Recovery-Tests | MAPPED | Referenz-Reset um 02:30 wird bewusst nicht kopiert |
| Sonnenschutzart | Sieben feste Varianten von Aus bis Innen-/Außen-/Direction-Kombination | Expliziter `shading_mode`, konditionale UI, Resolver, Listener, Runtime, Diagnose, Migration und Tests | FULL | Keine frei kombinierbaren AND-/OR-Regeln |
| Azimutbereich | Fensterrichtung ± Bereich | Gruppenwerte Direction ± Range, kürzeste Winkeldistanz mit 0°-Wrap, Migration und Tests | FULL | Referenz-2.1.1-Rohwert-Inkonsistenz nicht übernehmen |
| Elevationsbereich Beschattung | Mindesthöhe und Endhöhe | Min-/End-Elevation als feste Direction-Bedingung | FULL | – |
| Beschattungshelligkeit | Optionaler Sensor, Startwert, prozentuale Endhysterese | Optionaler `shading_brightness_sensor`, Schwellwert und prozentuale Hysterese | FULL | Sensor nicht gesetzt = Bedingung ignoriert |
| Innen-/Außentemperatur | Varianten mit Innen, Außen oder beiden Sensoren | Vorhandene Global-/Room-Sources, gruppenbezogene Schwellen und prozentuale Hysteresen | FULL | – |
| Heat Protection | Strikt oberhalb der Außentemperaturschwelle innerhalb gültiger Sun Protection auf vollständige Schließposition statt Beschattungsposition | Vorhandene Outdoor-Quelle, gültiger fester Modus, `close_position`, persistierter No-Churn-Hold, Diagnose und Tests | FULL | Kein eigener Sonnenschutzmodus |
| Beschattungs-Endverzögerung | Per Rollladen, bei erneutem Licht abgebrochen | End-Wait mit kontinuierlicher Bedingung, Cancel/Restart und Tests | FULL | – |
| Beschattungs-Rückkehr | Öffnen, Sonnenschutzposition halten oder Fensterziel beachten | Feste Window-Priorität, `keep_sun_protection`, Ventilation und Logbook | FULL | – |
| `KeepSunProtect` | Kein Öffnen beim Beschattungsende | Eindeutiges `keep_sun_protection`, Migration des früheren Felds und Runtime-Test | FULL | – |

### Entfernte frühere Zusatzfelder

Die freie Cover-Control-Regelengine und Forecast-Beschattung sind nicht mehr Teil des Modells. Entfernt wurden `shading_conditions_start_and`, `shading_conditions_start_or`, `shading_conditions_end_and`, `shading_conditions_end_or`, alle `shading_forecast_*`-Felder, `use_shading_forecast_sensor`, `shading_weather_conditions`, `shading_config`, `shading_independent_*`, `shading_start_max_duration`, `shading_end_max_duration`, `shading_end_immediate_by_sun_position`, `shading_waitingtime_start`, die generischen `shading_temperatur_sensor1/2`-Felder sowie die alten getrennten Brightness-Start-/Endwerte. Ebenfalls entfernt sind generische Additional Conditions, CCA-spezifische `prevent_*`-Schalter, Ventilation-Prioritätsoptionen und Lockout/Tilt-Sonderregeln. Legacy-Namen existieren nur noch im Migrationscode und in Migrationstests.
| Fenster geschlossen/gekippt/offen | Drei Zustände und getrennte Zielhöhen | Full-/Tilt-Sensoren, Lüftungs-/Lockoutpositionen und Kontakt-Listener | FULL | – |
| Triggerverzögerung Fenster | `trigDelyUp` verzögert die Öffnungsreaktion, `trigDelyDown` die Schließreaktion | `contact_trigger_delay`, `contact_status_delay` und `ventilation_delay_after_close` decken Entprellung, stabilen Status und zweistufige Rückfahrt ab | MAPPED | Nicht richtungsgetrennt und deshalb nicht parameteridentisch; der vorhandene Pfad deckt den Nutzerfall ohne Doppelkonfiguration ab |
| Aussperrschutz/Fahrerlaubnis | Off, onlyUp, onlyDown, upDown bei offenem Kontakt | Feste Fenstersemantik: offen → Lockout-Position, gekippt → Lüftungsposition; Window vor Shading | MAPPED | Kein konfigurierbarer vierstufiger Modus; feste sichere Priorität |
| Wiederherstellung nach Fensterschließen | Gesicherte Höhe/Aktion wird wieder angefahren | Persistierter Ventilationshintergrund und Restore-Ziel | FULL | – |
| Automatik schließt bei offenem Fenster auf Lüftung | Erst vollständig schließen, Fahrzeit warten, Kontakt erneut prüfen, dann Lüftungsposition | Per-Cover-Sequenz für `scheduled_close`, `sun_close` und `brightness_close`; aktueller Kontakt bestimmt das zweite Ziel, Safety/Force/Manual/Unload brechen ab und das Schließziel bleibt als Restore-Ziel erhalten | FULL | – |
| Schließen bei offenem Fenster | Je nach `autoDrive` blockieren oder schließen | Full-Open-Lockout verhindert Force-Close; automatische Schließfahrten verwenden die feste zweistufige Fenstersequenz | MAPPED | Referenzrichtungen nicht als Nutzeroption vorhanden; feste sichere Semantik |
| Fire Safety | Zielposition, höchste Priorität, Latch, keine automatische Rückkehr, bewusste Reinitialisierung | Gruppenbezogene `safety`-Konfiguration, globale Quelle, Room-Teilnahme, persistenter Runtime-Latch, Reset-Button, Listener/Trigger, Movement und Restart-/Entity-Tests | FULL | – |
| Rain Safety | Zielposition und nächsthöherer verbleibender Alarm | Gruppenziel, Room-Teilnahme, feste Priorität, unmittelbare Reevaluation und Reality-Test | FULL | Referenz ist bei Aktivierung eventreihenfolgeabhängig; Cover Control folgt bewusst der deterministischen Zielrangfolge |
| Wind 2 Safety | Zweite Windstufe mit Zielposition und Priorität | Gruppenziel, globale Quelle, Room-Teilnahme, Listener, Runtime und Regressionstest | FULL | – |
| Wind 1 Safety | Erste Windstufe mit Zielposition und Priorität | Gruppenziel, globale Quelle, Room-Teilnahme, Listener, Runtime und Regressionstest | FULL | – |
| Frost Safety | Nur geschlossenes Cover anheben; spätere Schließfahrt begrenzen | Frostziel in der Gruppe, per-Cover Prüfung ohne Gruppenfahrt, Clamp späterer Schließziele und Referenztest | FULL | Kein paralleler Restore-Zustand; normale Runtime evaluiert nach Ende neu |
| Alarmdiagnose | `autoState`, gespeicherte Alarmaktion/-höhe | Konkrete Control-State-Gründe sowie `active_safety`, `fire_latched` und `safety_target` im Entry-/Cover-Snapshot | FULL | – |
| Sommerzeitraum | `SummerStart`/`SummerEnd` gelten global und inklusiv; `inSummerNotDown` unterdrückt je Rollladen Zeit-, Sunset-, Golden-Hour-, Elevation-, Helligkeits- und vollständige Zwischenpositions-Schließfahrten, nicht aber `LateDown` oder Alarmaktionen | Wiederkehrender Zeitraum im Gruppenzeit, Room-Teilnahme `summer_skip_close_enabled`, gemeinsames Runtime-Gate für normale Close-Entscheidungen, `blocked_by=summer_period`, Safety/Force/Frost bleiben dominant; Flow-, Resolver-, Runtime-, Boundary- und Prioritätstests | FULL | Die Referenz kann selbst eine zuvor berechnete Frost-Komfortfahrt durch Sommer blockieren; Cover Control wahrt bewusst seine stärkere Safety-Priorität |
| Weihnachtszeitraum/-position | `XMasStart`/`XMasEnd` gelten global und inklusiv; `useXmasLevel` ersetzt je Rollladen das normale, Zwischen- und vollständige Schließziel durch `XmasLevel` | Wiederkehrender Zeitraum im Gruppenzeit; Room-Teilnahme und physische `christmas_position`; gemeinsame Zielauswahl vor dem bestehenden Aktor-, Fenster-, Frost- und Safety-Pfad; Intermediate-/Final-, Window-, Resolver- und Boundary-Tests | FULL | Referenz lässt `Xmas` nicht durch Frost überschreiben; Cover Control hält Frost bewusst dominant |
| Saison über Jahreswechsel | `IsSummerTime()` verschiebt Start- oder Endjahr bei `End < Start`, z. B. 01.12.–06.01.; Grenztage sind eingeschlossen | Gemeinsame `_is_date_in_recurring_range()`-Hilfe für Sommer und Weihnachten, lokale HA-Zeit, keine Jahreszahl in Persistenz und Tests für beide Jahreshälften sowie Grenzen | FULL | – |
| Eindeutige Trigger-IDs | Nutzer fordert fachlich eindeutige IDs | Rollenbezogene State-Trigger, getrennte Open-/Close-/Shading-/Kalender-Timer, kollisionsfreie Fenster-Timer, priorisierte Pending-Sets und unveränderte Event-Struktur; Regressionstests in `test_event_driven_processing.py` | FULL | – |
| Status/Diagnose normaler Automation | Aktionsstatus und Zielhöhe je Rollladen | Persistenter Status, Reason, Active/Configured/Blocked Controls, Sensoren, Logbook und Tests | FULL | – |

## Konfliktmatrix

Die Tabelle beschreibt den tatsächlich geprüften Gewinner. „Safety“ umfasst die feste Cover-Control-Rangfolge `Fire > Rain > Wind 2 > Wind 1 > Frost`; die Referenz ist bei der Aktivierung der Nicht-Feuer-Alarme teilweise eventreihenfolgeabhängig.

| Konflikt | Gewünschter/tatsächlicher Gewinner in Cover Control | Referenzverhalten | Bewertung |
|---|---|---|---|
| Safety vs Force/Window/Shading/Heat Protection | Safety | Alarmstatus sperrt normale und manuelle Komfortfahrten | funktional äquivalent, deterministischer |
| Safety vs Christmas/Summer | Safety | Alarmwege sind separat; normale Sommerfahrt wird blockiert, Christmas kann in normalen Close-Pfaden Frost überschreiben | bewusst sicherer |
| Force vs Manual Override | Force | explizite Gruppenaktion setzt neuen Aktionszustand | funktional äquivalent |
| Force vs Window | Full-Open-Lockout vor erzwungenem Schließen, sonst Force | `autoDrive`/Triggerzustand entscheidet richtungsabhängig | HA-native, granularere Abbildung |
| Window vs Shading/Heat Protection | Window/Lockout bzw. Lüftungssequenz | Kontaktfreigabe und Fensterziel begrenzen Sun Protection | funktional äquivalent |
| Shading vs Heat Protection | Heat Protection als Zielvariante der gültigen Beschattung | `heatProtection` ersetzt innerhalb gültiger Sun Protection das Ziel | funktional äquivalent |
| Summer vs Intermediate/Final Close | Summer blockiert beide normalen Schließstufen | `inSummerNotDown` blockiert normale Abfahrt und `shutterDownComplete`, nicht `LateDown` | FULL für die gestufte Schließung; LateDown bleibt MAPPED |
| Christmas vs Intermediate/Final Close | Christmas-Ziel ersetzt beide Ziele | `XmasLevel` ersetzt Zwischen- und Vollschließziel | funktional äquivalent |
| Frost vs Window | Frostziel; laufende Fenstersequenz wird abgebrochen beziehungsweise geklemmt | Frost verhindert die zweite Fahrt auf Fensterhöhe | bewusst sicherer gemeinsamer Safety-Pfad |
| Frost vs Christmas | Frost | In normalen Close-Pfaden bleibt `Xmas` vom Frost-Override ausgenommen | bewusst sicherer |

Die fünf geforderten Frost-/Christmas-Sequenzen führen deshalb in Cover Control alle zu Frost: bei `scheduled_close`, `final_close`, offenem Fenster, später startendem Christmas und später startendem Frost. In der Referenz gewinnt Christmas in den normalen geplanten Close-Pfaden; ein späteres Alarmereignis läuft über den separaten Alarmhandler. Das unsicherere Verhalten wird nicht nachgebaut.

## Reality- und Lifecycle-Nachweis

- Ein geladener Controller- und Room-ConfigEntry erzeugt Resolver, Manager, Controller und Next-Event-Sensor. Wiederholtes Refreshing bleibt identisch und ohne `unavailable`-Flattern; ein zentrales Gruppenupdate propagiert ohne Reload, anschließend läuft der Fahrbefehl über den realen HA-Servicepfad (`test_loaded_room_next_open_entity_matches_sun_schedule`).
- Safety-Prioritätswechsel, Fire-Latch, Fenstersequenz-Abbruch, Heat Protection und Frost-Clamp sind als reale Controller-Sequenzen abgedeckt (`test_safety_reality_sequence` und Konflikttests in `test_safety.py`).
- Sommer/Christmas, Jahreswechsel, Intermediate/Final Close, Restart-Neuberechnung sowie stabile Sun-/Brightness-/Final-Close-Prognosen sind in `test_seasonal_schedule.py`, `test_intermediate_close.py` und `test_event_driven_processing.py` abgedeckt.
- Gruppenänderungen für Time, Brightness, Sun, Shading, Ventilation, Resident, Behavior und Safety laufen zentral über `CoverControlHub.apply_model()` und `ControllerManager.apply_config_model()`; Resolver, Listener und Timer werden neu aufgebaut. Die drei Gruppen bleiben Daten im Controller-Entry, Rooms eigenständige ConfigEntries, unterstützte Subentry-Typen bleiben leer.
- Eindeutige Triggerrollen, Pending-Sets sowie Cancel/Recreate/Dedup von Condition-, Fenster-, Schedule- und Final-Close-Timern sind durch `test_event_driven_processing.py`, `test_group_runtime.py`, `test_window_down_sequence.py` und Unload-Tests abgedeckt. Es wurde kein neuer Polling-Loop eingeführt.

## Release-Entscheidung

Der Reality-Check bestätigt alle `FULL`-Ketten und die dokumentierten `MAPPED`-/`NOT_APPLICABLE`-Architekturentscheidungen. Nach der toleranzbasierten Adoption manuell erreichter Beschattungspositionen enthält die Matrix weder `PARTIAL` noch `MISSING`; der Stand ist **READY FOR RELEASE**. Ein Release wird dadurch nicht automatisch gestartet.

## Aktive Referenzfelder versus historische Felder

Aktiv und deshalb relevant sind unter anderem `inSummerNotDown`, `useXmasLevel`/`XmasLevel`, `betweenPosition`, `LateDown`, `noGoTime`, `heatProtection`, `useOpenWindowLevel`, sämtliche fünf Alarmaktivierungen und alle Fenster-/Beschattungsfelder.

Zur Runtime unbenutzt sind die globalen Felder `UseAstro`, `UseSunMode`, `driveHeightDown*`, `driveHeightUp*`, `driveHeightSun`, globales `heatProtection`, die alten Enum-Felder, `sunMonthStart`, `sunMonthEnd`, `sunProtecEnum`, `sun_shutterUp`, `sun_shutterDown` und globales `useXmasLevel`. Sie werden nicht portiert.

## Priorisierte Implementierungsreihenfolge

Die bestätigten saisonalen Referenzfunktionen und die manuelle Beschattungsadoption sind umgesetzt. Der finale Reality-Check bestätigt die verbleibenden `MAPPED`-Zeilen als bewusste Architekturzuordnungen.

Schedule-Prognosen sind an der zentralen Berechnungsgrenze auf volle Sekunden normalisiert. Wiederholtes Refreshing mit unveränderten Eingängen liefert dadurch identische `next_open`-/`next_close`-Werte; „Nächste Schließung“ wählt bei gestuftem Schließen das frühere reguläre oder endgültige Ereignis.

Nicht geplant sind separate frei benennbare Profile, separate Urlaubs-/Ferien-/Feiertagsarchitektur oder eine technische Portierung des JavaScript-Modulaufbaus.
