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
from homeassistant.core import callback

from .const import (
    CONF_COMMUNITY,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMUNITY,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OID_IDENT_MANUFACTURER,
    SNMP_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def _test_connection(host: str, port: int, community: str) -> str | None:
    """Return None on success, or an error key on failure."""
    client = PyWrapper(Client(host, V2C(community), port=port))
    try:
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


class CS121ConfigFlow(ConfigFlow, domain=DOMAIN):
    """UI configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            error = await _test_connection(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_COMMUNITY],
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(int, vol.Range(min=5, max=3600)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

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
