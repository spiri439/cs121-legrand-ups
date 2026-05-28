"""Base entity for the CS121 Legrand UPS integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OID_IDENT_MANUFACTURER,
    OID_IDENT_MODEL,
    OID_IDENT_NAME,
    OID_IDENT_SW_VERSION,
)
from .coordinator import CS121Coordinator


class CS121Entity(CoordinatorEntity[CS121Coordinator]):
    """Shared device info / coordinator wiring."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CS121Coordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"

        ident = coordinator.ident or {}
        manufacturer = ident.get(OID_IDENT_MANUFACTURER) or "Legrand"
        model = ident.get(OID_IDENT_MODEL) or "UPS via CS121"
        name = ident.get(OID_IDENT_NAME) or "Legrand UPS"
        sw_version = ident.get(OID_IDENT_SW_VERSION) or None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=name,
            manufacturer="spiri439",
            model=f"{manufacturer} {model}".strip(),
            sw_version=sw_version,
        )
