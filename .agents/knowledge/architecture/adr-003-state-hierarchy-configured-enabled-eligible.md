---
title: ADR-003: Dreistufiges Funktions-Zustandsmodell
type: adr
status: accepted
date: 2026-11-08
tags: [architecture, state-machine, runtime, groups]
---

# Configured / Enabled / Eligible

| Zustand | Bedeutung |
|---|---|
| `configured` | Funktion gehört zum festen Gruppenmodell. |
| `enabled` | Der zugehörige Laufzeitschalter ist eingeschaltet. |
| `eligible` | Die aktuellen Umwelt- und Sicherheitsbedingungen erlauben eine Aktion. |

Ein Schalter ändert niemals persistierte Gruppen- oder Room-Konfiguration. Alle drei Ebenen werden getrennt diagnostiziert und getestet.
