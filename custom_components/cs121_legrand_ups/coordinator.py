"""Data update coordinator for the CS121 Legrand UPS integration."""
from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import timedelta

from puresnmp import Client, V2C, PyWrapper
from puresnmp.exc import SnmpError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    IDENT_OIDS,
    KEY_ACTIVE_ALARM_LABELS,
    KEY_ACTIVE_ALARM_OIDS,
    MODBUS_ALARM_EXTRA,
    MODBUS_ALARM_REGS,
    MODBUS_REG_BATTERY_LOW,
    MODBUS_REG_STATUS,
    MODBUS_STATUS_BACKUP,
    MODBUS_STATUS_BYPASS,
    MODBUS_STATUS_OUTPUT_ACT,
    MODBUS_TELEMETRY,
    OID_ALARM_DESCR_COLUMN,
    OID_ALARMS_PRESENT,
    OID_BATTERY_STATUS,
    OID_INPUT_NUM_LINES,
    OID_OUTPUT_NUM_LINES,
    OID_OUTPUT_SOURCE,
    PROTOCOL_MODBUS,
    SCALAR_POLLED_OIDS,
    WELL_KNOWN_ALARMS,
    input_current_oid,
    input_frequency_oid,
    input_power_oid,
    input_voltage_oid,
    output_current_oid,
    output_load_oid,
    output_power_oid,
    output_voltage_oid,
)

# Per-attempt timeouts. puresnmp's installed Client() doesn't accept
# timeout/retries directly (newer API moved those to the Sender), so we bound
# each multiget with asyncio.wait_for and layer an outer retry loop on top to
# ride out the occasional dropped UDP packet without every entity going
# 'unavailable' for a full poll interval.
SNMP_PER_ATTEMPT_TIMEOUT = 4.0   # seconds — hard cap per multiget attempt
SNMP_OUTER_ATTEMPTS = 3          # retry passes around multiget
SNMP_OUTER_RETRY_DELAY = 0.5     # seconds between outer attempts

_LOGGER = logging.getLogger(__name__)


