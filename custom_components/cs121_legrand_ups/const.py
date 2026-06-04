"""Constants for the CS121 Legrand UPS integration.

Speaks SNMP v2c (and v3) against the Generex CS121 network adapter using
the standard UPS-MIB (RFC 1628, OID branch 1.3.6.1.2.1.33). The CS121 is
shipped by Legrand and several other UPS brands, so the same MIB applies
regardless of label.
"""
from __future__ import annotations

DOMAIN = "cs121_legrand_ups"

# Config keys
CONF_COMMUNITY = "community"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PROTOCOL = "protocol"          # "snmp" or "modbus"
CONF_MODBUS_UNIT = "modbus_unit"    # Modbus slave/unit id

# Transport protocols
PROTOCOL_SNMP = "snmp"
PROTOCOL_MODBUS = "modbus"
PROTOCOLS = (PROTOCOL_SNMP, PROTOCOL_MODBUS)

# Defaults
DEFAULT_NAME = "Legrand UPS"
DEFAULT_PORT = 161                  # SNMP
DEFAULT_MODBUS_PORT = 502           # Modbus TCP
DEFAULT_MODBUS_UNIT = 1
DEFAULT_COMMUNITY = "public"
DEFAULT_PROTOCOL = PROTOCOL_SNMP
DEFAULT_SCAN_INTERVAL = 30  # seconds
SNMP_TIMEOUT = 5

# --- RFC 1628 UPS-MIB OIDs (branch 1.3.6.1.2.1.33) ---

# Identification group (read once for device_info; values are OctetStrings)
OID_IDENT_MANUFACTURER = "1.3.6.1.2.1.33.1.1.1.0"
OID_IDENT_MODEL        = "1.3.6.1.2.1.33.1.1.2.0"
OID_IDENT_SW_VERSION   = "1.3.6.1.2.1.33.1.1.3.0"
OID_IDENT_AGENT_SW     = "1.3.6.1.2.1.33.1.1.4.0"
OID_IDENT_NAME         = "1.3.6.1.2.1.33.1.1.5.0"

# Battery group
OID_BATTERY_STATUS         = "1.3.6.1.2.1.33.1.2.1.0"   # 1=unknown 2=normal 3=low 4=depleted
OID_SECONDS_ON_BATTERY     = "1.3.6.1.2.1.33.1.2.2.0"   # s
OID_MINUTES_REMAINING      = "1.3.6.1.2.1.33.1.2.3.0"   # min
OID_CHARGE_REMAINING       = "1.3.6.1.2.1.33.1.2.4.0"   # %
OID_BATTERY_VOLTAGE        = "1.3.6.1.2.1.33.1.2.5.0"   # 0.1 V DC
OID_BATTERY_CURRENT        = "1.3.6.1.2.1.33.1.2.6.0"   # 0.1 A DC
OID_BATTERY_TEMPERATURE    = "1.3.6.1.2.1.33.1.2.7.0"   # °C

# upsInputLineBads — cumulative count of times the input went out of tolerance.
# On this CS121 firmware this is the only always-available "input bad" signal
# (the RFC 1628 alarm table stays empty), so it's polled every cycle.
OID_INPUT_LINE_BADS = "1.3.6.1.2.1.33.1.3.1.0"

# Line counts (read once to discover topology — single- or three-phase).
OID_INPUT_NUM_LINES  = "1.3.6.1.2.1.33.1.3.2.0"
OID_OUTPUT_NUM_LINES = "1.3.6.1.2.1.33.1.4.3.0"

# Per-line input table builders. Line index 1 is L1, etc.
def input_frequency_oid(line: int) -> str: return f"1.3.6.1.2.1.33.1.3.3.1.2.{line}"  # 0.1 Hz
def input_voltage_oid(line: int)   -> str: return f"1.3.6.1.2.1.33.1.3.3.1.3.{line}"  # V RMS
def input_current_oid(line: int)   -> str: return f"1.3.6.1.2.1.33.1.3.3.1.4.{line}"  # 0.1 A RMS
def input_power_oid(line: int)     -> str: return f"1.3.6.1.2.1.33.1.3.3.1.5.{line}"  # W

# Output scalars and per-line table builders.
OID_OUTPUT_SOURCE    = "1.3.6.1.2.1.33.1.4.1.0"          # 1=other 2=none 3=normal 4=bypass 5=battery 6=booster 7=reducer
OID_OUTPUT_FREQUENCY = "1.3.6.1.2.1.33.1.4.2.0"          # 0.1 Hz (system)

def output_voltage_oid(line: int) -> str: return f"1.3.6.1.2.1.33.1.4.4.1.2.{line}"  # V RMS
def output_current_oid(line: int) -> str: return f"1.3.6.1.2.1.33.1.4.4.1.3.{line}"  # 0.1 A RMS
def output_power_oid(line: int)   -> str: return f"1.3.6.1.2.1.33.1.4.4.1.4.{line}"  # W
def output_load_oid(line: int)    -> str: return f"1.3.6.1.2.1.33.1.4.4.1.5.{line}"  # %

