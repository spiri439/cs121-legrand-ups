"""Binary sensor platform for the CS121 Legrand UPS integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALARM_BINARY_SENSORS,
    DOMAIN,
    KEY_ACTIVE_ALARM_LABELS,
    KEY_ACTIVE_ALARM_OIDS,
    OID_ALARMS_PRESENT,
    OID_BATTERY_STATUS,
    OID_OUTPUT_SOURCE,
)
from .coordinator import CS121Coordinator
from .entity import CS121Entity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CS121Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        OnBatterySensor(coordinator, entry.entry_id),
        MainsPresentSensor(coordinator, entry.entry_id),
        BatteryLowSensor(coordinator, entry.entry_id),
        AlarmsPresentSensor(coordinator, entry.entry_id),
        ConnectionSensor(coordinator, entry.entry_id),
    ]
    # One PROBLEM sensor per well-known RFC 1628 alarm (Input bad, Output
    # overload, Temperature bad, …), driven entirely by the const table.
    entities += [
        AlarmBinarySensor(coordinator, entry.entry_id, oid, key, name)
        for oid, key, name in ALARM_BINARY_SENSORS
    ]
    async_add_entities(entities)


def _get(coordinator: CS121Coordinator, oid: str) -> int | None:
    raw = (coordinator.data or {}).get(oid)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class OnBatterySensor(CS121Entity, BinarySensorEntity):
    """True when the UPS is currently running from its battery (outputSource=5)."""

    _attr_name = "On battery"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING  # battery active = relevant
    _attr_icon = "mdi:battery-alert"

    def __init__(self, coordinator: CS121Coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "on_battery")

    @property
    def is_on(self) -> bool | None:
        v = _get(self.coordinator, OID_OUTPUT_SOURCE)
        return None if v is None else v == 5


class MainsPresentSensor(CS121Entity, BinarySensorEntity):
    """True when output is sourced from mains (outputSource=3)."""

    _attr_name = "Mains present"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator: CS121Coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "mains_present")

    @property
    def is_on(self) -> bool | None:
        v = _get(self.coordinator, OID_OUTPUT_SOURCE)
        return None if v is None else v == 3


class BatteryLowSensor(CS121Entity, BinarySensorEntity):
    """True when batteryStatus reports low or depleted (3 or 4)."""

    _attr_name = "Battery low"
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: CS121Coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "battery_low")

    @property
    def is_on(self) -> bool | None:
        v = _get(self.coordinator, OID_BATTERY_STATUS)
        return None if v is None else v in (3, 4)


class AlarmsPresentSensor(CS121Entity, BinarySensorEntity):
    """True when the UPS reports one or more active alarms."""

    _attr_name = "Alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: CS121Coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "alarms_present")

    @property
    def is_on(self) -> bool | None:
        v = _get(self.coordinator, OID_ALARMS_PRESENT)
        return None if v is None else v > 0

    @property
    def extra_state_attributes(self) -> dict[str, list[str]] | None:
        """Expose the decoded names of the active alarms (e.g. ['Input bad'])."""
        labels = (self.coordinator.data or {}).get(KEY_ACTIVE_ALARM_LABELS)
        if labels is None:
            return None
        return {"active_alarms": labels}


class AlarmBinarySensor(CS121Entity, BinarySensorEntity):
    """A single well-known RFC 1628 alarm — `on` while that alarm is active in
    the UPS's alarm table, the same condition the CS121 web UI shows."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: CS121Coordinator,
        entry_id: str,
        alarm_oid: str,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, entry_id, key)
        self._alarm_oid = alarm_oid
        self._attr_name = name

    @property
    def is_on(self) -> bool | None:
        oids = (self.coordinator.data or {}).get(KEY_ACTIVE_ALARM_OIDS)
        if oids is None:  # alarm walk hasn't succeeded yet — state unknown
            return None
        return self._alarm_oid in oids


class ConnectionSensor(CS121Entity, BinarySensorEntity):
    """Connectivity sensor. Stays *available* even when polling fails, so it
    can report 'off' as a reliable automation trigger."""

    _attr_name = "Connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CS121Coordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id, "connection")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
