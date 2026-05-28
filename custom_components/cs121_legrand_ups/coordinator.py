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
    input_current_oid,
    input_frequency_oid,
    input_power_oid,
    input_voltage_oid,
    output_current_oid,
    output_load_oid,
    output_power_oid,
    output_voltage_oid,
)

# Per-attempt timeouts. puresnmp does its own UDP retries; we then layer an
# outer retry loop on top to ride out the occasional dropped packet without
# every entity going 'unavailable' for a full poll interval.
SNMP_PER_ATTEMPT_TIMEOUT = 2.0   # seconds — puresnmp's per-try timeout
SNMP_INNER_RETRIES = 1           # puresnmp's own retry count (1 = 2 tries)
SNMP_OUTER_ATTEMPTS = 3          # additional retry passes around multiget
SNMP_OUTER_RETRY_DELAY = 0.5     # seconds between outer attempts

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
        # Short per-attempt timeout + small internal retry count keeps the worst
        # case under ~5s before our own outer retry loop kicks in.
        self._client = PyWrapper(
            Client(
                host,
                V2C(community),
                port=port,
                timeout=SNMP_PER_ATTEMPT_TIMEOUT,
                retries=SNMP_INNER_RETRIES,
            )
        )
        self.ident: dict[str, str | None] = {}
        # Topology — filled in by async_fetch_topology before first poll.
        self.lines_input: int = 1
        self.lines_output: int = 1
        # Polled OIDs are kept in chunks (scalar / per-phase input / per-phase
        # output) so a single bad OID only kills one chunk, not the whole poll.
        self._polled_oid_groups: tuple[tuple[str, ...], ...] = ()

    async def _multiget(self, oids: tuple[str, ...]) -> dict[str, object | None]:
        """Fetch many OIDs with retries around the multiget so that a single
        dropped UDP packet doesn't flip every entity to 'unavailable' for an
        entire poll cycle."""
        last_err: Exception | None = None
        for attempt in range(1, SNMP_OUTER_ATTEMPTS + 1):
            try:
                values = await self._client.multiget(list(oids))
                if attempt > 1:
                    _LOGGER.debug(
                        "SNMP multiget recovered on attempt %d/%d",
                        attempt, SNMP_OUTER_ATTEMPTS,
                    )
                return {oid: _decode(v) for oid, v in zip(oids, values)}
            except (SnmpError, asyncio.TimeoutError, OSError) as err:
                last_err = err
                _LOGGER.debug(
                    "SNMP multiget attempt %d/%d to %s:%s failed: %s",
                    attempt, SNMP_OUTER_ATTEMPTS, self._host, self._port, err,
                )
                if attempt < SNMP_OUTER_ATTEMPTS:
                    await asyncio.sleep(SNMP_OUTER_RETRY_DELAY)
        raise UpdateFailed(
            f"SNMP error to {self._host}:{self._port} after "
            f"{SNMP_OUTER_ATTEMPTS} attempts: {last_err}"
        )

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
        """Discover input/output line counts and freeze the per-cycle OID groups."""
        if self._polled_oid_groups:
            return
        try:
            data = await self._multiget((OID_INPUT_NUM_LINES, OID_OUTPUT_NUM_LINES))
            self.lines_input = max(1, min(3, int(data.get(OID_INPUT_NUM_LINES) or 1)))
            self.lines_output = max(1, min(3, int(data.get(OID_OUTPUT_NUM_LINES) or 1)))
        except (UpdateFailed, TypeError, ValueError):
            # Fall back to single-phase if the device doesn't report line counts.
            self.lines_input = 1
            self.lines_output = 1
        self._polled_oid_groups = self._build_polled_oid_groups()

    def _build_polled_oid_groups(self) -> tuple[tuple[str, ...], ...]:
        scalar: list[str] = list(SCALAR_POLLED_OIDS)
        inputs: list[str] = []
        for line in range(1, self.lines_input + 1):
            inputs += [
                input_frequency_oid(line),
                input_voltage_oid(line),
                input_current_oid(line),
                input_power_oid(line),
            ]
        outputs: list[str] = []
        for line in range(1, self.lines_output + 1):
            outputs += [
                output_voltage_oid(line),
                output_current_oid(line),
                output_power_oid(line),
                output_load_oid(line),
            ]
        return (tuple(scalar), tuple(inputs), tuple(outputs))

    async def _async_update_data(self) -> dict:
        # Identity and topology fetches are best-effort and only run until they succeed.
        if not self.ident:
            await self.async_fetch_ident()
        if not self._polled_oid_groups:
            await self.async_fetch_topology()

        # Poll the chunks; tolerate a partial-success update so transient
        # per-chunk failures only blank the affected entities, not all of them.
        results: dict[str, object | None] = {}
        errors: list[str] = []
        for group in self._polled_oid_groups:
            if not group:
                continue
            try:
                results.update(await self._multiget(group))
            except UpdateFailed as err:
                errors.append(str(err))

        if not results:
            raise UpdateFailed("; ".join(errors) or "no SNMP data")
        if errors:
            _LOGGER.warning(
                "Partial CS121 update: %d/%d chunks failed (%s); %d values returned.",
                len(errors), len(self._polled_oid_groups), "; ".join(errors), len(results),
            )
        return results
