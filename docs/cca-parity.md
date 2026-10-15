# CCA parity

Compared against `hvorragend/ha-blueprints` main @ `f7d10410aff3b96d909002584b150e0b4c370675`.

This matrix compares the current `ha-blueprints` CCA blueprint with the native
Cover Control model. `Before/After Actions` are an intentional architecture
difference: Cover Control exposes `Aktive Steuerung` and leaves external HA
automation actions outside the integration.

| Area | Status | Mapping / note |
| --- | --- | --- |
| Sun fixed elevation | FULL | Fixed thresholds and duration are evaluated by the room runtime. |
| Sun dynamic elevation | FULL | Configured open/close sensors, use switches, fallback to fixed. |
| Sun hybrid elevation | FULL | Dynamic value plus the fixed threshold as offset. |
| Configurable sun source | MAPPED | Global `sun_sensor`, default `sun.sun`; room source overrides are supported. |
| Dynamic sun room sources | MAPPED | Dynamic open/close sources are resolvable per room. |
| Force controls | FULL | Room UI, resolver, listeners, explicit priority, shared safety gates and imperative compatibility path. |
| Force pause | FULL | Entity pause blocks dispatch and release requests fresh evaluation, including delayed movements. |
| Restart/outage catch-up | FULL | Explicit startup/runtime-outage state with `never`, `outage` and `always` recovery modes; dependencies unavailable during startup remain in startup until the initial dependency set becomes usable. |
| Fixed/random drive delay | FULL | Central combined pre-drive delay with post-wait live-gate, force and target rechecks. |
| Manual override | MAPPED | Native override state and clear/re-evaluate behavior. |
| Tilt reposition | FULL | Native tilt-before-position mode is available. |
| Tilt tolerance | FULL | Separate configurable tilt tolerance is persisted, resolved and used for tilt no-op decisions. |
| Shading custom sensor | MAPPED | Additional shading conditions and configured sources cover the same use case. |
| Before/After Actions | MAPPED | `Aktive Steuerung` plus external HA automations. |
| CCA status helper | NOT_APPLICABLE | Runtime status is native Cover Control state and entities. |

The matrix is deliberately explicit: fields alone do not make a feature FULL;
the UI, persistence, resolver, listener, runtime decision, movement and test
chain must all be present.
