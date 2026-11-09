# CCA parity

Compared against `hvorragend/ha-blueprints` main @ `f7d10410aff3b96d909002584b150e0b4c370675`.

This matrix compares the current `ha-blueprints` CCA blueprint with the native
Cover Control model. `Before/After Actions` are an intentional architecture
difference: Cover Control exposes `Aktive Steuerung` and leaves external HA
automation actions outside the integration.

| Area | Status | Mapping / note |
| --- | --- | --- |
| Sun fixed elevation | FULL | Explicit opening/closing modes use fixed group thresholds and HA `sun.sun` elevation. |
| Sun dynamic elevation | NOT_APPLICABLE | Removed from the target model; legacy values migrate deterministically to fixed elevation. |
| Sun hybrid elevation | NOT_APPLICABLE | Removed from the target model; legacy values migrate deterministically to fixed elevation. |
| Configurable sun source | NOT_APPLICABLE | Cover Control uses the HA location and canonical `sun.sun`; no redundant source selector is exposed. |
| Dynamic sun room sources | NOT_APPLICABLE | Dynamic elevation sources are outside the simplified shuttercontrol-style model. |
| Restart/outage catch-up | FULL | Explicit startup/runtime-outage state with `never`, `outage` and `always` recovery modes; dependencies unavailable during startup remain in startup until the initial dependency set becomes usable. |
| Fixed drive delay | FULL | Deterministic pre-drive delay with post-wait live-gate and target rechecks. |
| Manual override | MAPPED | Native override state and clear/re-evaluate behavior. |
| Tilt reposition | FULL | Native tilt-before-position mode is available. |
| Tilt tolerance | FULL | Separate configurable tilt tolerance is persisted, resolved and used for tilt no-op decisions. |
| Shading mode selection | FULL | Seven fixed shuttercontrol-style modes cover UI, persistence, sources, listeners, runtime, diagnostics, migration and regression tests. |
| Before/After Actions | MAPPED | `Aktive Steuerung` plus external HA automations. |
| CCA status helper | NOT_APPLICABLE | Runtime status is native Cover Control state and entities. |

The matrix is deliberately explicit: fields alone do not make a feature FULL;
the UI, persistence, resolver, listener, runtime decision, movement and test
chain must all be present.
