"""Export the Amarr-Minmatar warzone jump graph from the SDE.

CCP marks every Faction Warfare system frontline, command operations or
rearguard from how close it sits to enemy-held space, and that state
multiplies complex LP by 1.5, 1.0 or 0.01. ESI does not expose it, so we
derive it from adjacency and need the graph on disk.

Run this once per SDE release:

    python manage.py export_warzone_jump_graph \\
        --sde ../frontend/app/src/data/sde-3316380.sqlite
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from campaigns.services.jump_graph import fixture_path

# The four regions the Amarr-Minmatar warzone spans.
WARZONE_REGION_IDS = [
    10000042,  # Metropolis
    10000030,  # Heimatar
    10000038,  # The Bleak Lands
    10000043,  # Domain
]


class Command(BaseCommand):
    help = "Export the warzone jump graph fixture from the EVE SDE sqlite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sde",
            required=True,
            help="Path to the SDE sqlite (frontend/app/src/data/sde-*.sqlite).",
        )
        parser.add_argument("--out", default=str(fixture_path()))

    def handle(self, *args, **options):
        sde_path = Path(options["sde"]).expanduser()
        if not sde_path.exists():
            raise CommandError(f"No SDE database at {sde_path}")

        connection = sqlite3.connect(str(sde_path))
        placeholders = ",".join("?" for _ in WARZONE_REGION_IDS)

        systems = {
            str(row[0]): {"name": row[1], "region_id": row[2]}
            for row in connection.execute(
                f"""
                SELECT solarSystemID, solarSystemName, regionID
                FROM mapSolarSystems
                WHERE regionID IN ({placeholders})
                """,
                WARZONE_REGION_IDS,
            )
        }

        edges: dict[str, list[int]] = {}
        edge_count = 0
        for from_id, to_id in connection.execute(
            f"""
            SELECT fromSolarSystemID, toSolarSystemID
            FROM mapSolarSystemJumps
            WHERE fromRegionID IN ({placeholders})
              AND toRegionID IN ({placeholders})
            """,
            WARZONE_REGION_IDS + WARZONE_REGION_IDS,
        ):
            edges.setdefault(str(from_id), []).append(to_id)
            edge_count += 1

        connection.close()

        out_path = Path(options["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "source": sde_path.name,
                    "region_ids": WARZONE_REGION_IDS,
                    "systems": systems,
                    "edges": edges,
                },
                indent=1,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(systems)} systems and {edge_count} edges to "
                f"{out_path}"
            )
        )
