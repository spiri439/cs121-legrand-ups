# Legrand UPS (CS121) — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Monitor a **Legrand UPS** (Keor, Daker DK, Megaline, ARCHIMOD, …) — or any UPS
fitted with a **Generex CS121 / CS141** network adapter — directly in Home
Assistant over **SNMP v2c** (RFC 1628 UPS-MIB) **or Modbus TCP**. Local
polling, no cloud.

## SNMP or Modbus?

Pick the transport when you add the integration:

- **SNMP** (default, port 161) — broadest telemetry, including per-phase input
  current/power and time-on-battery.
- **Modbus TCP** (port 502) — choose this if you need the **UPS alarm flags**
  (e.g. *Input bad*, *Output overload*, *Bypass bad*). Some CS121 firmwares
  leave the RFC 1628 SNMP alarm table empty even while the web UI shows an
  alarm; those flags are only exposed over Modbus.

Shared values (battery, voltages, frequency, load, …) are reported identically
on both transports, so dashboards and automations don't care which you use.

## Features

One device with:

**Sensors** — battery charge %, runtime remaining, time on battery, battery
voltage / current / temperature, battery status (enum), input voltage /
frequency / current / power, output source (enum: mains / battery / bypass /
…), output voltage / frequency / current / power / load %, active alarm count,
**UPS status** (e.g. "UPS is ON. Input bad.") and **Active alarms** list.

**Binary sensors** — On battery, Mains present, Battery low, Alarm, a dedicated
**Connection** sensor (stays available when polling fails — use it to trigger a
"UPS unreachable" notification), plus one **problem** sensor per well-known
alarm (Input bad, Output bad, Output overload, Bypass bad, Over temperature, …)
— populated from the SNMP alarm table or the Modbus alarm registers.

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
| Protocol | `snmp` | `snmp` or `modbus` |
| Port | 161 | **161** for SNMP, **502** for Modbus TCP |
| SNMP community | `public` | SNMP only — set the same value the CS121 uses |
| Modbus unit ID | 1 | Modbus only — the CS121 answers on unit 1 |
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

On **Modbus** the same data comes from input/holding registers (function 3/4,
unit 1) per the Legrand CS121 Modbus spec — telemetry at registers 100–145 and
the UPS status bitfield (109) and per-alarm flags (115–139, e.g. **120 = Input
bad**). Registers are scaled back to the same units as SNMP so every entity
value matches.

## Disclaimer

Not affiliated with Legrand or Generex. "Legrand", "CS121" and "CS141" are
trademarks of their respective owners. Use at your own risk.
