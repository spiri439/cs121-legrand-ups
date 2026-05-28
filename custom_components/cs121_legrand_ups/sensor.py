"""Sensor platform for the CS121 Legrand UPS integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BATTERY_STATUS_MAP,
    DOMAIN,
    OID_ALARMS_PRESENT,
    OID_BATTERY_CURRENT,
    OID_BATTERY_STATUS,
    OID_BATTERY_TEMPERATURE,
    OID_BATTERY_VOLTAGE,
    OID_CHARGE_REMAINING,
    OID_MINUTES_REMAINING,
    OID_OUTPUT_FREQUENCY,
    OID_OUTPUT_SOURCE,
    OID_SECONDS_ON_BATTERY,
    OUTPUT_SOURCE_MAP,
    input_current_oid,
    input_frequency_oid,
    input_power_oid,
    input_voltage_oid,
    output_current_oid,
    output_load_oid,
    output_power_oid,
    output_voltage_oid,
)
from .coordinator import CS121Coordinator
from .entity import CS121Entity


@dataclass(frozen=True, kw_only=True)
class CS121SensorEntityDescription(SensorEntityDescription):
    """Sensor description: which OID to read, optional divisor, optional enum map."""

    oid: str
    scale: float = 1.0
    enum_map: dict[int, str] | None = None


# Scalar sensors that exist on every UPS regardless of phase count.
SCALAR_SENSORS: tuple[CS121SensorEntityDescription, ...] = (
    # Battery / UPS body
    CS121SensorEntityDescription(
        key="battery_charge", name="Battery charge", oid=OID_CHARGE_REMAINING,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        # upsEstimatedMinutesRemaining — the device's autonomy estimate.
        key="battery_runtime", name="Autonomy time", oid=OID_MINUTES_REMAINING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-sand",
    ),
    CS121SensorEntityDescription(
        key="time_on_battery", name="Time on battery", oid=OID_SECONDS_ON_BATTERY,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline", entity_category=EntityCategory.DIAGNOSTIC,
    ),
    CS121SensorEntityDescription(
        key="battery_voltage", name="Battery voltage", oid=OID_BATTERY_VOLTAGE, scale=10,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="battery_current", name="Battery current", oid=OID_BATTERY_CURRENT, scale=10,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    CS121SensorEntityDescription(
        # upsBatteryTemperature is the only temperature this CS121 firmware exposes;
        # on Legrand ARCHIMOD it's effectively the UPS internal temp.
        key="battery_temperature", name="UPS temperature", oid=OID_BATTERY_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="battery_status", name="Battery status", oid=OID_BATTERY_STATUS,
        device_class=SensorDeviceClass.ENUM, enum_map=BATTERY_STATUS_MAP,
        options=list(BATTERY_STATUS_MAP.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Output (system-wide)
    CS121SensorEntityDescription(
        key="output_source", name="Output source", oid=OID_OUTPUT_SOURCE,
        device_class=SensorDeviceClass.ENUM, enum_map=OUTPUT_SOURCE_MAP,
        options=list(OUTPUT_SOURCE_MAP.values()),
    ),
    CS121SensorEntityDescription(
        key="output_frequency", name="Output frequency", oid=OID_OUTPUT_FREQUENCY, scale=10,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY, state_class=SensorStateClass.MEASUREMENT,
    ),
    # Alarms
    CS121SensorEntityDescription(
        key="alarms_present", name="Active alarms", oid=OID_ALARMS_PRESENT,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _suffix(line: int) -> tuple[str, str]:
    """Return ('', '') for L1 (back-compat with v1.0.0 keys) or ('_lN', ' LN') for L2+."""
    if line == 1:
        return "", ""
    return f"_l{line}", f" L{line}"


def _input_phase_descs(line: int) -> list[CS121SensorEntityDescription]:
    key_s, name_s = _suffix(line)
    descs = [
        CS121SensorEntityDescription(
            key=f"input_voltage{key_s}", name=f"Input voltage{name_s}",
            oid=input_voltage_oid(line),
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT,
        ),
        CS121SensorEntityDescription(
            key=f"input_current{key_s}", name=f"Input current{name_s}",
            oid=input_current_oid(line), scale=10,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT,
        ),
        CS121SensorEntityDescription(
            key=f"input_power{key_s}", name=f"Input power{name_s}",
            oid=input_power_oid(line),
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT,
        ),
    ]
    if line == 1:
        # Treat input frequency as system-wide and only expose it once (L1).
        descs.append(
            CS121SensorEntityDescription(
                key="input_frequency", name="Input frequency",
                oid=input_frequency_oid(1), scale=10,
                native_unit_of_measurement=UnitOfFrequency.HERTZ,
                device_class=SensorDeviceClass.FREQUENCY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )
    return descs


def _output_phase_descs(line: int) -> list[CS121SensorEntityDescription]:
    key_s, name_s = _suffix(line)
    return [
        CS121SensorEntityDescription(
            key=f"output_voltage{key_s}", name=f"Output voltage{name_s}",
            oid=output_voltage_oid(line),
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT,
        ),
        CS121SensorEntityDescription(
            key=f"output_current{key_s}", name=f"Output current{name_s}",
            oid=output_current_oid(line), scale=10,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT,
        ),
        CS121SensorEntityDescription(
            key=f"output_power{key_s}", name=f"Output power{name_s}",
            oid=output_power_oid(line),
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT,
        ),
        CS121SensorEntityDescription(
            key=f"output_load{key_s}", name=f"Output load{name_s}",
            oid=output_load_oid(line),
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT, icon="mdi:gauge",
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up CS121 sensors. Per-phase entities are created based on the UPS-MIB
    line counts the coordinator discovered at first refresh."""
    coordinator: CS121Coordinator = hass.data[DOMAIN][entry.entry_id]

    descriptions: list[CS121SensorEntityDescription] = list(SCALAR_SENSORS)
    for line in range(1, coordinator.lines_input + 1):
        descriptions.extend(_input_phase_descs(line))
    for line in range(1, coordinator.lines_output + 1):
        descriptions.extend(_output_phase_descs(line))

    async_add_entities(
        CS121Sensor(coordinator, entry.entry_id, desc) for desc in descriptions
    )


class CS121Sensor(CS121Entity, SensorEntity):
    """A single OID-backed sensor, optionally scaled or enum-mapped."""

    entity_description: CS121SensorEntityDescription

    def __init__(
        self,
        coordinator: CS121Coordinator,
        entry_id: str,
        description: CS121SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry_id, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        raw = (self.coordinator.data or {}).get(self.entity_description.oid)
        if raw is None:
            return None
        if self.entity_description.enum_map is not None:
            try:
                return self.entity_description.enum_map.get(int(raw))
            except (TypeError, ValueError):
                return None
        if self.entity_description.scale != 1:
            try:
                return round(float(raw) / self.entity_description.scale, 1)
            except (TypeError, ValueError):
                return None
        return raw
