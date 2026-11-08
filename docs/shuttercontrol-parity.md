# ioBroker.shuttercontrol parity

Stand: 2026-11-08
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
| Arbeits-/Nichtarbeitstag | Getrennte Zeitfenster; Samstag optional Werktag | Workday-Sensor plus getrennte Profilzeiten in `const.py`, `config_profile_schema.py`, `schedule.py`; Flow-, Resolver-, Runtime- und Schedule-Tests | FULL | – |
| Urlaub/Feiertag/Schulferien | Zusätzliche Quellen klassifizieren Tage als Wochenende | Verbindlich über vorhandenen Workday-/Non-Workday-Sensor abzubilden | NOT_APPLICABLE | Keine separate Kalenderarchitektur bauen |
| Living/Sleep/Children | Drei feste Gruppen mit eigenen Zeiten | Frei benennbare zentrale Profile und Room-Profilzuweisung | MAPPED | Keine festen Gruppen hardcoden |
| Früheste/späteste Öffnung | Astro/Helligkeit wird durch Min/Max-Zeitfenster begrenzt | Early/Late Workday/Non-Workday, `_time_bounds()`, stabile Point-Timer und Tests | FULL | – |
| Schließfenster | Frühe/späte Schließgrenzen | Getrennte Down-Early/Down-Late-Profilwerte, Runtime- und Schedule-Diagnose | FULL | – |
| Sunrise/Sunset | Tägliche SunCalc-Zeitpunkte plus Offset | `sun.sun`-Elevation in Zeitfenstern; Ereignisse werden aus HA-Standortdaten berechnet | MAPPED | Keine direkte Sunrise-/Sunset-Auswahl oder Minutenoffsets |
| Golden Hour | Golden-Hour-Beginn/-Ende als Zeitquelle | Über konfigurierbare Elevationsschwellen fachlich abbildbar | MAPPED | Kein benannter Golden-Hour-Modus; Schwellen müssen bewusst gewählt werden |
| Elevation öffnen/schließen | Per-Rollladen Elevationsschließen; globales Ende für Beschattung | Fixe/dynamische/hybride Profil-Schwellen, Dauer, Timer, Diagnose und Tests | FULL | Referenzfeld liegt pro Rollladen, Ziel bewusst im Profil |
| Astro-Offsets | Minutenoffset auf Sunrise/Sunset/Golden Hour | Elevationswerte/-sensoren statt Zeitoffset | MAPPED | Keine direkte Minutenoffset-UI |
| Helligkeit öffnen/schließen | Separate Schwellen und früheste Zeiten | Profil-Schwellen, Hysterese, Dauer, Listener, Runtime, Status und Tests | FULL | – |
| Versetztes Fahren | Bereichs-/Astro-Verzögerung zwischen Rollläden | Fester plus zufälliger Fahrdelay pro Raum; Aktor prüft Gates nach Delay erneut | FULL | – |
| Spätes Schließen | Ausgewählte Rollläden später vollständig schließen | Down-Late-Zeit und normale Profil-/Room-Auswahl | MAPPED | Referenz besitzt separaten `LateDown`-Schalter je Rollladen |
| Zwischenposition, später komplett schließen | Normale Abfahrt fährt bei aktiviertem `betweenPosition` zuerst `betweenPositionLevel`; `betweenPositionTime` löst für Covers im Zustand `middle` die vollständige Fahrt auf `heightDown` aus. `LateAllDown`/`LateDown` ist davon unabhängig | Time-Profil aktiviert die Zwischenfahrt und besitzt `final_close_time`; die Room-Position `intermediate_close_position` bleibt physisch raumeigen. Der vorhandene Scheduler verwendet getrennte Reasons/Trigger, die Schlussfahrt läuft durch Safety-, Frost- und Fenstersequenz, und „Nächste Schließung“ zeigt das tatsächlich frühere Ereignis | FULL | Covers unterhalb der Zwischenposition werden bewusst nicht wieder geöffnet; sicherere Cover-Control-Invariante gegenüber der Referenz |
| No-Go-Time / letzte Bewegung | `noGoTime` wird ausschließlich in den zeitgesteuerten `shutterUpLiving/Sleep/Children`-Callbacks geprüft. Maßgeblich ist pro Cover `state.lc`, also jede manuelle oder automatische echte Zustandsänderung; `0` deaktiviert, es gibt keinen Retry-Timer | Behavior-Profil `no_go_time_minutes`; die Runtime verwendet pro Cover Home Assistants `State.last_changed`, blockiert nur `scheduled_open`, setzt keinen Manual Override und meldet `blocked_by=no_go_time`. Safety und Force laufen vorher und bleiben unbeeinflusst | FULL | Sunrise/Golden Hour/Helligkeit werden entsprechend dem Referenzcode nicht gesperrt |
| Getrenntes Auto-Up/Auto-Down | Richtung je Rollladen schaltbar | Room-Schalter/Entities für Auto-Up und Auto-Down, Feature-State-Tests | FULL | – |
| Manuelle Gruppenbuttons | Open/Close/SunProtect/Auto für alle oder Bereiche | Force-Entities und Room-Koordination bilden Aktionen ab | MAPPED | Keine festen Bereichsbuttons gewünscht |
| Positionsinversion | `heightDown > heightUp` kehrt Vergleiche um | HA standardisiert Positionen; `cover_type=awning` passt Richtungslogik an | MAPPED | Keine freie Inversion zweier beliebiger Endwerte |
| Manuelle Bewegungserkennung | Unerwartete Endposition setzt `Manu_Mode`; eigene Fahrten ausgenommen | Service-Kontext, Ziel/Fahrfenster, Zwischenzustände, persistenter Override und Regressionstests | FULL | – |
| Manuelle bekannte Zielposition | Öffnen/Schließen/Beschatten kann Automatikzustand erhalten | Optionale Schedule-Adoption erkennt finale Open-/Close-Ziele; Beschattungsziel bleibt Override | PARTIAL | Exakte Referenzsemantik für manuell erreichte Beschattungsposition fehlt |
| Restart-Zustand | Aktions-/Zielzustände persistiert; tägliche Initialisierung | HA `Store`, Status-Hydration, Recovery-Modi, Unload-Save und Recovery-Tests | MAPPED | Referenz-Reset um 02:30 wird bewusst nicht kopiert |
| Azimutbereich | Fensterrichtung ± Bereich | Start-/Endazimut im Room/Profil-Resolver, Listener, Shading-Runtime und Diagnose | FULL | Referenz-2.1.1-Rohwert-Inkonsistenz nicht übernehmen |
| Elevationsbereich Beschattung | Mindest-/Maximalhöhe und globales Endfenster | Min/Max-Elevation, sofortiges Ende nach Sonnenposition, Tests | FULL | – |
| Beschattungshelligkeit | Startwert, prozentuale Endhysterese | Start/Ende plus absolute Hysterese und frei kombinierbare Bedingungen | MAPPED | Hysterese-Einheit unterscheidet sich bewusst |
| Innen-/Außentemperatur | Varianten mit Innen, Außen oder beiden Sensoren | Zwei Temperaturbedingungen, globale/Room-Sources, Hysterese und Condition-Matrix | FULL | – |
| Heat Protection | Strikt oberhalb der Außentemperaturschwelle innerhalb gültiger Sun Protection auf vollständige Schließposition statt Beschattungsposition | Zwei Shading-Profilwerte, vorhandene Outdoor-Quelle, normale Condition-Matrix, `close_position`, persistierter No-Churn-Hold, konkrete Diagnose, Safety-/Propagation-/Runtime-Tests | FULL | Bestehende absolute Shading-Hysteresen ersetzen bewusst die prozentuale Referenzhysterese der normalen Endbedingungen |
| Beschattungs-Startverzögerung | Indirekt durch Sensor-/Fahrverarbeitung | Eigener Start-Wait mit Managed Timer, Cancel/Restart und Tests | FULL | – |
| Beschattungs-Endverzögerung | Per Rollladen, bei erneutem Licht abgebrochen | End-Wait mit kontinuierlicher Bedingung, Cancel/Restart und Tests | FULL | – |
| Beschattungs-Rückkehr | Öffnen, Zustand halten oder Fensterziel beachten | Status-Hintergrund, Shading-End-Optionen, Ventilation und Logbook | FULL | – |
| `KeepSunProtect` | Kein Öffnen beim Beschattungsende | `prevent_opening_after_shading_end` | MAPPED | – |
| Fenster geschlossen/gekippt/offen | Drei Zustände und getrennte Zielhöhen | Full-/Tilt-Sensoren, Lüftungs-/Lockoutpositionen und Kontakt-Listener | FULL | – |
| Triggerverzögerung Fenster | Getrennte Verzögerung für Öffnen und Schließen | Trigger- plus Statusdelay, Managed Point-Timer | MAPPED | Nicht richtungsgetrennt |
| Aussperrschutz/Fahrerlaubnis | Off, onlyUp, onlyDown, upDown bei offenem Kontakt | Lockoutposition, Tilt-Locks und Ventilation-Gates | MAPPED | Kein einzelner vierstufiger Modus; Zielarchitektur bleibt granular |
| Wiederherstellung nach Fensterschließen | Gesicherte Höhe/Aktion wird wieder angefahren | Persistierter Ventilationshintergrund und Restore-Ziel | FULL | – |
| Automatik schließt bei offenem Fenster auf Lüftung | Erst vollständig schließen, Fahrzeit warten, Kontakt erneut prüfen, dann Lüftungsposition | Per-Cover-Sequenz für `scheduled_close`, `sun_close` und `brightness_close`; aktueller Kontakt bestimmt das zweite Ziel, Safety/Force/Manual/Unload brechen ab und das Schließziel bleibt als Restore-Ziel erhalten | FULL | – |
| Schließen bei offenem Fenster | Je nach `autoDrive` blockieren oder schließen | Full-Open-Lockout verhindert Force-Close; Tilt-Locks sind konfigurierbar | MAPPED | Referenzrichtungen nicht 1:1 als Select vorhanden |
| Fire Safety | Zielposition, höchste Priorität, Latch, keine automatische Rückkehr, bewusste Reinitialisierung | Eigene `safety`-Profilfunktion, globale Quelle, Room-Teilnahme, persistenter Runtime-Latch, Reset-Button, Listener/Trigger, Movement und Restart-/Entity-Tests | FULL | – |
| Rain Safety | Zielposition und nächsthöherer verbleibender Alarm | Profilziel, Room-Teilnahme, feste Priorität, unmittelbare Reevaluation und Reality-Test | FULL | Referenz ist bei Aktivierung eventreihenfolgeabhängig; Cover Control folgt bewusst der deterministischen Zielrangfolge |
| Wind 2 Safety | Zweite Windstufe mit Zielposition und Priorität | Profilziel, globale Quelle, Room-Teilnahme, Listener, Runtime und Regressionstest | FULL | – |
| Wind 1 Safety | Erste Windstufe mit Zielposition und Priorität | Profilziel, globale Quelle, Room-Teilnahme, Listener, Runtime und Regressionstest | FULL | – |
| Frost Safety | Nur geschlossenes Cover anheben; spätere Schließfahrt begrenzen | Frostziel im Profil, per-Cover Prüfung ohne Gruppenfahrt, Clamp späterer Schließziele und Referenztest | FULL | Kein paralleler Restore-Zustand; normale Runtime evaluiert nach Ende neu |
| Alarmdiagnose | `autoState`, gespeicherte Alarmaktion/-höhe | Konkrete Control-State-Gründe sowie `active_safety`, `fire_latched` und `safety_target` im Entry-/Cover-Snapshot | FULL | – |
| Sommerzeitraum | Je Rollladen im Zeitraum nicht schließen | Nicht vorhanden | MISSING | Nur einfache Profilregel plus Room-Auswahl, keine neue Kategorie |
| Weihnachtszeitraum/-position | Im Zeitraum alternatives Schließziel | Nicht vorhanden | MISSING | Einfache Profilperiode plus Room-Position |
| Saison über Jahreswechsel | Zeitraum wie 01.12–06.01 | Nicht vorhanden | MISSING | Periodenresolver muss Jahreswechsel testen |
| Eindeutige Trigger-IDs | Nutzer fordert fachlich eindeutige IDs | Rollenbezogene State-Trigger, getrennte Open-/Close-/Shading-/Kalender-Timer, kollisionsfreie Fenster-Timer, priorisierte Pending-Sets und unveränderte Event-Struktur; Regressionstests in `test_event_driven_processing.py` | FULL | – |
| Status/Diagnose normaler Automation | Aktionsstatus und Zielhöhe je Rollladen | Persistenter Status, Reason, Active/Configured/Blocked Controls, Sensoren, Logbook und Tests | FULL | – |

