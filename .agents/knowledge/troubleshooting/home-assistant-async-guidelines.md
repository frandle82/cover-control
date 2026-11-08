---
title: Home Assistant Async Guidelines & Event-Loop Schutz
type: troubleshooting
status: active
tags:
  - troubleshooting
  - home-assistant
  - async
  - event-loop
  - performance
---

# Home Assistant Async Guidelines & Event-Loop Schutz

## Problem
Wird im Home Assistant Event-Loop eine synchrone, blockierende Operation ausgeführt (z. B. File-I/O, synchrone HTTP-Aufrufe, `time.sleep()`), friert der gesamte Home Assistant Core kurzzeitig ein. Home Assistant protokolliert dies mit Warnungen:
`WARNING (MainThread) [homeassistant.util.async_] Detected blocking call to open inside the event loop...`

## Regeln für Cover Control

### 1. I/O immer in Executor auslagern
Wenn Dateizugriffe (z. B. Blueprint-Inspektion, JSON-Parsing von Platten) notwendig sind:
```python
result = await hass.async_add_executor_job(blocking_function, arg1, arg2)
```

### 2. Keine blockierenden Sleeps
* Niemals `time.sleep()` verwenden.
* Wenn asynchron gewartet werden muss: `await asyncio.sleep(seconds)` nutzen.
* Für zeitgesteuerte Aktionen: Home Assistant Helfer wie `async_call_later` oder `async_track_point_in_time` verwenden.

### 3. Non-blocking Callbacks
* Funktionen, die mit `@callback` dekoriert sind, laufen direkt im Event-Loop. Sie dürfen weder `await` enthalten noch blockieren.
* Sämtliche Berechnungen in Callbacks müssen rein in-memory sein.

### 4. Ressourcen-Cleanup beim Unload
* Alle `async_track_*`-Listener müssen bei `async_unload_entry` deregistriert werden.
* Hintergrund-Tasks (`async_create_task`) müssen getrackt und bei Unload abgebrochen (`task.cancel()`) werden.

---
Verwandte Notizen:
* [`../architecture/adr-001-mixin-architecture.md`](../architecture/adr-001-mixin-architecture.md)
* [`../architecture/adr-002-config-entry-vs-subentry.md`](../architecture/adr-002-config-entry-vs-subentry.md)
