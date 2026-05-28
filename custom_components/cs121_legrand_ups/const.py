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

# Defaults
DEFAULT_NAME = "Legrand UPS"
DEFAULT_PORT = 161
DEFAULT_COMMUNITY = "public"
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
OID_ALARMS_PRESENT = "1.3.6.1.2.1.33.1.6.1.0"            # count

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
)

# Read once at setup, cached on the coordinator for device_info.
IDENT_OIDS = (
    OID_IDENT_MANUFACTURER,
    OID_IDENT_MODEL,
    OID_IDENT_SW_VERSION,
    OID_IDENT_NAME,
)
