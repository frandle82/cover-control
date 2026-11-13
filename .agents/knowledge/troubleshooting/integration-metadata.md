---
title: Cover Control Integrationsmetadaten
type: troubleshooting
status: active
tags:
  - home-assistant
  - hacs
  - metadata
---

# Cover Control Integrationsmetadaten

## Entscheidungen

* Die IoT-Class ist `calculated`: Cover Control kommuniziert nicht direkt mit
  Geräten oder einem Cloud-Dienst. Es berechnet Steuerentscheidungen aus
  Home-Assistant-Entity-Zuständen und lokalen Zeitereignissen.
* Die einzige Kategorie ist `blinds_curtains`; sie beschreibt den primären
  Zweck der Integration. Die Lüftungslogik ist eine Nebenbedingung und keine
  zweite Produktkategorie.
* `country` ist nicht gesetzt. Ohne technische Länderbeschränkung würde das
  optionale HACS-Feld die Auffindbarkeit unnötig einschränken.

## Quellen

* Home Assistant Manifest: `calculated` bedeutet, dass die Integration mit
  nichts kommuniziert und ihr Ergebnis berechnet.
  <https://contributors.home-assistant.io/core/integrations/manifest/>
* Home Assistant Kategorien: `blinds_curtains` umfasst Jalousien, Vorhänge,
  Rollläden und Markisen.
  <https://contributors.home-assistant.io/core/integrations/categories/>
* HACS setzt `country` nur für Repositories voraus, die auf einzelne oder
  begrenzte Länder ausgerichtet sind.
  <https://www.hacs.xyz/docs/publish/include/>

---
Verwandte Notizen:
* [`ha-2026-11-test-toolchain.md`](ha-2026-11-test-toolchain.md)
