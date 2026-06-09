from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from octopus.core.paths import (
    BASELINE_PROFILE_MD,
    CURRENT_CONTEXT,
    EXPERIMENT_MEMORY_MD,
    NEXT_STEPS_MD,
    SESSION_MD,
)


@dataclass(frozen=True)
class OctopusResource:
    uri: str
    name: str
    description: str
    path: Path
    mime_type: str = "text/markdown"


RESOURCES: dict[str, OctopusResource] = {
    "octopus://context/current": OctopusResource(
        uri="octopus://context/current",
        name="Current Context",
        description="Latest task-focused context built by octopus context.",
        path=CURRENT_CONTEXT,
    ),
    "octopus://memory/experiments": OctopusResource(
        uri="octopus://memory/experiments",
        name="Experiment Memory",
        description="Long-term experiment memory summary.",
        path=EXPERIMENT_MEMORY_MD,
    ),
    "octopus://session/current": OctopusResource(
        uri="octopus://session/current",
        name="Current Session",
        description="Short-term active session state.",
        path=SESSION_MD,
    ),
    "octopus://reports/baseline_profile": OctopusResource(
        uri="octopus://reports/baseline_profile",
        name="Baseline Profile",
        description="Latest baseline diagnosis and ranked techniques.",
        path=BASELINE_PROFILE_MD,
    ),
    "octopus://plans/next_steps": OctopusResource(
        uri="octopus://plans/next_steps",
        name="Next Steps",
        description="Ranked next experiment directions.",
        path=NEXT_STEPS_MD,
    ),
}


def list_resources() -> list[OctopusResource]:
    return list(RESOURCES.values())


def read_resource(uri: str) -> tuple[OctopusResource, str]:
    try:
        resource = RESOURCES[uri]
    except KeyError as exc:
        raise KeyError(f"Unknown Octopus resource: {uri}") from exc
    if not resource.path.exists():
        return resource, ""
    return resource, resource.path.read_text(encoding="utf-8")