# Alarms
OID_ALARMS_PRESENT = "1.3.6.1.2.1.33.1.6.1.0"            # count of active alarms

# upsAlarmTable (1.3.6.1.2.1.33.1.6.2). Each active alarm is a row; the
# upsAlarmDescr column holds an OID pointing into the well-known-alarm branch
# below. Row indices are dynamic, so this column is *walked* each cycle rather
# than fetched by a fixed OID.
OID_ALARM_DESCR_COLUMN = "1.3.6.1.2.1.33.1.6.2.1.2"      # upsAlarmDescr

# upsWellKnownAlarms (1.3.6.1.2.1.33.1.6.3) — the OIDs upsAlarmDescr points at.
OID_ALARM_INPUT_BAD = "1.3.6.1.2.1.33.1.6.3.6"
OID_ALARM_BYPASS_BAD = "1.3.6.1.2.1.33.1.6.3.10"

# Alarm OIDs never treated as an active alarm, on any transport. Bypass bad is
# always set on a UPS run without a bypass feed (de-energised bypass line), so
# it would otherwise be a permanent false alarm.
IGNORED_ALARM_OIDS = frozenset({OID_ALARM_BYPASS_BAD})

# Map each well-known-alarm OID to the same human label the CS121 web UI uses.
WELL_KNOWN_ALARMS = {
    "1.3.6.1.2.1.33.1.6.3.1": "Battery bad",
    "1.3.6.1.2.1.33.1.6.3.2": "On battery",
    "1.3.6.1.2.1.33.1.6.3.3": "Low battery",
    "1.3.6.1.2.1.33.1.6.3.4": "Depleted battery",
    "1.3.6.1.2.1.33.1.6.3.5": "Temperature bad",
    OID_ALARM_INPUT_BAD:       "Input bad",
    "1.3.6.1.2.1.33.1.6.3.7": "Output bad",
    "1.3.6.1.2.1.33.1.6.3.8": "Output overload",
    "1.3.6.1.2.1.33.1.6.3.9": "On bypass",
    "1.3.6.1.2.1.33.1.6.3.10": "Bypass bad",
    "1.3.6.1.2.1.33.1.6.3.11": "Output off as requested",
    "1.3.6.1.2.1.33.1.6.3.12": "UPS off as requested",
    "1.3.6.1.2.1.33.1.6.3.13": "Charger failed",
    "1.3.6.1.2.1.33.1.6.3.14": "UPS output off",
    "1.3.6.1.2.1.33.1.6.3.15": "UPS system off",
    "1.3.6.1.2.1.33.1.6.3.16": "Fan failure",
    "1.3.6.1.2.1.33.1.6.3.17": "Fuse failure",
    "1.3.6.1.2.1.33.1.6.3.18": "General fault",
    "1.3.6.1.2.1.33.1.6.3.19": "Diagnostic test failed",
    "1.3.6.1.2.1.33.1.6.3.20": "Communications lost",
    "1.3.6.1.2.1.33.1.6.3.21": "Awaiting power",
    "1.3.6.1.2.1.33.1.6.3.22": "Shutdown pending",
    "1.3.6.1.2.1.33.1.6.3.23": "Shutdown imminent",
    "1.3.6.1.2.1.33.1.6.3.24": "Test in progress",
}

# Synthetic coordinator-data keys (NOT OIDs) for values derived from the walk.
# Kept distinct from the dotted OID keyspace so entities can read them directly.
KEY_ACTIVE_ALARM_OIDS = "active_alarm_oids"      # list[str] of well-known OIDs
KEY_ACTIVE_ALARM_LABELS = "active_alarm_labels"  # list[str] of human labels

