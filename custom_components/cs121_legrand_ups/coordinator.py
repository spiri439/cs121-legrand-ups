"""Data update coordinator for the CS121 Legrand UPS integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from puresnmp import Client, V2C, PyWrapper
from puresnmp.exc import SnmpError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    IDENT_OIDS,
    POLLED_OIDS,
    SNMP_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def _decode(value):
    """Convert puresnmp return values into JSON-ish Python types."""
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8").strip("\x00 \t\r\n") or None
        except UnicodeDecodeError:
            return value.hex()
    return value


class CS121Coordinator(DataUpdateCoordinator[dict]):
    """Polls the CS121 over SNMP v2c and exposes the values to entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        community: str,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._host = host
        self._port = port
        # PyWrapper exposes a friendlier multiget API on top of the raw Client.
        self._client = PyWrapper(Client(host, V2C(community), port=port))
        self.ident: dict[str, str | None] = {}

    async def _multiget(self, oids: tuple[str, ...]) -> dict[str, object | None]:
        """Fetch many OIDs in one request; per-OID failures map to None."""
        try:
            values = await asyncio.wait_for(
                self._client.multiget(list(oids)), timeout=SNMP_TIMEOUT
            )
        except (SnmpError, asyncio.TimeoutError, OSError) as err:
            raise UpdateFailed(f"SNMP error to {self._host}:{self._port}: {err}") from err
        return {oid: _decode(v) for oid, v in zip(oids, values)}

    async def async_fetch_ident(self) -> None:
        """Read identification strings once (manufacturer, model, …) for device_info."""
        if self.ident:
            return
        try:
            data = await self._multiget(IDENT_OIDS)
        except UpdateFailed:
            # Not fatal — device_info can be filled in later if it works.
            return
        self.ident = {oid: data.get(oid) for oid in IDENT_OIDS}

    async def _async_update_data(self) -> dict:
        # Identity fetch is best-effort and only runs until it succeeds once.
        if not self.ident:
            await self.async_fetch_ident()
        return await self._multiget(POLLED_OIDS)
