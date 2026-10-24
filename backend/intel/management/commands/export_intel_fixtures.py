"""Export the intel tool's ship types and jump map from the EVE SDE.

D-scan pastes carry a type id, name and type name per line, but not the
ship class, so grouping a scan by Frigate / Destroyer / Cruiser needs the
SDE's groups. The desktop app works out "how many jumps from me" itself
(the pilot's location never leaves the PC), so it needs the gate graph.
Both are small enough to keep in the repo, like the warzone jump graph.

Run this once per SDE release:

    python manage.py export_intel_fixtures \\
        --sde ../frontend/app/src/data/sde-3316380.sqlite
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from intel.services.fixtures import map_fixture_path, types_fixture_path

# What can show up on d-scan and is worth naming: ships, drones and
# fighters, structures, starbases, deployables and orbitals.
TYPE_CATEGORY_IDS = [6, 18, 22, 23, 40, 46, 65, 87]

# The warzone plus the regions next to it, where intel and capital pings
# near Amamake land.
MAP_REGION_IDS = [
    10000042,  # Metropolis
    10000030,  # Heimatar
    10000038,  # The Bleak Lands
    10000043,  # Domain
    10000028,  # Molden Heath
    10000001,  # Derelik
    10000036,  # Devoid
    10000065,  # Kor-Azor
    10000020,  # Tash-Murkon
]


class Command(BaseCommand):
    help = "Export the intel ship types and jump map from the EVE SDE sqlite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sde",
            required=True,
            help="Path to the SDE sqlite (frontend/app/src/data/sde-*.sqlite).",
        )

    def handle(self, *args, **options):
        sde_path = Path(options["sde"]).expanduser()
        if not sde_path.exists():
            raise CommandError(f"No SDE database at {sde_path}")

        connection = sqlite3.connect(str(sde_path))
        try:
            types = self._types(connection)
            systems, edges = self._map(connection)
        finally:
            connection.close()

        source = sde_path.name
        self._write(types_fixture_path(), {"source": source, "types": types})
        self._write(
            map_fixture_path(),
            {
                "source": source,
                "region_ids": MAP_REGION_IDS,
                "systems": systems,
                "edges": edges,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(types)} types and {len(systems)} systems "
                f"from {source}"
            )
        )

    @staticmethod
    def _types(connection) -> dict[str, list]:
        placeholders = ",".join("?" for _ in TYPE_CATEGORY_IDS)
        rows = connection.execute(
            f"""
            SELECT t.typeID, t.typeName, g.groupName, g.categoryID
            FROM invTypes t JOIN invGroups g ON g.groupID = t.groupID
            WHERE g.categoryID IN ({placeholders}) AND t.published = 1
            ORDER BY t.typeID
            """,
            TYPE_CATEGORY_IDS,
        )
        return {
            str(type_id): [name, group, category]
            for type_id, name, group, category in rows
        }

    @staticmethod
    def _map(connection) -> tuple[dict[str, str], dict[str, list[int]]]:
        placeholders = ",".join("?" for _ in MAP_REGION_IDS)
        systems = {
            str(row[0]): row[1]
            for row in connection.execute(
                f"""
                SELECT solarSystemID, solarSystemName FROM mapSolarSystems
                WHERE regionID IN ({placeholders})
                """,
                MAP_REGION_IDS,
            )
        }
        edges: dict[str, list[int]] = {}
        for from_id, to_id in connection.execute(
            f"""
            SELECT fromSolarSystemID, toSolarSystemID
            FROM mapSolarSystemJumps
            WHERE fromRegionID IN ({placeholders})
              AND toRegionID IN ({placeholders})
            ORDER BY fromSolarSystemID, toSolarSystemID
            """,
            MAP_REGION_IDS + MAP_REGION_IDS,
        ):
            edges.setdefault(str(from_id), []).append(to_id)
        return systems, edges

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            json.dump(data, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