## Aktive Referenzfelder versus historische Felder

Aktiv und deshalb relevant sind unter anderem `inSummerNotDown`, `useXmasLevel`/`XmasLevel`, `betweenPosition`, `LateDown`, `noGoTime`, `heatProtection`, `useOpenWindowLevel`, sämtliche fünf Alarmaktivierungen und alle Fenster-/Beschattungsfelder.

Zur Runtime unbenutzt sind die globalen Felder `UseAstro`, `UseSunMode`, `driveHeightDown*`, `driveHeightUp*`, `driveHeightSun`, globales `heatProtection`, die alten Enum-Felder, `sunMonthStart`, `sunMonthEnd`, `sunProtecEnum`, `sun_shutterUp`, `sun_shutterDown` und globales `useXmasLevel`. Sie werden nicht portiert.

## Priorisierte Implementierungsreihenfolge

1. Sommer- und Weihnachtsperiode minimal in vorhandene Profile/Rooms integrieren.

Schedule-Prognosen sind an der zentralen Berechnungsgrenze auf volle Sekunden normalisiert. Wiederholtes Refreshing mit unveränderten Eingängen liefert dadurch identische `next_open`-/`next_close`-Werte; „Nächste Schließung“ wählt bei gestuftem Schließen das frühere reguläre oder endgültige Ereignis.

Nicht geplant sind feste Living/Sleep/Children-Profile, separate Urlaubs-/Ferien-/Feiertagsarchitektur oder eine technische Portierung des JavaScript-Modulaufbaus.
