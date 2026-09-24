"""Verify that the test plugin and requirements.txt pin the same HA release."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = "pytest-homeassistant-custom-component"


def pin(requirements: str, package: str) -> str:
    """Read one exact package pin, rejecting missing or duplicate declarations."""
    matches: list[str] = re.findall(
        rf"^{re.escape(package)}==([^\s#]+)\s*(?:#.*)?$",
        requirements,
        re.MULTILINE | re.IGNORECASE,
    )
    if len(matches) != 1:
        raise ValueError(f"requirements.txt must have exactly one {package}== pin")
    return matches[0]


def plugin_ha_pin(requires_dist: list[str]) -> str:
    """Extract the plugin's exact Home Assistant requirement from PyPI metadata."""
    matches = [
        match.group(1)
        for requirement in requires_dist
        if (
            match := re.match(
                r"^homeassistant\s*(?:\(\s*)?==\s*([^\s;)]+)",
                requirement,
                re.IGNORECASE,
            )
        )
    ]
    if len(matches) != 1:
        raise ValueError(f"{PLUGIN} must declare exactly one homeassistant== pin")
    return matches[0]


def main() -> int:
    """Fetch the selected plugin release's metadata and compare HA versions."""
    try:
        requirements = (ROOT / "requirements.txt").read_text()
        requested_ha = pin(requirements, "homeassistant")
        plugin_version = pin(requirements, PLUGIN)
        url = f"https://pypi.org/pypi/{PLUGIN}/{plugin_version}/json"
        with urlopen(url, timeout=15) as response:
            metadata = json.load(response)
        plugin_ha = plugin_ha_pin(metadata["info"]["requires_dist"])
    except (OSError, KeyError, TypeError, ValueError) as error:
        sys.stderr.write(f"Cannot check Home Assistant test stack: {error}\n")
        return 1

    if requested_ha != plugin_ha:
        sys.stderr.write(
            f"Home Assistant test stack mismatch: requirements.txt pins "
            f"homeassistant=={requested_ha}, but {PLUGIN}=={plugin_version} "
            f"requires homeassistant=={plugin_ha}. Wait for the plugin to "
            "support the new HA release, then update both pins together.\n"
        )
        return 1
    sys.stdout.write(
        f"Home Assistant test stack pins agree: homeassistant=={requested_ha}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
