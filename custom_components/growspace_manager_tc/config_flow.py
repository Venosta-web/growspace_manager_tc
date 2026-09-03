"""Configuration flow for the Growspace Manager TC integration.

Setting up tissue-culture tracking needs nothing from the user: every culture
line references a phenotype that Growspace Manager owns, so the only question
this flow has to answer is whether Growspace Manager is there to reference.
"""

from __future__ import annotations

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DEFAULT_NAME, DOMAIN, GROWSPACE_MANAGER_DOMAIN

_LOGGER = logging.getLogger(__name__)


class GrowspaceTcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of Growspace Manager TC.

    A second entry is refused by Home Assistant itself — the manifest declares
    `single_config_entry` — so this flow only guards the companion dependency.
    """

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup, once Growspace Manager is loaded.

        Args:
            user_input: The user's confirmation, or None to show the form.

        Returns:
            An abort naming the missing companion, the confirmation form, or the
            created entry.
        """
        if GROWSPACE_MANAGER_DOMAIN not in self.hass.config.components:
            _LOGGER.debug("Refusing setup: %s is not loaded", GROWSPACE_MANAGER_DOMAIN)
            return self.async_abort(reason="growspace_manager_missing")

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

        return self.async_create_entry(title=DEFAULT_NAME, data={})
