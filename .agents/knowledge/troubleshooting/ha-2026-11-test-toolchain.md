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

---
Verwandte Notizen:
* [`home-assistant-async-guidelines.md`](home-assistant-async-guidelines.md)
