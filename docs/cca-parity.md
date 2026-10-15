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
| Force controls | PARTIAL | Room UI, resolver, listeners and runtime priority exist; legacy imperative force paths still need consolidation and dedicated regression coverage. |
| Force pause | PARTIAL | Entity pause blocks new evaluation and releases through event-driven evaluation; delay/recovery integration remains. |
| Restart/outage catch-up | PARTIAL | Structural config recovery exists; CCA event catch-up is not complete. |
| Fixed/random drive delay | PARTIAL | Central fixed plus random pre-drive delay and live gate recheck exist; ownership/recovery semantics and full regression coverage remain. |
| Manual override | MAPPED | Native override state and clear/re-evaluate behavior. |
| Tilt reposition | FULL | Native tilt-before-position mode is available. |
| Tilt tolerance | FULL | Separate configurable tilt tolerance is persisted, resolved and used for tilt no-op decisions. |
| Shading custom sensor | MAPPED | Additional shading conditions and configured sources cover the same use case. |
| Before/After Actions | MAPPED | `Aktive Steuerung` plus external HA automations. |
| CCA status helper | NOT_APPLICABLE | Runtime status is native Cover Control state and entities. |

The matrix is deliberately explicit: fields alone do not make a feature FULL;
the UI, persistence, resolver, listener, runtime decision, movement and test
chain must all be present.
