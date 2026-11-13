---
title: Home Assistant 2026.11 Test-Toolchain
type: troubleshooting
status: active
tags:
  - home-assistant
  - testing
  - compatibility
---

# Home Assistant 2026.11 Test-Toolchain

## Historischer Befund

`pytest-homeassistant-custom-component` 0.13.375 reicht nur bis Home Assistant 2026.10.4.
Mit Home Assistant 2026.11 kann sie die Tests nicht laden.

## Abgelöste Testbasis

* Das offizielle, im Home-Assistant-Core gepflegte Paket
  `pytest-homeassistant==2026.11.1` pinnt `homeassistant==2026.11.1`.
* Es ersetzt `pytest-homeassistant-custom-component`; die Testimporte wechseln von
  `pytest_homeassistant_custom_component` zu `pytest_homeassistant`.
* Die pytest-Konfiguration muss `-p no:respx` setzen, damit Home Assistant vor dem
  separaten `respx`-Plugin seinen `httpx`-Alias installiert.
* Der frühere Wrapper für `enable_custom_integrations` ist nicht nötig: das offizielle
  Plugin aktiviert Custom Integrations standardmäßig.

## Konsequenzen / Wichtige Hinweise

* CI installiert beide Versionen über `pytest-homeassistant==2026.11.1` und gibt sie aus.
* Die vollständige Cover-Control-Suite läuft mit dieser Kombination (384 Tests).
* Home Assistant 2026.11 besitzt keinen `Store._manager`; Tests dürfen diese private
  Cache-Implementierung nicht verwenden.
* Cover-Control-Produktcode bleibt unverändert.

## Mindestversion-Befund (2026-11-13)

`hacs.json` deklarierte Home Assistant 2025.2.0, aber dieser Stand besitzt weder
`ConfigEntry.subentries` noch `ConfigEntries.async_remove_subentry`. Cover Control
verwendet beide APIs für die Legacy-Subentry-Migration in `__init__.py`; sie sind ab
Home Assistant 2025.3.0 verfügbar. Eine 2025.2-Testmatrix darf daher nicht ergänzt
werden, ohne den Produktivcode oder die deklarierte Mindestversion zu ändern.

Die verifizierte Mindestbasis ist Python 3.13 mit
`pytest-homeassistant-custom-component==0.13.221`; sie pinnt exakt
`homeassistant==2025.3.0`. Aktuelle Tests importieren `pytest_homeassistant`, daher
stellt `tests/conftest.py` für die historische Testbasis zentral den gleichwertigen
Legacy-Importpfad bereit und aktiviert Custom Integrations. Beide Baselines bestehen
vollständig: HA 2025.3.0 / Python 3.13 / Legacy-Plugin und HA 2026.11.1 / Python 3.14 /
`pytest-homeassistant==2026.11.1` mit jeweils 384 Tests.

---
Verwandte Notizen:
* [`home-assistant-async-guidelines.md`](home-assistant-async-guidelines.md)