# Well-known alarms surfaced as individual problem binary sensors, as
# (well-known-alarm OID, stable entity key, friendly name). The three battery
# alarms (On battery / Low battery / Depleted battery) are intentionally left
# out — they already have dedicated sensors — but still appear in the
# 'Active alarms' text sensor and its `active_alarms` attribute.
ALARM_BINARY_SENSORS = (
    ("1.3.6.1.2.1.33.1.6.3.1",  "alarm_battery_bad",       "Battery bad"),
    ("1.3.6.1.2.1.33.1.6.3.5",  "alarm_temperature_bad",   "Temperature bad"),
    (OID_ALARM_INPUT_BAD,        "input_bad",               "Input bad"),
    ("1.3.6.1.2.1.33.1.6.3.7",  "alarm_output_bad",        "Output bad"),
    ("1.3.6.1.2.1.33.1.6.3.8",  "alarm_output_overload",   "Output overload"),
    ("1.3.6.1.2.1.33.1.6.3.9",  "alarm_on_bypass",         "On bypass"),
    # Bypass bad (3.6.3.10) intentionally not exposed — see MODBUS_ALARM_REGS.
    ("1.3.6.1.2.1.33.1.6.3.11", "alarm_output_off",        "Output off as requested"),
    ("1.3.6.1.2.1.33.1.6.3.12", "alarm_ups_off",           "UPS off as requested"),
    ("1.3.6.1.2.1.33.1.6.3.13", "alarm_charger_failed",    "Charger failed"),
    ("1.3.6.1.2.1.33.1.6.3.14", "alarm_ups_output_off",    "UPS output off"),
    ("1.3.6.1.2.1.33.1.6.3.15", "alarm_ups_system_off",    "UPS system off"),
    ("1.3.6.1.2.1.33.1.6.3.16", "alarm_fan_failure",       "Fan failure"),
    ("1.3.6.1.2.1.33.1.6.3.17", "alarm_fuse_failure",      "Fuse failure"),
    ("1.3.6.1.2.1.33.1.6.3.18", "alarm_general_fault",     "General fault"),
    ("1.3.6.1.2.1.33.1.6.3.19", "alarm_diagnostic_failed", "Diagnostic test failed"),
    ("1.3.6.1.2.1.33.1.6.3.20", "alarm_comms_lost",        "Communications lost"),
    ("1.3.6.1.2.1.33.1.6.3.21", "alarm_awaiting_power",    "Awaiting power"),
    ("1.3.6.1.2.1.33.1.6.3.22", "alarm_shutdown_pending",  "Shutdown pending"),
    ("1.3.6.1.2.1.33.1.6.3.23", "alarm_shutdown_imminent", "Shutdown imminent"),
    ("1.3.6.1.2.1.33.1.6.3.24", "alarm_test_in_progress",  "Test in progress"),
)

# Enum maps (raw int -> human label)
BATTERY_STATUS_MAP = {
    1: "unknown",
    2: "normal",
    3: "low",
    4: "depleted",
}

OUTPUT_SOURCE_MAP = {
    1: "other",
    2: "none",
    3: "normal",
    4: "bypass",
    5: "battery",
    6: "booster",
    7: "reducer",
}

# Human-readable phrasing for the composed "UPS status" sensor (mirrors the
# leading clause of the CS121 web UI's status line, e.g. "UPS is ON").
OUTPUT_SOURCE_STATUS = {
    1: "Unknown",
    2: "Output off",
    3: "UPS is ON",
    4: "On bypass",
    5: "On battery",
    6: "UPS is ON (boosting)",
    7: "UPS is ON (reducing)",
}

# Scalar OIDs polled every cycle. Per-phase OIDs are appended dynamically by the
# coordinator after topology detection (upsInputNumLines / upsOutputNumLines).
SCALAR_POLLED_OIDS = (
    OID_BATTERY_STATUS,
    OID_SECONDS_ON_BATTERY,
    OID_MINUTES_REMAINING,
    OID_CHARGE_REMAINING,
    OID_BATTERY_VOLTAGE,
    OID_BATTERY_CURRENT,
    OID_BATTERY_TEMPERATURE,
    OID_OUTPUT_SOURCE,
    OID_OUTPUT_FREQUENCY,
    OID_ALARMS_PRESENT,
    OID_INPUT_LINE_BADS,
)

# Read once at setup, cached on the coordinator for device_info.
IDENT_OIDS = (
    OID_IDENT_MANUFACTURER,
    OID_IDENT_MODEL,
    OID_IDENT_SW_VERSION,
    OID_IDENT_NAME,
)

# ---------------------------------------------------------------------------
# Modbus transport (Generex CS121 holding/input registers, function 3/4).
#
# The CS121 also speaks Modbus TCP, and unlike its SNMP agent it DOES expose
# the UPS alarm flags (e.g. "Input bad") that the standard RFC 1628 alarm table
# leaves empty on this firmware. To keep every entity's value identical no
# matter which transport is selected, the Modbus coordinator maps each register
# back onto the SAME OID keyspace the SNMP path uses (scaling raw registers to
# the SNMP unit convention), so sensors/binary_sensors need no transport logic.
#
# Register map per the Legrand CS121 Modbus spec, ARCHIMOD/Trimod family,
# firmware >= 5.30.x: https://ups.legrand.com/media/software/cs121_modbus.pdf
# ---------------------------------------------------------------------------

MODBUS_REG_STATUS = 109   # UPS Status bitfield (see MODBUS_STATUS_BITS)

