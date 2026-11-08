---
title: Reverse Engineering ioBroker.shuttercontrol 2.1.2
type: domain
status: active
updated: 2026-11-08
tags:
  - reverse-engineering
  - parity
  - shuttercontrol
  - safety
---

# Reverse Engineering ioBroker.shuttercontrol

## Referenz und Reproduzierbarkeit

- Repository: `https://github.com/simatec/ioBroker.shuttercontrol`
- Branch bei Prüfungsbeginn: `master`
- untersuchter Commit: [`64ccaedc4f413f187e2a6f6d5164c83b5d6aa848`](https://github.com/simatec/ioBroker.shuttercontrol/commit/64ccaedc4f413f187e2a6f6d5164c83b5d6aa848)
- Paketversion: `2.1.2`
- geprüft am: 2026-11-07

Der Commit wurde detached ausgecheckt. Aussagen unten beziehen sich ausschließlich auf diesen Stand. Quellcode hat bei Widersprüchen Vorrang vor README und Dokumentation.

## Analysierter Scope

Untersucht wurden `main.js`, `io-package.json`, `package.json`, `README.md`, `CHANGELOG_OLD.md`, `admin/index_m.js`, `admin/jsonTab.json5`, `docs/de/shuttercontrol.md`, die Tests sowie sämtliche Dateien mit Steuerungsverhalten unter `lib/`:

- Zeit/Astro: `shutterUpLiving.js`, `shutterUpSleep.js`, `shutterUpChildren.js`, `shutterDownLiving.js`, `shutterDownSleep.js`, `shutterDownChildren.js`, `shutterDownLate.js`, `shutterDownComplete.js`, `shutterSunriseSunset.js`, `shutterGoldenHour.js`, `elevationDown.js`, `shutterBrightnessSensor.js`.
- Umwelt und Sicherheit: `sunProtect.js`, `shutterAlarm.js`, `isSummerTime.js`.
- Fenster, manuelle Eingriffe und Aktorik: `triggerChange.js`, `windowLevel.js`, `buttonAction.js`, `shutterState.js`, `setShutter.js`.
- Tests: `main.test.js`, `lib/windowLevel.test.js`, `test/integration.js`, `test/unit.js`, `test/package.js`.

`lib/tools.js` enthält Übersetzungs-Hilfen und kein Steuerungsverhalten.

## Referenzarchitektur und Zustände

Die Referenz hält eine globale Adapterkonfiguration und eine `events`-Zeile je Rollladen. Feste Bereiche (`living`, `sleep`, `children`) wählen Zeit-/Astromodi; das ist keine Zielarchitektur für Cover Control. Dort werden diese Gruppen mit frei benennbaren Profilen und eigenständigen Room-ConfigEntries abgebildet.

Pro Rollladen werden unter anderem `currentAction`, `currentHeight`, `oldHeight`, `triggerAction`, `triggerHeight`, `firstCompleteUp`, `alarmTriggerAction`, `alarmTriggerLevel` und `lastAutoAction` geführt. `shutters.currentStates` persistiert diese Werte über Adapterstarts. Um 02:30 Uhr werden Aktionszustände täglich zurückgesetzt und die Istposition neu eingelesen.

Wichtige Aktionszustände sind `up`, `down`, `middle`, `Xmas`, `sunProtect`, `OpenInSunProtect`, `manu_sunProtect`, `Manu_Mode`, `triggered`, `wind1`, `wind2`, `rain`, `frost` und `fire`.

## Trigger und Timer

- State-Listener reagieren auf Bereichsschalter, Helligkeit, fünf Alarmquellen, Fensterkontakte, Innen-/Außentemperatur, Beschattungshelligkeit und Rollladenpositionen.
- Ein täglicher Job um 02:30 Uhr berechnet Zeitpunkte neu und initialisiert Aktionszustände.
- Sonnenposition wird alle fünf Minuten berechnet; Änderungen von Azimut/Elevation lösen Beschattung beziehungsweise Elevations-Schließen aus.
- Öffnen/Schließen, Sunrise/Sunset, Golden Hour, spätes und vollständiges Schließen verwenden benannte `node-schedule`-Jobs.
- Fahrten werden pro Rollladen verzögert. `noGoTime` wartet nach einem Schließen vor einem Öffnen.
- Fensteränderungen besitzen getrennte Auf-/Zu-Verzögerungen; das neue `windowLevel` wartet zusätzlich die konfigurierte Fahrzeit zwischen vollständigem Schließen und Lüftungsposition.
- Beschattungsende kann je Rollladen verzögert werden. Wird die Startbedingung wieder gültig, wird der Endtimer abgebrochen.

Die Referenz dedupliziert gleiche Sensor-Entity-IDs über mehrere Rollläden, verwendet aber denselben Datenpunkt für verschiedene fachliche Reaktionen. Für Cover Control gilt strenger: logisch unterschiedliche Auslöser erhalten eindeutige Trigger-IDs wie `sun_open_threshold`, `window_open` oder `wind_alarm`; generische IDs wie `state` oder `contact` reichen nicht.

Cover Control setzt diese Invariante in der gesamten Evaluation-Kette um: Shared-State-Events werden je konfigurierter Rolle aufgelöst, gleichzeitig eintreffende Ursachen bleiben als `set[str]` erhalten, und die bestehende Priorität wählt nur den repräsentativen `trigger`. Der Bewegungsgrund bleibt davon getrennt in `reason`. Richtungsabhängige Point-Timer verwenden `scheduled_open`/`scheduled_close`, `sun_open_duration_elapsed`/`sun_close_duration_elapsed`, `brightness_open_duration_elapsed`/`brightness_close_duration_elapsed` sowie vier getrennte Kalendergrenzen. Fenster liefern `window_open`, `window_tilted` oder `window_closed`; ihre internen Verzögerungsschlüssel enthalten zusätzlich die Sensor-Entity-ID und kollidieren daher bei mehreren Kontakten nicht. `cover_control_event` behält seine Struktur und veröffentlicht die präzisierten Triggerwerte.

## Zeit-, Astro- und Helligkeitsverhalten

- Arbeits-/Nichtarbeitstag unterscheiden früheste und späteste Öffnungszeit sowie Schließzeit. Referenzseitige Urlaubs-, Feiertags- und Schulferienquellen beeinflussen nur diese Tagesklassifikation.
- Pro Bereich wird zwischen reiner Zeit, Sunrise/Sunset und Golden Hour gewählt. Astro-Offsets werden global auf Auf-/Untergang beziehungsweise Golden-Hour-Beginn/-Ende addiert.
- Pro Rollladen kann Schließen über Zeit, Sunset, Golden Hour, Elevation oder Helligkeit erfolgen. Öffnen unterstützt Zeit, Sunrise, Golden Hour oder Helligkeit.
- `LateAllDown` schließt ausgewählte Rollläden zu einer festen späten Zeit. `betweenPosition` fährt zunächst eine Zwischenposition und `shutterDownComplete` später vollständig zu.
- Der Helligkeitssensor besitzt getrennte Auf-/Ab-Schwellen und früheste Ausführungszeiten.
- Jede automatische Fahrt respektiert Aktivierung, Fensterfreigabe, Alarmstatus, Frostschutz und aktuelle/letzte Aktionszustände.

## Beschattung

Beschattung ist pro Rollladen aktivierbar. Die Varianten kombinieren:

- Sonnenrichtung als Mittelpunkt plus Bereich,
- Innen- und/oder Außentemperatur,
- optional Helligkeit,
- eine globale Mindest-Elevation sowie ein Elevationsfenster zum Beschattungsende.

Startbedingungen verwenden strikte Schwellenvergleiche. Endbedingungen verwenden prozentuale Hysteresen für Temperatur und Helligkeit; optional wartet ein Endtimer. `heatProtection` ersetzt die Beschattungsposition durch die vollständige Schließposition, wenn die Außentemperatur den Heat-Protection-Wert überschreitet. `KeepSunProtect` verhindert das automatische Öffnen beim Ende.

`heatProtection` ist dabei kein unabhängiger Temperaturmodus: Es benötigt eine konfigurierte Außentemperaturquelle und gilt strikt bei `outsideTemp > tempHeatProtection`, ändert aber nur das Ziel einer ohnehin gültigen Sun-Protection-Entscheidung. Die gewählte Variante muss ihre normalen Innen-/Außentemperatur-, Helligkeits-, Azimut- und Elevationsbedingungen weiterhin erfüllen. Sinkt die Außentemperatur wieder, bleibt eine weiterhin gültige normale Beschattung ohne Gegenfahrt aktiv; ihr reguläres Ende einschließlich `KeepSunProtect` entscheidet über die Rückkehr.

Bei geschlossenem Rollladen kann `OpenInSunProtect` vorgemerkt werden, damit ein späteres automatisches Öffnen direkt auf die Beschattungsposition fährt. Eine manuelle Zwischenposition setzt `Manu_Mode`; manuelles Fahren auf bekannte Zielpositionen hält die zugehörige Automatik dagegen aktiv.

## Fenster, Aussperrschutz und Wiederherstellung

Ein Trigger kennt geschlossen, optional gekippt und sonst offen. `triggerChange` kann nur beim Öffnen, nur beim Schließen, in beide Richtungen oder gar nicht fahren. Vor einer Fensterfahrt werden Höhe und Aktion gesichert; beim Schließen kann die vorherige Verdunklungs-/Beschattungsposition wiederhergestellt werden.

`autoDrive` bestimmt, welche Automatikrichtungen bei offenem Fenster erlaubt sind. `driveAfterClose` stellt die zuvor verlangte Position nach dem Schließen wieder her.

Seit 2.1.0 kann `useOpenWindowLevel` bei einer automatischen Schließfahrt:

1. zuerst die normale Verdunklungsposition anfahren,
2. eine volle Fahrzeit warten,
3. den Kontakt erneut prüfen,
4. danach von unten auf die offene oder gekippte Lüftungsposition fahren.

Schließt das Fenster während der ersten Fahrt, bleibt der Rollladen geschlossen. Frost verhindert die zweite Fahrt. `oldHeight` wird auf die Schließposition gesetzt, damit die zweite automatische Fahrt nicht als manuelle Bewegung erkannt wird. Die Verdunklungsposition bleibt als `triggerHeight` für die spätere Wiederherstellung erhalten. Dies ist durch `lib/windowLevel.test.js` abgedeckt.

## Safety-Alarme und Prioritätsabweichung

Jeder Alarm besitzt eine globale Entity und Zielposition sowie eine Aktivierung pro Rollladen.

Der Referenzcode besitzt keine durchgehend feste Rangfolge für Nicht-Feuer-Alarme: `Fire` gewinnt immer; bei der Aktivierung von Rain, Wind 2, Wind 1 und Frost gewinnt dagegen das zuletzt verarbeitete Event. Erst bei der Rücknahme weist `shutterAlarm.js` in fester Reihenfolge `Rain > Wind 2 > Wind 1 > Frost` zu. Dokumentation und gewünschtes Cover-Control-Verhalten formulieren dagegen eine feste Rangfolge.

Cover Control übernimmt deshalb bewusst die deterministische Zielinvariante `Fire > Rain > Wind 2 > Wind 1 > Frost` für Aktivierung, gleichzeitige Zustände, Restart und Fallback. Diese Abweichung beseitigt die eventreihenfolgeabhängige Referenzsemantik. Feuer bleibt nach Rücknahme verriegelt: der persistente `fire_latched`-Zustand blockiert normale Automation, bis der Feuer-Sensor inaktiv ist und der Nutzer den Reset-Button betätigt.

Regen, Wind 2 und Wind 1 fahren bei Aktivierung auf ihre Profil-Zielposition. Nach Rücknahme wird kein separater Restore-Befehl erzeugt; die normale Cover-Control-Evaluation beziehungsweise der höchste verbleibende Alarm entscheidet unmittelbar neu.

Frost fährt einen bereits offenen Rollladen nicht präventiv. Er begrenzt eine spätere Schließfahrt auf die Frostposition und hebt nur einen bereits vollständig geschlossenen Rollladen bis dorthin an. Nach Rücknahme entscheidet die normale Evaluation neu; ein eigener Restore-Zustand wird nicht parallel aufgebaut.

## Saisonale Funktionen

Die Funktionen sind im aktuellen Quellcode aktiv und daher nicht historisch:

- `inSummerNotDown`: unterdrückt Schließfahrten je Rollladen innerhalb `SummerStart`/`SummerEnd`.
- `useXmasLevel`/`XmasLevel`: ersetzt innerhalb `XMasStart`/`XMasEnd` die normale Schließ- oder Zwischenposition.

Zeiträume über den Jahreswechsel werden unterstützt.

## Restart, manuelle Eingriffe und Edge Cases

- Persistierte Aktions- und Zielzustände werden beim Start hydriert; aktuelle Hardwarepositionen werden danach eingelesen.
- Positionen außerhalb der erwarteten automatischen Ziele werden nach einer Wartezeit als `Manu_Mode` erkannt. Mehrfachmeldungen langsamer Geräte werden durch `oldHeight`, `currentHeight` und zusätzliche Wartezeiten abgefangen.
- Level-Invertierung wird aus dem Verhältnis von `heightDown` zu `heightUp` abgeleitet.
- Alarme speichern den Hintergrundzustand einschließlich Fenster-Triggerzustand und stellen ihn nur bei erlaubter Rückkehr wieder her.
- Beschattung startet nicht aus beliebigen tieferen Positionen und öffnet einen regulär geschlossenen Rollladen beim Ende nicht versehentlich.
- Unload beendet Schedule-Jobs und die neuen Window-Level-Timer.

## Aktuelle Änderungen 2.1.x

- 2.1.0 (`33ded886…`): vollständiges Schließen mit anschließendem Anfahren der Lüftungsposition bei offenem/gekipptem Fenster, einschließlich Unload- und Manu-Mode-Schutz sowie Unit-Tests.
- 2.1.1 (`07b8918d…`): Änderung der Azimut-/Elevationsberechnung und State-Rollen.
- 2.1.2 (`1865efa…`): UI-Korrektur in `jsonTab`.

Reality Check zu 2.1.1: `main.js::sunPos()` übernimmt am untersuchten Commit die Rückgabewerte von `SunCalc.getPosition()` direkt und rundet sie, während Richtungskonfiguration und Dokumentation Gradwerte beschreiben. Vor 2.1.1 wurden die Werte in Grad konvertiert. Diese Inkonsistenz darf nicht blind in Cover Control übernommen werden; Home Assistants `sun.sun` liefert bereits Gradwerte und bleibt dort maßgeblich.

## Historische oder zur Laufzeit unbenutzte Optionen

Folgende globale `native`-Felder werden am untersuchten Commit in `main.js` und `lib/*.js` nicht als `adapter.config.<key>` gelesen und sind deshalb kein Beleg für aktive Funktionalität:

`UseAstro`, `UseSunMode`, `driveHeightDownAstro`, `driveHeightDownChildren`, `driveHeightDownLiving`, `driveHeightDownSleep`, `driveHeightSun`, `driveHeightUpAstro`, `driveHeightUpChildren`, `driveHeightUpLiving`, `driveHeightUpSleep`, globales `heatProtection`, `livingEnum`, `livingEnumAuto`, `sleepEnum`, `sleepEnumAuto`, `sunMonthStart`, `sunMonthEnd`, `sunProtecEnum`, `sun_shutterUp`, `sun_shutterDown` und globales `useXmasLevel`.

Die gleichnamigen **per-Rollladen** Felder `heatProtection` und `useXmasLevel` werden dagegen aktiv verwendet.

## Konsequenzen für Cover Control

- Controller/Global/Profile/Room/Runtime bleiben unverändert die Zielarchitektur.
- Feste Referenzbereiche werden durch frei benennbare Profile abgebildet.
- Ferien-/Urlaubs-/Schulferienlogik wird ausschließlich auf den bestehenden Workday-/Non-Workday-Mechanismus gemappt.
- Safety ist als eigene Profilfunktion umgesetzt: globale Quellen, Profil-Enabled/Zielwerte, Room-Teilnahme, Listener, eindeutige Trigger, Runtime-Priorität, Diagnose und Tests bilden die vollständige Kette.
- Safety wird vor Force, Manual, Kontakten und Komfortautomation ausgewertet. Der Fire-Latch liegt ausschließlich im persistenten Laufzeitstatus, nicht im Profil.
- Der 2.1.0-Fensterablauf ist umgesetzt: reguläre automatische Schließfahrten fahren bei offenem oder gekipptem Fenster zuerst das Schließziel an, warten die konfigurierte `drive_time`, lesen den Kontakt erneut und fahren erst danach die aktuelle Lockout-/Lüftungsposition an. Die Sequenz ist pro Cover und wird durch Safety, Force, Manual, Unload oder Reconfigure abgebrochen.
- Heat Protection ist als Teil der bestehenden Shading-Kette umgesetzt: Profilaktivierung und Außentemperaturschwelle verwenden die vorhandene Outdoor-Quelle, alle normalen Shading-Gates bleiben erforderlich, das Ziel wird auf `close_position` gesetzt und Safety bleibt dominant. Diagnose und persistierter Hold unterscheiden aktive Heat Protection von normaler Beschattung ohne Positions-Churn.
- Die Runtime-Trigger sind fachlich eindeutig; neue Safety-Trigger müssen dieselbe Trennung von `trigger` (Evaluationsursache) und `reason` (Fahrentscheidung) beibehalten.
- Saisonale Funktionen, Zwischenposition/spätes Komplettschließen und exaktes No-Go-Verhalten fehlen.

Die vollständige Statuszuordnung und Priorisierung steht in [`../../docs/shuttercontrol-parity.md`](file:///Users/andreasgrundke/Git/cover-control/docs/shuttercontrol-parity.md).

---
Verwandte Notizen:
* [`domain/priorities-and-lockout.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/priorities-and-lockout.md)
* [`domain/shading-and-solar-geometry.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/shading-and-solar-geometry.md)
* [`domain/manual-override-vs-automation.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/domain/manual-override-vs-automation.md)
