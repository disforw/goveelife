<p align="center">
  <img src="custom_components/goveelife/brand/logo@2x.png" alt="GoveeLife" width="400">
</p>

<h1 align="center">GoveeLife for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="https://github.com/disforw/goveelife/releases"><img src="https://img.shields.io/github/v/release/disforw/goveelife" alt="Latest release"></a>
  <a href="https://github.com/disforw/goveelife/actions/workflows/test.yaml"><img src="https://img.shields.io/github/actions/workflow/status/disforw/goveelife/test.yaml?label=tests" alt="Tests"></a>
  <a href="https://github.com/disforw/goveelife/actions/workflows/hassfest.yaml"><img src="https://img.shields.io/github/actions/workflow/status/disforw/goveelife/hassfest.yaml?label=hassfest" alt="Hassfest"></a>
  <a href="https://github.com/disforw/goveelife/issues"><img src="https://img.shields.io/github/issues/disforw/goveelife" alt="Open issues"></a>
</p>

<p align="center">
  🏠 Bring your <strong>Govee</strong> smart home devices into Home Assistant — natively, via the official cloud API.<br>
  No bridges, no reverse-engineering, no polling your LAN at 2am.
</p>

---

## ✨ Why this integration

Govee makes a *lot* of devices — lights, fans, heaters, humidifiers, ice makers, sensors, you name it. This integration talks to the [Govee OpenAPI v2](https://developer.govee.com/) and builds Home Assistant entities straight from whatever capabilities your device reports.

That means:

- 🔍 **Auto-discovery** — every device on your Govee account shows up automatically, no SKU allow-list to maintain.
- 🧩 **Capability-driven** — entities are built from what the API says your device *can do*, not a hardcoded guess.
- 🔄 **Keeps up with new hardware** — as Govee ships new devices that speak the same API shapes (lights, toggles, work modes, ranges…), they tend to just work.

## 📦 What kind of devices work today

We've had real success across these device families — exact models vary, and new ones get picked up automatically:

| 🏷️ Device family | 🧰 Shows up as | 💡 What you get |
|---|---|---|
| **Lights** (bulbs, strips, panels, RGBIC) | `light` | On/off, brightness, RGB & color temp, scenes, DIY scenes, per-segment control |
| **Fans & Air Purifiers** | `fan` | On/off, speed, preset/work modes |
| **Heaters & Kettles** | `climate` | On/off, HVAC mode, target & current temperature |
| **Humidifiers & Dehumidifiers** | `humidifier` | On/off, target humidity, mode |
| **Switches & Plugs** (incl. ice makers, diffusers) | `switch` | On/off toggles |
| **Thermometers & Hygrometers** | `sensor` | Temperature, humidity, air quality |
| **Appliance nightlights & alerts** | `light` / `binary_sensor` | Brightness & color on appliance nightlights; water-full / ice-full style event alerts |

Got something that's not listed, or a device that's only *half* working? That's exactly what [issues](https://github.com/disforw/goveelife/issues) are for — see below.

## 🚀 Installation

### Via HACS (recommended)

1. Make sure [HACS](https://www.hacs.xyz/docs/use/) is installed.
2. HACS → **⋮** → **Custom repositories** → add `https://github.com/disforw/goveelife` as an **Integration**.
3. Search for **GoveeLife** in HACS and download it.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/goveelife` into your HA `config/custom_components/` folder.
2. Restart Home Assistant.

## ⚙️ Setup

1. 📱 In the **Govee Home** app: **Settings → Apply for API Key** (arrives by email within a few minutes).
2. In HA: **Settings → Devices & Services → Add Integration → GoveeLife**.
3. Paste your API key and (optionally) set a poll interval.

> ⏱️ The Govee cloud API is rate-limited. The default poll interval works for most setups — don't go much lower unless you enjoy throttling.

Once added, every device on your account shows up automatically. No further configuration needed.

## 🩺 Troubleshooting

**Device isn't showing up**
Confirm it's online in the Govee Home app. Not every Govee product is exposed through the cloud API yet — check the [Govee Developer site](https://developer.govee.com/) for coverage, or reload the integration (**Settings → Devices & Services → GoveeLife → ⋮ → Reload**).

**State looks stale / commands feel slow**
That's usually the cloud API's rate limit, not a bug — HA will catch up on the next poll.

**Something's missing or broken for your device**
Open an [issue](https://github.com/disforw/goveelife/issues/new) and attach your device's raw API response (strip your API key and MAC addresses first):

```bash
curl -H 'Govee-API-Key: YOUR_KEY_HERE' \
     -X GET https://openapi.api.govee.com/router/api/v1/user/devices \
     -o govee_devices.json
```

The integration also ships a built-in [Diagnostics](https://www.home-assistant.io/integrations/diagnostics/) download for bug reports — it includes your device capability dump with sensitive data redacted.

## 🤝 Contributing

PRs welcome! A few guidelines:

- Open an issue first for anything beyond a small fix.
- Match the existing style (async, type hints, HA entity patterns).
- Add a regression test where you can — the Govee API has no sandbox, so tests are how we keep devices working across releases.

## ❤️ Credits

Maintained by [@disforw](https://github.com/disforw) and the community, built on the [Govee OpenAPI v2](https://developer.govee.com/).
