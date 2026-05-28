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
    OID_INPUT_CURRENT,
    OID_INPUT_FREQUENCY,
    OID_INPUT_POWER,
    OID_INPUT_VOLTAGE,
    OID_MINUTES_REMAINING,
    OID_OUTPUT_CURRENT,
    OID_OUTPUT_FREQUENCY,
    OID_OUTPUT_LOAD,
    OID_OUTPUT_POWER,
    OID_OUTPUT_SOURCE,
    OID_OUTPUT_VOLTAGE,
    OID_SECONDS_ON_BATTERY,
    OUTPUT_SOURCE_MAP,
)
from .coordinator import CS121Coordinator
from .entity import CS121Entity


@dataclass(frozen=True, kw_only=True)
class CS121SensorEntityDescription(SensorEntityDescription):
    """Sensor description: which OID to read, optional divisor, optional enum map."""

    oid: str
    scale: float = 1.0
    enum_map: dict[int, str] | None = None


SENSORS: tuple[CS121SensorEntityDescription, ...] = (
    # Battery
    CS121SensorEntityDescription(
        key="battery_charge", name="Battery charge", oid=OID_CHARGE_REMAINING,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="battery_runtime", name="Battery runtime remaining", oid=OID_MINUTES_REMAINING,
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
        key="battery_temperature", name="Battery temperature", oid=OID_BATTERY_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="battery_status", name="Battery status", oid=OID_BATTERY_STATUS,
        device_class=SensorDeviceClass.ENUM, enum_map=BATTERY_STATUS_MAP,
        options=list(BATTERY_STATUS_MAP.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Input
    CS121SensorEntityDescription(
        key="input_voltage", name="Input voltage", oid=OID_INPUT_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="input_frequency", name="Input frequency", oid=OID_INPUT_FREQUENCY, scale=10,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="input_current", name="Input current", oid=OID_INPUT_CURRENT, scale=10,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="input_power", name="Input power", oid=OID_INPUT_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT,
    ),
    # Output
    CS121SensorEntityDescription(
        key="output_source", name="Output source", oid=OID_OUTPUT_SOURCE,
        device_class=SensorDeviceClass.ENUM, enum_map=OUTPUT_SOURCE_MAP,
        options=list(OUTPUT_SOURCE_MAP.values()),
    ),
    CS121SensorEntityDescription(
        key="output_voltage", name="Output voltage", oid=OID_OUTPUT_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="output_frequency", name="Output frequency", oid=OID_OUTPUT_FREQUENCY, scale=10,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="output_current", name="Output current", oid=OID_OUTPUT_CURRENT, scale=10,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="output_power", name="Output power", oid=OID_OUTPUT_POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT,
    ),
    CS121SensorEntityDescription(
        key="output_load", name="Output load", oid=OID_OUTPUT_LOAD,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:gauge",
    ),
    # Alarms
    CS121SensorEntityDescription(
        key="alarms_present", name="Active alarms", oid=OID_ALARMS_PRESENT,
        state_class=SensorStateClass.MEASUREMENT, icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up CS121 sensors from a config entry."""
    coordinator: CS121Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CS121Sensor(coordinator, entry.entry_id, description) for description in SENSORS
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
