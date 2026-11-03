"""UI configuration, options, and token replacement."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL, CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import NourishApi, NourishError, InvalidAuth, normalize_url
from .const import DOMAIN, DEFAULT_URL, DEFAULT_INTERVAL, CONF_INTERVAL
from .model import apply_response


def schema(defaults=None):
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, DEFAULT_URL)): str,
            vol.Required(CONF_API_TOKEN): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_INTERVAL, default=defaults.get(CONF_INTERVAL, DEFAULT_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=43200)),
        }
    )


class NourishConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure Nourish via its account-scoped read-only API."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return NourishOptionsFlow()

    async def _validate(self, user_input):
        user_input[CONF_URL] = normalize_url(user_input[CONF_URL])
        user_input[CONF_API_TOKEN] = user_input[CONF_API_TOKEN].strip()
        if not user_input[CONF_API_TOKEN]:
            raise InvalidAuth("Missing API token")
        api = NourishApi(
            async_get_clientsession(self.hass), user_input[CONF_URL], user_input[CONF_API_TOKEN]
        )
        payload = await api.fetch()
        snapshot = apply_response(None, payload, initial=True)
        account_id = str(snapshot["account"]["id"])
        return f"{user_input[CONF_URL]}|{account_id}"

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                unique_id = await self._validate(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NourishError:
                errors["base"] = "cannot_connect"
            except ValueError, KeyError, TypeError:
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Nourish", data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(user_input), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._replace_token("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._replace_token("reconfigure", user_input)

    async def _replace_token(self, step_id, user_input):
        entry = (
            self._get_reauth_entry()
            if step_id == "reauth_confirm"
            else self._get_reconfigure_entry()
        )
        errors = {}
        if user_input is not None:
            try:
                unique_id = await self._validate(user_input)
                if unique_id != entry.unique_id:
                    return self.async_abort(reason="wrong_account")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NourishError:
                errors["base"] = "cannot_connect"
            except ValueError, KeyError, TypeError:
                errors["base"] = "invalid_response"
            else:
                # The coordinator detects a changed token fingerprint and starts
                # a fresh export while preserving historical zero dates.
                result = self.async_update_and_abort(
                    entry,
                    data_updates=user_input,
                    options={**entry.options, CONF_INTERVAL: user_input[CONF_INTERVAL]},
                    reason="reauth_successful"
                    if step_id == "reauth_confirm"
                    else "reconfigure_successful",
                )
                if not entry.update_listeners:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return result
        defaults = {**entry.data, **entry.options}
        return self.async_show_form(step_id=step_id, data_schema=schema(defaults), errors=errors)


class NourishOptionsFlow(config_entries.OptionsFlow):
    """Change the polling interval without requiring the token again."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        interval = self.config_entry.options.get(
            CONF_INTERVAL, self.config_entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTERVAL, default=interval): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=43200)
                    ),
                }
            ),
        )
