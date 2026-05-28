# Legrand UPS (CS121) — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Monitor a **Legrand UPS** (Keor, Daker DK, Megaline, …) — or any UPS fitted
with a **Generex CS121 / CS141** network adapter — directly in Home Assistant
over **SNMP v2c** (RFC 1628 UPS-MIB). Local polling, no cloud.

## Features

One device with:

**Sensors** — battery charge %, runtime remaining, time on battery, battery
voltage / current / temperature, battery status (enum), input voltage /
frequency / current / power, output source (enum: mains / battery / bypass /
…), output voltage / frequency / current / power / load %, active alarm count.

**Binary sensors** — On battery, Mains present, Battery low, Alarm, and a
dedicated **Connection** sensor (stays available when polling fails — use it
to trigger a "UPS unreachable" notification).

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/spiri439/cs121-legrand-ups` with category **Integration**.
3. Install **Legrand UPS (CS121)**, then restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → Legrand UPS (CS121)**.

### Manual installation

Copy `custom_components/cs121_legrand_ups` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

| Field | Default | Notes |
|-------|---------|-------|
| Host / IP | — | IP of the CS121 adapter |
| Port | 161 | SNMP port |
| SNMP community | `public` | Set the same value the CS121 uses |
| Scan interval | 30 s | Adjustable later via the integration options |

## How it reads the device

The integration polls the standard **UPS-MIB (RFC 1628)** branch
`1.3.6.1.2.1.33.x`:

- Battery: `1.2.{1..7}.0` (status, seconds-on-battery, minutes-remaining,
  charge %, voltage ×10, current ×10, temperature °C).
- Input (line 1): `1.3.3.1.{2..5}.1` (frequency ×10, voltage, current ×10,
  true power W).
- Output: `1.4.1.0` (source enum) and `1.4.4.1.{2..5}.1` (voltage, current
  ×10, power, load %).
- Alarms: `1.6.1.0` (active alarm count).

Identification strings (`1.1.{1..5}.0`) populate the HA device's
manufacturer / model / firmware fields on first successful read.

## Disclaimer

Not affiliated with Legrand or Generex. "Legrand", "CS121" and "CS141" are
trademarks of their respective owners. Use at your own risk.
