"""The site's gate manifest (frontend/app/src/json/feature_gates.json).

Each gate names the pilot feature that owns it and the Django-permission
expression the site used before. The backend reads it to test the mapping
and to audit how many users a switch to features would change.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

DEFAULT_MANIFEST_PATH = (
    Path(settings.BASE_DIR).parent
    / "frontend"
    / "app"
    / "src"
    / "json"
    / "feature_gates.json"
)

# Gates allowed to drop someone the legacy expression let in: the old
# permission showed UI the API already refuses.
LOSS_ALLOWED_PARITY = frozenset({"dead_ui"})


@dataclass(frozen=True)
class Gate:
    key: str
    feature: str
    perms: tuple[str, ...]
    superuser: bool
    custom: bool
    parity: str

    def legacy_allows(self, permissions, is_superuser: bool) -> bool:
        if self.superuser and is_superuser:
            return True
        return any(perm in permissions for perm in self.perms)


def load_gates(path: Path | str | None = None) -> list[Gate]:
    with open(path or DEFAULT_MANIFEST_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    gates = []
    for key, gate in data["gates"].items():
        legacy = gate.get("legacy", {})
        gates.append(
            Gate(
                key=key,
                feature=gate["feature"],
                perms=tuple(legacy.get("perms", [])),
                superuser=bool(legacy.get("superuser", False)),
                custom=bool(legacy.get("custom", False)),
                parity=gate.get("parity", ""),
            )
        )
    return gates
