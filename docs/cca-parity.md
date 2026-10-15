# CCA parity

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
| Force controls | NOT_IMPLEMENTED | No native force entity model yet. |
| Force pause | NOT_IMPLEMENTED | No native force-pause entity model yet. |
| Restart/outage catch-up | PARTIAL | Structural config recovery exists; CCA event catch-up is not complete. |
| Fixed/random drive delay | NOT_IMPLEMENTED | `drive_time` remains feedback/manual-drive timing only. |
| Manual override | MAPPED | Native override state and clear/re-evaluate behavior. |
| Tilt reposition | FULL | Native tilt-before-position mode is available. |
| Tilt tolerance | PARTIAL | Position tolerance is implemented; separate tilt tolerance is pending. |
| Shading custom sensor | MAPPED | Additional shading conditions and configured sources cover the same use case. |
| Before/After Actions | MAPPED | `Aktive Steuerung` plus external HA automations. |
| CCA status helper | NOT_APPLICABLE | Runtime status is native Cover Control state and entities. |

The matrix is deliberately explicit: fields alone do not make a feature FULL;
the UI, persistence, resolver, listener, runtime decision, movement and test
chain must all be present.
