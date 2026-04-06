# GoveeLife — Home Assistant Integration

A community-maintained [HACS](https://hacs.xyz) custom integration that connects your Govee smart home devices to Home Assistant via the [Govee OpenAPI v2](https://developer.govee.com/).

> **Current version:** v4.B3 (pre-release) · [Changelog](https://github.com/disforw/goveelife/releases)

---

## Supported Device Types

The integration auto-discovers all devices on your Govee account and creates entities based on each device's reported capabilities. No SKU hardcoding — if your device exposes a capability through the API, it will be available in HA.

| Device Type | HA Platform | Capabilities |
|---|---|---|
| **Lights** | `light` | On/off, brightness, RGB color, color temperature, scenes, DIY scenes, RGBIC segments |
| **Heaters** | `climate` | On/off, target temperature, current temperature, HVAC mode |
| **Tea Kettles** | `climate` | On/off, target temperature |
| **Air Purifiers** | `fan` | On/off, preset modes |
| **Fans** | `fan` | On/off, speed, preset modes, oscillation |
| **Humidifiers** | `humidifier` | On/off, target humidity, preset modes, humidity/temperature sensors |
| **Ice Makers** | `switch` | On/off |
| **Aroma Diffusers** | `switch` | On/off |
| **Smart Plugs / Sockets** | `switch` | On/off |
| **Wi-Fi Thermometers** | `sensor` | Temperature, humidity |

### RGBIC / Segmented Lights

Devices with per-zone LED control (such as ceiling panels and backlight kits) get individual segment entities — one `light` entity per zone — in addition to the main device entity. Segments support independent color and brightness control.

Confirmed segmented devices: H6076, H60A1, H60A4, H60B2, H70C7, H7075 and any device exposing `segment_color_setting` in the API.

---

## Installation

### Via HACS (recommended)

1. Make sure [HACS is installed](https://www.hacs.xyz/docs/use/).
2. In the HACS UI, click the **⋮ menu** (top-right) → **Custom repositories**.
3. Add `https://github.com/disforw/goveelife` as type **Integration** and click **Add**.
4. Search for **goveelife** in HACS and click **Download**.
5. Restart Home Assistant.

### Manual

1. Download or clone this repository.
2. Copy the `custom_components/goveelife` folder into your HA `config/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

### 1. Get your Govee API key

1. Open the **Govee Home** app on your phone.
2. Go to **Settings** → **Apply for API Key**.
3. Check your email — Govee will send the key within a few minutes.

> **Note:** The Govee API has rate limits. Setting the poll interval too low will result in throttling. The default interval is recommended for most setups; 60–120 seconds is a good starting point.

### 2. Add the integration

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **GoveeLife** and follow the prompts.
3. Enter your API key.
4. Optionally set the **poll interval** (in seconds). A lower value gives faster state updates but increases API calls.

Once configured, the integration will discover all devices on your Govee account and add them to HA automatically.

---

## Features

### Lights

- **On/off** — basic power control
- **Brightness** — full 1–100% range via HA brightness slider
- **RGB color** — full color wheel support
- **Color temperature** — warm/cool white adjustment (where supported by hardware)
- **Scenes** — Govee built-in lighting scenes (dynamic effects like "Ocean", "Sunset", etc.)
- **DIY scenes** — your custom scenes from the Govee Home app
- **Per-segment control** — on RGBIC devices, each zone is a separate `light` entity with independent color and brightness

### Fans

- On/off, speed levels, preset modes (Normal, Sleep, Auto, etc.)
- Oscillation toggle (H7102, H7106, H7120 and compatible models)

### Climate (Heaters & Kettles)

- On/off, HVAC mode, target and current temperature

### Humidifiers

- On/off, target humidity, preset modes
- `sensor` entities for `sensorHumidity` and `sensorTemperature` where the device exposes them

### Diagnostics

The integration includes a [HA Diagnostics](https://www.home-assistant.io/integrations/diagnostics/) endpoint. If you're reporting a bug, please include the diagnostics download — it contains your full device capability dump (with sensitive data redacted).

---

## Troubleshooting

### My device isn't showing up

- Make sure the device is visible in the Govee Home app and linked to your account.
- Not all Govee devices are supported by the cloud API. Check the [Govee Developer site](https://developer.govee.com/) for API coverage.
- Try refreshing the integration: **Settings → Devices & Services → GoveeLife → ⋮ → Reload**.

### Controls aren't working / state is wrong

- The Govee cloud API has rate limits (~10 requests/minute per device). If you're hitting limits, Home Assistant will show stale state until the next successful poll.
- Check the HA logs (`Settings → System → Logs`) for `goveelife` errors.

### Segments won't turn off (RGBIC devices like H60A4)

- This was a bug in v4.B2 and v4.B3 — segments would clamp to ~1% brightness instead of fully turning off.
- Fixed in the current `main` branch (see [PR #134 fix](https://github.com/disforw/goveelife/issues/134)).

### I want to help / my device isn't supported

The more API response data we have, the more devices we can support. If your device isn't working or is missing features, please open an issue and include your device's API response:

```bash
curl -H 'Govee-API-Key: YOUR_KEY_HERE' \
     -X GET https://openapi.api.govee.com/router/api/v1/user/devices \
     -o govee_devices.json
```

Attach the `govee_devices.json` to your issue. **Remove your API key and sanitize any MAC addresses before posting.**

---

## Contributing

Pull requests are welcome. Please:

- Open an issue first to discuss significant changes.
- Follow the existing code style (async, type hints, HA patterns).
- Test against a real device if possible — the Govee API doesn't have a sandbox.

---

## Credits

Maintained by [@disforw](https://github.com/disforw) with contributions from the community.  
Uses the [Govee OpenAPI v2](https://developer.govee.com/).
