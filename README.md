# Cover Control for Home Assistant

Cover Control is a Home Assistant custom integration that automates blinds and shutters with fine-grained safety, shading and ventilation logic. It is based on the original Cover Control Automation (CCA) blueprint, bringing those inputs into a
guided configuration flow and adding per-cover controllers that react to sensor changes and time-based triggers.

## Features
- **Guided setup & options**: Configure covers, schedules, brightness and sun elevation thresholds, window/door contacts, ventilation lockout, and shading preferences via the built-in config and options flows.
- **Per-cover runtime control**: A controller monitors time windows and sensor state to open, close, shade, tilt, or stop automation when conditions (brightness, sun, occupancy, ventilation, vacation overrides) are not met.
- **Condition overrides**: Optional binary sensors, input booleans or switches can gate opening, closing, ventilation start/stop, shading in/out, and
  shading tilt so you can temporarily disable or force specific behaviors.
- **Service hooks**: Trigger immediate shading or pause automation for a cover for a set duration through Home Assistant
  services.
- **Diagnostics & transparency**: Datapoint sensors expose the latest target position, reason for the action, override
  status, and the next planned open/close timestamps.

## Requirements
- Home Assistant 2023.9 or newer.
- At least one supported cover entity.
- Optional: binary sensors, input booleans or switches for brightness, sun position, doors/windows, vacation mode, ventilation, and any conditional
  overrides you want to use.

## Installation
### HACS (recommended)
1. In HACS, open **Integrations** → menu **Custom repositories** and add this repository URL as a **Integration**.
2. Search for **Cover Control** in HACS and install.
3. Restart Home Assistant.

### Manual copy
1. Download the latest release archive.
2. Copy the `custom_components/cover_control` folder into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration
1. Go to **Settings → Devices & Services → Add Integration** and search for **Cover Control**.
2. Follow the wizard to select covers, define opening/closing windows, shading positions, brightness and sun thresholds,
   and optional sensors.
3. After setup, open the integration's **Configure** dialog to adjust options or add conditional override sensors at any
   time.

### Services
- `shuttercontrol.set_manual_override`: Pause automation for a cover for a specified number of minutes.
- `shuttercontrol.activate_shading`: Immediately move a cover to its shading position and hold it using the override timer.

## Entities
- **Master switch**: Enables/disables automation globally and exposes attributes for any settings that differ from the defaults.
- **Cover switches**: Per-cover automation toggles (state only, no extra attributes).
- **Datapoint sensors**: Per-cover sensors reporting target position, reason, manual override window, and next
  open/close times.
  
## Troubleshooting
- Ensure all referenced entities (covers, binary sensors) exist and are available; invalid entities will be flagged during configuration.
- If actions do not trigger, check that the relevant condition sensors are **on** (true) and that manual overrides or
  ventilation locks are not active.
- Review Home Assistant logs for `shuttercontrol` entries to understand why an action was skipped or deferred.
