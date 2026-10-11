"""Single-instance configuration through the Home Assistant UI."""
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class StationMeteoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the station panel; entity settings are in its gear menu."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Station Météo", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
