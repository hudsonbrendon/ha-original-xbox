"""Config flow do Xbox Clássico."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import APP_OTHER, XboxClient, XboxError, XboxOffline
from .const import CONF_DASHBOARD, DEFAULT_DASHBOARD, DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN


def _arp_mac(host: str) -> str | None:
    """MAC pela tabela ARP do host do HA (o container usa a rede do host)."""
    try:
        with open("/proc/net/arp", encoding="ascii") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if parts and parts[0] == host and parts[3] != "00:00:00:00:00:00":
                    return format_mac(parts[3])
    except OSError:
        pass
    return None


def _probe(host: str, username: str, password: str) -> tuple[dict[str, str], str | None]:
    info = XboxClient(host, username, password).probe()
    return info, _arp_mac(host)


class XboxConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        mac = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        try:
            info, _ = await self.hass.async_add_executor_job(
                _probe, discovery_info.ip, DEFAULT_USERNAME, DEFAULT_PASSWORD
            )
        except XboxError:
            return self.async_abort(reason="not_xbox")
        if info["app"] == APP_OTHER:
            return self.async_abort(reason="not_xbox")
        self._host = discovery_info.ip
        self.context["title_placeholders"] = {"host": discovery_info.ip}
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                info, mac = await self.hass.async_add_executor_job(
                    _probe, host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except XboxOffline:
                errors["base"] = "cannot_connect"
            except XboxError:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(mac or self.unique_id or f"xbox_{host}")
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title="Xbox Clássico",
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={CONF_DASHBOARD: DEFAULT_DASHBOARD},
                    description_placeholders={"system": info.get("system", "")},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host or ""): str,
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return XboxOptionsFlow()


class XboxOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_DASHBOARD, DEFAULT_DASHBOARD)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_DASHBOARD, default=current): str}),
        )