# Telemetry registers -> (target SNMP OID key, multiplier, signed). The stored
# value is (signed-decoded raw * multiplier) so the entity's existing SNMP scale
# yields the same number (e.g. battery V: reg 271 *10 -> 2710 -> /10 = 271.0).
MODBUS_TELEMETRY = (
    (103, OID_CHARGE_REMAINING, 1, False),    # battery charge %
    (108, OID_MINUTES_REMAINING, 1, False),   # autonomy minutes
    (110, OID_BATTERY_VOLTAGE, 10, True),     # battery V (whole V -> 0.1 V units)
    (107, OID_BATTERY_TEMPERATURE, 1, True),  # UPS/battery temperature °C
    (104, input_voltage_oid(1), 1, True),     # input V L1/L2/L3
    (105, input_voltage_oid(2), 1, True),
    (106, input_voltage_oid(3), 1, True),
    (111, input_frequency_oid(1), 10, False), # input freq Hz -> 0.1 Hz units
    (140, output_voltage_oid(1), 1, False),   # output V L1/L2/L3
    (141, output_voltage_oid(2), 1, False),
    (142, output_voltage_oid(3), 1, False),
    (143, output_current_oid(1), 1, False),   # output current already in 0.1 A
    (144, output_current_oid(2), 1, False),
    (145, output_current_oid(3), 1, False),
    (100, output_load_oid(1), 1, False),      # output load %
    (101, output_load_oid(2), 1, False),
    (102, output_load_oid(3), 1, False),
    (114, OID_INPUT_LINE_BADS, 1, False),     # powerfail counter == upsInputLineBads
)

# OID keys the Modbus transport can actually fill (telemetry above + the enums
# derived from the status/alarm registers). Sensors keyed off anything NOT in
# here — input current/power, output power, output frequency, time-on-battery,
# battery current — have no Modbus register and would read 'unknown', so they
# are simply not created on the Modbus transport.
MODBUS_PROVIDED_OIDS = frozenset(
    {oid for _reg, oid, _mult, _signed in MODBUS_TELEMETRY}
    | {OID_OUTPUT_SOURCE, OID_BATTERY_STATUS, OID_ALARMS_PRESENT}
)

# Alarm flag registers (1=active) -> well-known-alarm OID, so the existing
# alarm binary sensors / active-alarm list light up unchanged. Register 139
# (manual bypass switch) has no RFC 1628 equivalent and is handled by label.
MODBUS_ALARM_REGS = {
    115: "1.3.6.1.2.1.33.1.6.3.1",   # Battery bad
    116: "1.3.6.1.2.1.33.1.6.3.2",   # On battery
    117: "1.3.6.1.2.1.33.1.6.3.3",   # Battery low
    119: "1.3.6.1.2.1.33.1.6.3.5",   # Temperature bad
    120: OID_ALARM_INPUT_BAD,        # Input bad
    121: "1.3.6.1.2.1.33.1.6.3.7",   # Output bad
    122: "1.3.6.1.2.1.33.1.6.3.8",   # Output overload
    123: "1.3.6.1.2.1.33.1.6.3.9",   # On bypass
    # 124 (Bypass bad) intentionally omitted — on UPS configured without a
    # bypass feed the bypass line is permanently de-energised, so this flag is
    # always set and is not a real fault. See also ALARM_BINARY_SENSORS.
    125: "1.3.6.1.2.1.33.1.6.3.11",  # Output off as requested
    126: "1.3.6.1.2.1.33.1.6.3.12",  # UPS off as requested
    127: "1.3.6.1.2.1.33.1.6.3.13",  # Charger failed
    128: "1.3.6.1.2.1.33.1.6.3.14",  # UPS output off
    129: "1.3.6.1.2.1.33.1.6.3.15",  # UPS system off
    132: "1.3.6.1.2.1.33.1.6.3.18",  # General fault
    133: "1.3.6.1.2.1.33.1.6.3.19",  # Diagnostic test failed
    134: "1.3.6.1.2.1.33.1.6.3.20",  # Communications lost
    136: "1.3.6.1.2.1.33.1.6.3.22",  # Shutdown pending
    137: "1.3.6.1.2.1.33.1.6.3.23",  # Shutdown imminent
    138: "1.3.6.1.2.1.33.1.6.3.24",  # Test in progress
}
# Registers with no RFC 1628 alarm OID — surfaced only in the active-alarm list.
MODBUS_ALARM_EXTRA = {
    139: "Manual bypass switch closed",
}

# Convenience alarm registers used to derive battery status.
MODBUS_REG_BATTERY_LOW = 117

# upsBypassNumLines is not needed for Modbus; topology comes from the spec (the
# ARCHIMOD HE map always exposes L1-L3 registers, absent ones simply read 0).

# Register-109 status bits -> upsOutputSource enum, so the output_source sensor
# and on_battery/mains_present binary sensors work unchanged.
MODBUS_STATUS_BYPASS = 0x0001
MODBUS_STATUS_OUTPUT_ACT = 0x0004
MODBUS_STATUS_BACKUP = 0x0008
