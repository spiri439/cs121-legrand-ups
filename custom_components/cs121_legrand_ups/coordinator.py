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
    OID_INPUT_NUM_LINES,
    OID_OUTPUT_NUM_LINES,
    SCALAR_POLLED_OIDS,
    SNMP_TIMEOUT,
    input_current_oid,
    input_frequency_oid,
    input_power_oid,
    input_voltage_oid,
    output_current_oid,
    output_load_oid,
    output_power_oid,
    output_voltage_oid,
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
        # Topology — filled in by async_fetch_topology before first poll.
        self.lines_input: int = 1
        self.lines_output: int = 1
        self._polled_oids: tuple[str, ...] = ()

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

    async def async_fetch_topology(self) -> None:
        """Discover input/output line counts and freeze the per-cycle OID list."""
        if self._polled_oids:
            return
        try:
            data = await self._multiget((OID_INPUT_NUM_LINES, OID_OUTPUT_NUM_LINES))
            self.lines_input = max(1, min(3, int(data.get(OID_INPUT_NUM_LINES) or 1)))
            self.lines_output = max(1, min(3, int(data.get(OID_OUTPUT_NUM_LINES) or 1)))
        except (UpdateFailed, TypeError, ValueError):
            # Fall back to single-phase if the device doesn't report line counts.
            self.lines_input = 1
            self.lines_output = 1
        self._polled_oids = self._build_polled_oids()

    def _build_polled_oids(self) -> tuple[str, ...]:
        oids: list[str] = list(SCALAR_POLLED_OIDS)
        for line in range(1, self.lines_input + 1):
            oids += [
                input_frequency_oid(line),
                input_voltage_oid(line),
                input_current_oid(line),
                input_power_oid(line),
            ]
        for line in range(1, self.lines_output + 1):
            oids += [
                output_voltage_oid(line),
                output_current_oid(line),
                output_power_oid(line),
                output_load_oid(line),
            ]
        return tuple(oids)

    async def _async_update_data(self) -> dict:
        # Identity and topology fetches are best-effort and only run until they succeed.
        if not self.ident:
            await self.async_fetch_ident()
        if not self._polled_oids:
            await self.async_fetch_topology()
        return await self._multiget(self._polled_oids)
