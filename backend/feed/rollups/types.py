from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RollupContext:
    since: datetime
    until: datetime
    configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    system_names: dict[int, str] = field(default_factory=dict)


@dataclass
class RollupResult:
    kind: str
    occurred_at: datetime
    title: str
    subheader: str
    preview: str
    body: str
    accent: str
    payload: dict[str, Any]
    rollup_code: str
    rollup_version: int
    cluster_key: str = ""
    source_type: str = ""
    source_id: int | None = None
    is_active: bool = False
    expires_at: datetime | None = None
    killmail_ids: list[int] = field(default_factory=list)
