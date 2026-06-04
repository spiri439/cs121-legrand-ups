"""Config flow for the CS121 Legrand UPS integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from puresnmp import Client, V2C, PyWrapper
from puresnmp.exc import SnmpError

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_COMMUNITY,
    CONF_MODBUS_PORT,
    CONF_MODBUS_UNIT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMUNITY,
    DEFAULT_MODBUS_PORT,
    DEFAULT_MODBUS_UNIT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OID_IDENT_MANUFACTURER,
    PROTOCOL_BOTH,
    PROTOCOL_MODBUS,
    PROTOCOLS,
    SNMP_TIMEOUT,
)
from .coordinator import modbus_unit_kwargs

_LOGGER = logging.getLogger(__name__)


def _build_test_client(host: str, port: int, community: str) -> PyWrapper:
    """Construct a puresnmp client. Blocking (plugin imports); call via executor."""
    return PyWrapper(Client(host, V2C(community), port=port))


async def _test_connection(
    hass: HomeAssistant, host: str, port: int, community: str
) -> str | None:
    """Return None on success, or an error key on failure."""
    try:
        client = await hass.async_add_executor_job(
            _build_test_client, host, port, community
        )
        value = await asyncio.wait_for(
            client.get(OID_IDENT_MANUFACTURER), timeout=SNMP_TIMEOUT
        )
        if not value:
            return "invalid_response"
    except (SnmpError, asyncio.TimeoutError, OSError) as err:
        _LOGGER.warning("CS121 connection test failed: %s", err)
        return "cannot_connect"
    except Exception:  # noqa: BLE001 - keep a clean error code rather than 'unknown'
        _LOGGER.exception("Unexpected error testing CS121 connection")
        return "unknown"
    return None


async def _test_modbus(host: str, port: int, unit: int) -> str | None:
    """Return None on success, or an error key on failure. Reads the battery
    charge register (103) to confirm the CS121 answers Modbus on this unit."""
    try:
        from pymodbus.client import AsyncModbusTcpClient

        client = AsyncModbusTcpClient(host, port=port)
        await client.connect()
        if not client.connected:
            return "cannot_connect"
        try:
            unit_kw = modbus_unit_kwargs(client.read_input_registers, unit)
            rr = await asyncio.wait_for(
                client.read_input_registers(103, count=1, **unit_kw),
                timeout=SNMP_TIMEOUT,
            )
            if rr.isError():
                return "invalid_response"
        finally:
            client.close()
    except (asyncio.TimeoutError, OSError) as err:
        _LOGGER.warning("CS121 Modbus connection test failed: %s", err)
        return "cannot_connect"
    except Exception:  # noqa: BLE001 - keep a clean error code rather than 'unknown'
        _LOGGER.exception("Unexpected error testing CS121 Modbus connection")
        return "unknown"
    return None


class CS121ConfigFlow(ConfigFlow, domain=DOMAIN):
    """UI configuration flow.

    Step 1 picks the host + transport from a dropdown; step 2 then shows only
    the fields that transport needs, pre-filled with its default port (SNMP
    161 / Modbus TCP 502)."""

    VERSION = 1

    def __init__(self) -> None:
        self._base: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._base = dict(user_input)
            protocol = user_input[CONF_PROTOCOL]
            if protocol == PROTOCOL_MODBUS:
                return await self.async_step_modbus()
            if protocol == PROTOCOL_BOTH:
                return await self.async_step_both()
            return await self.async_step_snmp()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): SelectSelector(
                    SelectSelectorConfig(
                        options=list(PROTOCOLS),
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="protocol",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_snmp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._base, **user_input}
            await self.async_set_unique_id(f"{data[CONF_HOST]}:{data[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            error = await _test_connection(
                self.hass, data[CONF_HOST], data[CONF_PORT], data[CONF_COMMUNITY]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(int, vol.Range(min=5, max=3600)),
            }
        )
        return self.async_show_form(step_id="snmp", data_schema=schema, errors=errors)

    async def async_step_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._base, **user_input}
            await self.async_set_unique_id(f"{data[CONF_HOST]}:{data[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            error = await _test_modbus(
                data[CONF_HOST], data[CONF_PORT], data[CONF_MODBUS_UNIT]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT, default=DEFAULT_MODBUS_PORT): int,
                vol.Required(
                    CONF_MODBUS_UNIT, default=DEFAULT_MODBUS_UNIT
                ): vol.All(int, vol.Range(min=0, max=255)),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(int, vol.Range(min=5, max=3600)),
            }
        )
        return self.async_show_form(step_id="modbus", data_schema=schema, errors=errors)

    async def async_step_both(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._base, **user_input}
            await self.async_set_unique_id(f"{data[CONF_HOST]}:{data[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            error = await _test_connection(
                self.hass, data[CONF_HOST], data[CONF_PORT], data[CONF_COMMUNITY]
            )
            if not error:
                error = await _test_modbus(
                    data[CONF_HOST], data[CONF_MODBUS_PORT], data[CONF_MODBUS_UNIT]
                )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
                vol.Required(CONF_MODBUS_PORT, default=DEFAULT_MODBUS_PORT): int,
                vol.Required(
                    CONF_MODBUS_UNIT, default=DEFAULT_MODBUS_UNIT
                ): vol.All(int, vol.Range(min=0, max=255)),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(int, vol.Range(min=5, max=3600)),
            }
        )
        return self.async_show_form(step_id="both", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CS121OptionsFlow()


class CS121OptionsFlow(OptionsFlow):
    """Allow changing the scan interval after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    int, vol.Range(min=5, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
