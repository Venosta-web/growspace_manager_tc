"""Tests for the files HACS and Home Assistant read before any code runs."""

import json
from pathlib import Path

from custom_components.growspace_manager_tc.const import DOMAIN

_COMPONENT = Path(__file__).parent.parent / "custom_components" / DOMAIN
_REPOSITORY = Path(__file__).parent.parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_describes_this_integration() -> None:
    """The manifest names the domain it lives in and declares its shape."""
    manifest = _load(_COMPONENT / "manifest.json")

    assert manifest["domain"] == DOMAIN == _COMPONENT.name
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["version"]
    # HACS refuses a custom integration whose manifest omits these.
    assert manifest["documentation"]
    assert manifest["issue_tracker"]
    assert manifest["codeowners"]


def test_hacs_manifest_is_installable() -> None:
    """hacs.json names the integration and the floor it needs."""
    hacs = _load(_REPOSITORY / "hacs.json")

    assert hacs["name"]
    assert hacs["homeassistant"]


def test_hacs_installs_the_published_archive_and_not_the_branch() -> None:
    """Without these two keys HACS copies the default branch into config/.

    That ships tests/, docs/ and whatever else happens to be on `main` at the
    moment the user clicks install. The release workflow builds the archive;
    only hacs.json redirects HACS to it.
    """
    hacs = _load(_REPOSITORY / "hacs.json")

    assert hacs["zip_release"] is True
    assert hacs["filename"] == f"{DOMAIN}.zip"


def test_english_translations_match_strings() -> None:
    """translations/en.json is the copy Home Assistant actually loads.

    strings.json is the source of truth for translators; a custom integration
    is served from translations/en.json instead, so a message improved in one
    and not the other is invisible to the user it was written for.
    """
    assert _load(_COMPONENT / "strings.json") == _load(
        _COMPONENT / "translations" / "en.json"
    )


def test_every_flow_outcome_has_a_message() -> None:
    """Each way setup can end tells the user something actionable."""
    strings = _load(_COMPONENT / "strings.json")

    # Raised by the flow itself.
    assert strings["config"]["abort"]["growspace_manager_missing"]
    # Raised by Home Assistant, because the manifest sets single_config_entry.
    assert strings["config"]["abort"]["single_instance_allowed"]
    # Raised by async_setup_entry when the companion disappears later.
    assert strings["exceptions"]["growspace_manager_missing"]["message"]
