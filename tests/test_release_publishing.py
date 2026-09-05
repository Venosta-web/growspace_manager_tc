"""Regression tests for the TC stable and prerelease publishing channels."""

import json
from pathlib import Path
import runpy

from awesomeversion import AwesomeVersion
import yaml

REPO_ROOT = Path(__file__).parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/prerelease.yaml"
STABLE_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/release.yaml"
MANIFEST_PATH = REPO_ROOT / "custom_components/growspace_manager_tc/manifest.json"
VERSION_SCRIPT = REPO_ROOT / ".github/scripts/prerelease_version.py"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def _workflow_steps() -> list[dict]:
    return _workflow()["jobs"]["build"]["steps"]


def _step(name: str) -> dict:
    return next(step for step in _workflow_steps() if step.get("name") == name)


def test_prerelease_publishing_contract() -> None:
    """The prerelease must be monotonic, correctly tagged, and pruned."""
    version_module = runpy.run_path(str(VERSION_SCRIPT))

    stable = json.loads(MANIFEST_PATH.read_text())["version"]
    prerelease = version_module["prerelease_version"](stable, 123)
    assert prerelease == f"{version_module['next_stable_version'](stable)}b123"
    # HACS offers an update only when the new version sorts above the installed
    # one, so a beta of the *next* patch is what makes the channel usable.
    assert AwesomeVersion(prerelease) > AwesomeVersion(stable)
    assert AwesomeVersion(prerelease) > AwesomeVersion(
        version_module["prerelease_version"](stable, 122)
    )

    assert _workflow()["on"] == {"push": {"branches": ["prerelease"]}}
    assert _workflow()["concurrency"] == {
        "group": "prerelease-publish",
        "cancel-in-progress": False,
    }

    release = _step("Create Pre-release")
    assert release["with"]["prerelease"] is True
    assert release["with"]["tag_name"] == "v${{ steps.version_step.outputs.version }}"
    assert release["with"]["target_commitish"] == "${{ github.sha }}"
    assert release["with"]["generate_release_notes"] is True
    assert release["with"]["fail_on_unmatched_files"] is True
    # Two prereleases must be distinguishable at a glance on the releases page.
    assert "${{ github.ref_name }}" in release["with"]["name"]
    assert "${{ github.sha }}" in release["with"]["name"]

    # The computed beta lives in the workspace only. Committing it would move
    # the stable version the next run's calculation reads.
    assert not any(
        step.get("name") == "Commit prerelease version" for step in _workflow_steps()
    )

    verification = _step("Verify release tag")
    assert "GITHUB_SHA" in verification["run"]
    assert "git/ref/tags" in verification["run"]

    cleanup = _step("Delete Older Pre-releases")
    assert cleanup["with"]["keep_latest"] == 5
    assert cleanup["with"]["delete_prerelease_only"] is True
    assert cleanup["with"]["delete_tags"] is True
    assert "delete_tag_pattern" not in cleanup["with"]


def test_stable_publishing_contract() -> None:
    """A main push must publish and verify the manifest's stable version."""
    workflow = yaml.safe_load(STABLE_WORKFLOW_PATH.read_text())

    assert workflow["on"] == {
        "push": {"branches": ["main"]},
        "workflow_dispatch": None,
    }
    assert workflow["concurrency"] == {
        "group": "stable-publish",
        "cancel-in-progress": False,
    }

    steps = workflow["jobs"]["build"]["steps"]
    version = next(
        step for step in steps if step.get("name") == "Read version from manifest.json"
    )
    # The version is a consequence of a reviewed manifest bump, and a version
    # that is not X.Y.Z must not be published as stable.
    assert "custom_components/growspace_manager_tc/manifest.json" in version["run"]
    assert "^[0-9]+\\.[0-9]+\\.[0-9]+$" in version["run"]

    # An already-published version is skipped rather than re-tagged, so a
    # docs-only merge needs no version bump.
    existing = next(
        step for step in steps if step.get("name") == "Check for existing release"
    )
    assert "exists=true" in existing["run"]
    skipped = {
        step["name"]
        for step in steps
        if step.get("if") == "steps.check_release.outputs.exists != 'true'"
    }
    assert {"ZIP Release", "Create Release", "Verify release tag"} <= skipped

    release = next(step for step in steps if step.get("name") == "Create Release")
    assert release["with"]["tag_name"] == "v${{ steps.version_step.outputs.version }}"
    assert release["with"]["target_commitish"] == "${{ github.sha }}"
    assert release["with"]["generate_release_notes"] is True
    assert release["with"]["fail_on_unmatched_files"] is True
    assert "growspace_manager_tc.zip" in release["with"]["files"]

    verification = next(
        step for step in steps if step.get("name") == "Verify release tag"
    )
    assert "TARGET_SHA" in verification["run"]
    assert "git/ref/tags" in verification["run"]


def test_publishing_jobs_request_only_what_they_use() -> None:
    """A publish job writes releases and nothing else."""
    for path in (STABLE_WORKFLOW_PATH, WORKFLOW_PATH):
        workflow = yaml.safe_load(path.read_text())
        assert "permissions" not in workflow
        for job in workflow["jobs"].values():
            assert job["permissions"] == {"contents": "write"}


def test_the_prerelease_branch_survives_the_weekly_branch_sweep() -> None:
    """The sweep deletes what nothing reserves, and this is a channel branch."""
    maintenance = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/branch-maintenance.yaml").read_text()
    )
    keep = maintenance["jobs"]["maintain-branches"]["env"]["KEEP_BRANCHES"]

    assert "prerelease" in keep.split(",")
