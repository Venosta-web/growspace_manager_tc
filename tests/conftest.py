"""Shared fixtures for the Growspace Manager TC test suite."""

import pytest

from custom_components.growspace_manager_tc.const import GROWSPACE_MANAGER_DOMAIN
from homeassistant.core import HomeAssistant


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the explicit regeneration option for committed contract fixtures."""
    parser.addoption(
        "--regenerate-contract-fixture",
        action="store_true",
        help="Regenerate tests/fixtures/contract/tc_manifest_response.json",
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load this repository's custom_components/."""


@pytest.fixture
def growspace_manager_loaded(hass: HomeAssistant) -> None:
    """Pretend Growspace Manager has finished setting up.

    The gate asks `hass.config.components`, which is what Home Assistant marks
    when an integration is loaded — so a real Growspace Manager checkout is not
    needed to exercise either side of it.
    """
    hass.config.components.add(GROWSPACE_MANAGER_DOMAIN)