def modbus_unit_kwargs(fn, unit: int) -> dict:
    """Return the unit-id keyword for a pymodbus read call as {name: unit}.

    pymodbus renamed the parameter from ``slave`` to ``device_id`` around 3.9,
    so we inspect the signature and pick whichever this version accepts rather
    than hard-coding one (a wrong keyword raises TypeError -> 'unknown' error)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {"slave": unit}
    if "slave" in params:
        return {"slave": unit}
    if "device_id" in params:
        return {"device_id": unit}
    return {"slave": unit}


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
        protocol: str = "snmp",
        modbus_unit: int = 1,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._host = host
        self._port = port
        self._community = community
        self._protocol = protocol
        self._modbus_unit = modbus_unit
        # Client construction triggers blocking importlib + os.listdir for
        # puresnmp's plugin discovery, so we defer it to an executor on first
        # use rather than building it here on the event loop.
        self._client: PyWrapper | None = None
        self._modbus_client = None  # AsyncModbusTcpClient, built lazily
        self.ident: dict[str, str | None] = {}
        # Topology — filled in by async_fetch_topology before first poll. The
        # Modbus register map is fixed at three phases (absent phases read 0),
        # so there's no line-count discovery on that transport.
        self.lines_input: int = 3 if protocol == PROTOCOL_MODBUS else 1
        self.lines_output: int = 3 if protocol == PROTOCOL_MODBUS else 1
        # Polled OIDs are kept in chunks (scalar / per-phase input / per-phase
        # output) so a single bad OID only kills one chunk, not the whole poll.
        self._polled_oid_groups: tuple[tuple[str, ...], ...] = ()

    def _build_snmp_client(self) -> PyWrapper:
        """Construct the puresnmp client. Blocking (plugin imports) — call from an executor."""
        return PyWrapper(Client(self._host, V2C(self._community), port=self._port))

    async def _ensure_client(self) -> None:
        if self._client is None:
            self._client = await self.hass.async_add_executor_job(self._build_snmp_client)

    async def _multiget(self, oids: tuple[str, ...]) -> dict[str, object | None]:
        """Fetch many OIDs with retries around the multiget so that a single
        dropped UDP packet doesn't flip every entity to 'unavailable' for an
        entire poll cycle."""
        await self._ensure_client()
        assert self._client is not None  # for type checkers
        last_err: Exception | None = None
        for attempt in range(1, SNMP_OUTER_ATTEMPTS + 1):
            try:
                values = await asyncio.wait_for(
                    self._client.multiget(list(oids)),
                    timeout=SNMP_PER_ATTEMPT_TIMEOUT,
                )
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

    async def _walk_alarm_descrs(self) -> list[str]:
        """Walk the upsAlarmDescr column and return the well-known-alarm OIDs of
        every currently active alarm (empty list when the table has no rows).

        Best-effort and time-bounded like the multigets — the alarm table row
        indices are dynamic, so this is the only way to learn *which* alarms
        (e.g. 'Input bad') are active rather than just how many."""
        await self._ensure_client()
        assert self._client is not None  # for type checkers

        async def _collect() -> list[str]:
            oids: list[str] = []
            async for var_bind in self._client.walk(OID_ALARM_DESCR_COLUMN):
                # upsAlarmDescr's value is an OID pointing into upsWellKnownAlarms.
                oid_str = str(var_bind.value).lstrip(".")
                if oid_str:
                    oids.append(oid_str)
            return oids

        return await asyncio.wait_for(_collect(), timeout=SNMP_PER_ATTEMPT_TIMEOUT)

    async def async_fetch_ident(self) -> None:
        """Read identification strings once (manufacturer, model, …) for device_info.

        SNMP-only — the Modbus register map carries no identity strings, so the
        device falls back to the generic name/model in CS121Entity."""
        if self.ident or self._protocol == PROTOCOL_MODBUS:
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
        if self._protocol == PROTOCOL_MODBUS:
            return await self._async_update_modbus()
        return await self._async_update_snmp()

    async def _async_update_snmp(self) -> dict:
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

        # Best-effort: learn which alarms are active (e.g. 'Input bad'). A failure
        # here must not blank the rest of the poll, so it never adds to `errors`.
        try:
            alarm_oids = await self._walk_alarm_descrs()
            results[KEY_ACTIVE_ALARM_OIDS] = alarm_oids
            results[KEY_ACTIVE_ALARM_LABELS] = [
                WELL_KNOWN_ALARMS.get(oid, oid) for oid in alarm_oids
            ]
        except (SnmpError, asyncio.TimeoutError, OSError) as err:
            _LOGGER.debug("Alarm table walk to %s:%s failed: %s", self._host, self._port, err)
        except Exception as err:  # noqa: BLE001 — optional data; never break the poll
            _LOGGER.debug("Unexpected alarm table walk error: %s", err)

        if not results:
            raise UpdateFailed("; ".join(errors) or "no SNMP data")
        if errors:
            _LOGGER.warning(
                "Partial CS121 update: %d/%d chunks failed (%s); %d values returned.",
                len(errors), len(self._polled_oid_groups), "; ".join(errors), len(results),
            )
        return results

    # --- Modbus transport -------------------------------------------------

    async def _ensure_modbus_client(self):
        if self._modbus_client is None:
            # Imported lazily so SNMP-only installs never need pymodbus loaded.
            from pymodbus.client import AsyncModbusTcpClient

            self._modbus_client = AsyncModbusTcpClient(self._host, port=self._port)
        if not self._modbus_client.connected:
            await self._modbus_client.connect()
        return self._modbus_client

    async def _read_modbus_block(self, start: int, count: int) -> dict[int, int] | None:
        """Read `count` input registers from `start` with retries (the CS121's
        Modbus link drops the odd request just like its SNMP agent). Returns a
        {register: value} map, or None if every attempt failed."""
        client = await self._ensure_modbus_client()
        unit_kw = modbus_unit_kwargs(client.read_input_registers, self._modbus_unit)
        last_err: Exception | None = None
        for attempt in range(1, SNMP_OUTER_ATTEMPTS + 1):
            try:
                rr = await asyncio.wait_for(
                    client.read_input_registers(start, count=count, **unit_kw),
                    timeout=SNMP_PER_ATTEMPT_TIMEOUT,
                )
                if not rr.isError():
                    return {start + i: v for i, v in enumerate(rr.registers)}
                last_err = Exception(str(rr))
            except (asyncio.TimeoutError, OSError, Exception) as err:  # noqa: BLE001
                last_err = err
            if attempt < SNMP_OUTER_ATTEMPTS:
                await asyncio.sleep(SNMP_OUTER_RETRY_DELAY)
        _LOGGER.debug(
            "Modbus read @%d+%d to %s:%s failed: %s",
            start, count, self._host, self._port, last_err,
        )
        return None

    async def _async_update_modbus(self) -> dict:
        """Poll the CS121 over Modbus TCP and project the registers onto the SAME
        OID keyspace the SNMP path uses, so every entity reads identical values
        regardless of transport."""
        regs: dict[int, int] = {}
        # Three modest blocks (telemetry / alarm flags / output) — kept small
        # because the device is happier with shorter reads.
        for start, count in ((100, 15), (115, 25), (140, 6)):
            block = await self._read_modbus_block(start, count)
            if block:
                regs.update(block)
        if not regs:
            raise UpdateFailed(f"No Modbus response from {self._host}:{self._port}")

        data: dict[str, object | None] = {}

        # Telemetry -> OID keys, scaled to the SNMP unit convention.
        for reg, oid, mult, signed in MODBUS_TELEMETRY:
            raw = regs.get(reg)
            if raw is None:
                continue
            if signed and raw > 0x7FFF:
                raw -= 0x10000
            data[oid] = raw * mult

        # Alarm flags -> active well-known-alarm OIDs + human labels, so the
        # existing alarm binary sensors and 'Active alarms' sensor work as-is.
        active_oids: list[str] = []
        labels: list[str] = []
        for reg, oid in MODBUS_ALARM_REGS.items():
            if regs.get(reg) == 1:
                active_oids.append(oid)
                labels.append(WELL_KNOWN_ALARMS.get(oid, oid))
        for reg, label in MODBUS_ALARM_EXTRA.items():
            if regs.get(reg) == 1:
                labels.append(label)
        data[KEY_ACTIVE_ALARM_OIDS] = active_oids
        data[KEY_ACTIVE_ALARM_LABELS] = labels
        data[OID_ALARMS_PRESENT] = len(labels)

        # Derived enums so battery_status / output_source / on_battery / etc. match.
        data[OID_BATTERY_STATUS] = 3 if regs.get(MODBUS_REG_BATTERY_LOW) == 1 else 2
        status = regs.get(MODBUS_REG_STATUS)
        if status is not None:
            if status & MODBUS_STATUS_BACKUP:
                data[OID_OUTPUT_SOURCE] = 5      # on battery
            elif status & MODBUS_STATUS_BYPASS:
                data[OID_OUTPUT_SOURCE] = 4      # bypass
            elif status & MODBUS_STATUS_OUTPUT_ACT:
                data[OID_OUTPUT_SOURCE] = 3      # normal / online
            else:
                data[OID_OUTPUT_SOURCE] = 2      # none

        return data
