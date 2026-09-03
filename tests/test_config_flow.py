"""Tests for the Growspace Manager TC config flow."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.growspace_manager_tc.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_refuses_without_growspace_manager(hass: HomeAssistant) -> None:
    """The flow aborts when the companion integration is not loaded."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "growspace_manager_missing"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_creates_entry_when_growspace_manager_is_loaded(
    hass: HomeAssistant, growspace_manager_loaded: None
) -> None:
    """Confirming the single step creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_refuses_a_second_entry(
    hass: HomeAssistant, growspace_manager_loaded: None
) -> None:
    """One entry covers every culture line, so the manifest allows only one."""
    MockConfigEntry(domain=DOMAIN, title=DEFAULT_NAME).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
