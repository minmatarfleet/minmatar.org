"""Refresh Hed + CVA campaign theatres from production_readonly + live ESI.

Dev only. Copies recent killmails, contested readings, structure timers, and
the CVA-related strategic fleets (with AAR links) into the local campaigns.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

import factory
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.models import signals
from django.utils import timezone

from campaigns.helpers import campaign_day
from campaigns.models import (
    Campaign,
    CampaignKillmail,
    CampaignSystemSnapshot,
    StructureStatus,
)
from campaigns.services import (
    attribution,
    fleets as fleet_service,
    plan,
    snapshots,
    stats,
)
from campaigns.services import structures as structure_service
from eveonline.models import EveLocation
from feed.models import FeedKillmail
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
)
from structures.models import EveStructureTimer

PROD = "production_readonly"

HED_SYSTEM_IDS = [
    30002537,  # Amamake
    30002538,  # Vard
    30002539,  # Siseide
    30002540,  # Lantorn
    30002541,  # Dal
    30002542,  # Auga
]
CVA_SYSTEM_IDS = [
    30003069,  # Kamela
    30002958,  # Raa
]
THEATER_SYSTEM_IDS = HED_SYSTEM_IDS + CVA_SYSTEM_IDS

# Production strategic fleets tied to the CVA / Raa / Kamela push, with AAR
# Discord threads filled in when the fleet row itself has none.
CVA_FLEET_AARS: dict[int, str | None] = {
    # Azbel timer in Raa (Snuff third-party) — AAR forum thread
    2297: "https://discord.com/channels/1041384161505722368/1545553318984552458",
    2298: "https://discord.com/channels/1041384161505722368/1545553318984552458",
    # CVA Fortizar hull (Knock Knock) — 350B capital engagement AAR
    2288: "https://discord.com/channels/1041384161505722368/1543594299156074627",
    # Keep prod aar_link when present
    2284: None,
    2289: None,
    # Kamela push / Turning the Tide AAR
    2317: "https://discord.com/channels/1041384161505722368/1549476710322409473",
    2331: "https://discord.com/channels/1041384161505722368/1549476710322409473",
    # Town hall + Raa/Dal structure chores
    2323: None,
    2340: None,  # Raa Azbel armor + Dal Fortizar anchoring
    2343: None,  # Amarr Astrahus final
    2344: None,  # Wardogs / structure chores
    2339: None,  # Third-party timer
    # Upcoming CVA/structure follow-ups on the schedule
    2352: None,
    2354: None,
    2356: None,
}

# Discord pastes from #fcs that are newer than the last prod timerboard rows.
DISCORD_STRUCTURES = [
    {
        "name": "I dunno why I still standin",
        "structure_type": "fortizar",
        "system_name": "Raa",
        "solar_system_id": 30002958,
        "alliance_name": "Curatores Veritatis Alliance",
        "corporation_name": "",
        "status": StructureStatus.REINFORCED,
        "timer": datetime(2026, 9, 22, 18, 33, 1, tzinfo=dt_timezone.utc),
        "timer_state": "armor",
    },
    {
        "name": "Sacriledge Fleet is OP 5 years",
        "structure_type": "azbel",
        "system_name": "Raa",
        "solar_system_id": 30002958,
        "alliance_name": "Sev3rance",
        "corporation_name": "",
        "status": StructureStatus.REINFORCED,
        "timer": datetime(2026, 9, 24, 18, 11, 37, tzinfo=dt_timezone.utc),
        "timer_state": "armor",
    },
]


class Command(BaseCommand):
    help = (
        "Pull live ESI + production_readonly killmails/timers/fleets into "
        "the local Hed and CVA campaigns (dev only)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--pilots", type=int, default=50)
        parser.add_argument(
            "--skip-killmails",
            action="store_true",
            help="Reuse local feed killmails instead of copying from prod.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if not options["skip_killmails"]:
            copied = self._copy_killmails(days)
            self.stdout.write(f"Copied {copied} killmails from production")

        # Make sure the campaigns exist (seed creates them if missing).
        call_command(
            "seed_kind_campaigns",
            days=days,
            pilots=options["pilots"],
            reset=False,
        )

        hed = Campaign.objects.get(slug="hed-constellation")
        cva = Campaign.objects.get(slug="cva-pressure")

        self._refresh_snapshots(hed)
        structures = self._refresh_cva_structures(cva)
        fleet_n = self._refresh_cva_fleets(cva)
        attributed = self._reattribute(hed, days) + self._reattribute(
            cva, days
        )

        for campaign in (hed, cva):
            stats.materialise_recent(campaign, days=days)
            stats.rebuild_stats(campaign)
            if campaign.is_faction_warfare:
                plan.propose_week(campaign)
                plan.update_week_progress(campaign)
                plan.generate_orders(campaign)
                plan.evaluate_orders(campaign)

        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed Hed + CVA: {structures} structures, "
                f"{fleet_n} fleets, {attributed} mails attributed. "
                f"/campaigns/hed-constellation/ · /campaigns/cva-pressure/"
            )
        )

    def _copy_killmails(self, days: int) -> int:
        since = timezone.now() - timedelta(days=days)
        remote = FeedKillmail.objects.using(PROD).filter(
            solar_system_id__in=THEATER_SYSTEM_IDS,
            killmail_time__gte=since,
        )
        copied = 0
        for mail in remote.iterator(chunk_size=500):
            _, created = FeedKillmail.objects.update_or_create(
                killmail_id=mail.killmail_id,
                defaults={
                    "hash": mail.hash,
                    "killmail_time": mail.killmail_time,
                    "solar_system_id": mail.solar_system_id,
                    "victim_character_id": mail.victim_character_id,
                    "victim_ship_type_id": mail.victim_ship_type_id,
                    "attacker_summary": mail.attacker_summary or [],
                    "raw_killmail": mail.raw_killmail or {},
                    "zkb_meta": mail.zkb_meta or {},
                    "zkill_sequence_id": mail.zkill_sequence_id,
                },
            )
            copied += int(created)
        return copied

    def _refresh_snapshots(self, campaign: Campaign) -> None:
        CampaignSystemSnapshot.objects.filter(
            campaign_system__campaign=campaign
        ).delete()
        result = snapshots.record_snapshots()
        self.stdout.write(
            f"  Hed snapshots from ESI: {result.get('written', 0)}"
        )

    def _refresh_cva_structures(self, campaign: Campaign) -> int:
        """Prod timerboard rows for Kamela/Raa + the latest Discord pastes."""
        campaign.structures.all().delete()
        EveStructureTimer.objects.filter(campaign=campaign).delete()

        cursor = connections[PROD].cursor()
        cursor.execute(
            """
            SELECT id, name, type, state, timer, system_name,
                   alliance_name, corporation_name
            FROM structures_evestructuretimer
            WHERE system_name IN ('Kamela', 'Raa', 'Dal')
              AND timer >= %s
            ORDER BY timer DESC
            """,
            [timezone.now() - timedelta(days=45)],
        )
        rows = cursor.fetchall()
        operator = User.objects.filter(is_superuser=True).first()
        written = 0

        for (
            unused_prod_id,
            name,
            structure_type,
            state,
            timer,
            system_name,
            alliance_name,
            corporation_name,
        ) in rows:
            _ = unused_prod_id
            name = (name or "").strip()
            status = StructureStatus.REINFORCED
            if state in ("anchoring", "unanchoring"):
                status = StructureStatus.ANCHORED
            timer_row, _ = EveStructureTimer.objects.update_or_create(
                name=name,
                system_name=system_name,
                type=structure_type,
                defaults={
                    "state": state or "armor",
                    "timer": timer,
                    "alliance_name": alliance_name,
                    "corporation_name": corporation_name,
                    "campaign": campaign,
                    "created_by": operator,
                },
            )
            structure_service.attach_structure(
                campaign,
                name=name,
                structure_type=structure_type,
                system_name=system_name,
                corporation_name=corporation_name or "",
                alliance_name=alliance_name or "",
                status=status,
                timer=timer_row,
                created_by=operator,
            )
            written += 1

        for row in DISCORD_STRUCTURES:
            timer_row, _ = EveStructureTimer.objects.update_or_create(
                name=row["name"],
                system_name=row["system_name"],
                type=row["structure_type"],
                defaults={
                    "state": row["timer_state"],
                    "timer": row["timer"],
                    "alliance_name": row["alliance_name"],
                    "corporation_name": row["corporation_name"] or None,
                    "campaign": campaign,
                    "created_by": operator,
                },
            )
            structure_service.attach_structure(
                campaign,
                name=row["name"],
                structure_type=row["structure_type"],
                system_name=row["system_name"],
                solar_system_id=row["solar_system_id"],
                corporation_name=row["corporation_name"],
                alliance_name=row["alliance_name"],
                status=row["status"],
                timer=timer_row,
                created_by=operator,
            )
            written += 1

        self.stdout.write(f"  CVA structures/timers: {written}")
        return written

    def _refresh_cva_fleets(self, campaign: Campaign) -> int:
        audience = EveFleetAudience.objects.filter(name="Warzone").first()
        if audience is None:
            audience = EveFleetAudience.objects.first()

        # Drop previously imported CVA fleets for a clean refresh.
        EveFleet.objects.filter(
            campaign=campaign,
            description__startswith="[prod#",
        ).delete()

        cursor = connections[PROD].cursor()
        placeholders = ",".join(["%s"] * len(CVA_FLEET_AARS))
        cursor.execute(
            f"""
            SELECT id, description, objective, type, status, start_time,
                   aar_link, created_by_id, location_id
            FROM fleets_evefleet
            WHERE id IN ({placeholders})
            ORDER BY start_time
            """,
            list(CVA_FLEET_AARS.keys()),
        )
        rows = cursor.fetchall()
        created = 0

        for (
            prod_id,
            description,
            objective,
            fleet_type,
            status,
            start_time,
            aar_link,
            created_by_id,
            location_id,
        ) in rows:
            aar = CVA_FLEET_AARS.get(prod_id) or aar_link or None
            local_user = self._map_user(created_by_id)
            marked = f"[prod#{prod_id}] {description or ''}".strip()
            location_id = (
                location_id
                if location_id
                and EveLocation.objects.filter(pk=location_id).exists()
                else None
            )

            with factory.django.mute_signals(
                signals.pre_save, signals.post_save
            ):
                fleet = EveFleet.objects.create(
                    type=fleet_type or "strategic",
                    description=marked,
                    objective=objective or "",
                    start_time=start_time,
                    status=status or "complete",
                    campaign=campaign,
                    created_by=local_user,
                    audience=audience,
                    location_id=location_id,
                    aar_link=aar,
                    disable_motd=True,
                )
            self._copy_fleet_attendance(prod_id, fleet)
            created += 1

            if status == "complete":
                fleet_service.link_killmails_to_fleets(
                    campaign, campaign_day(start_time)
                )

        self.stdout.write(f"  CVA fleets imported: {created}")
        return created

    def _copy_fleet_attendance(
        self, prod_fleet_id: int, fleet: EveFleet
    ) -> None:
        cursor = connections[PROD].cursor()
        cursor.execute(
            """
            SELECT id, start_time, end_time
            FROM fleets_evefleetinstance
            WHERE eve_fleet_id = %s
            ORDER BY id
            """,
            [prod_fleet_id],
        )
        instances = cursor.fetchall()
        for prod_instance_id, start_time, end_time in instances:
            local_instance_id = 800_000_000 + int(prod_instance_id)
            EveFleetInstance.objects.filter(pk=local_instance_id).delete()
            instance = EveFleetInstance.objects.create(
                id=local_instance_id,
                eve_fleet=fleet,
                end_time=end_time,
            )
            EveFleetInstance.objects.filter(pk=instance.pk).update(
                start_time=start_time or fleet.start_time,
                last_updated=end_time or start_time or fleet.start_time,
            )
            cursor.execute(
                """
                SELECT character_id, character_name, join_time, role, role_name,
                       ship_type_id, ship_name, solar_system_id, solar_system_name,
                       squad_id, wing_id, updated_at
                FROM fleets_evefleetinstancemember
                WHERE eve_fleet_instance_id = %s
                """,
                [prod_instance_id],
            )
            for member in cursor.fetchall():
                (
                    character_id,
                    character_name,
                    join_time,
                    role,
                    role_name,
                    ship_type_id,
                    ship_name,
                    solar_system_id,
                    solar_system_name,
                    squad_id,
                    wing_id,
                    updated_at,
                ) = member
                row = EveFleetInstanceMember.objects.create(
                    eve_fleet_instance=instance,
                    character_id=character_id,
                    character_name=character_name or "",
                    role=role or "squad_member",
                    role_name=role_name or "Squad Member",
                    ship_type_id=ship_type_id or 0,
                    ship_name=ship_name or "",
                    solar_system_id=solar_system_id or 0,
                    solar_system_name=solar_system_name or "",
                    squad_id=squad_id or 0,
                    wing_id=wing_id or 0,
                )
                EveFleetInstanceMember.objects.filter(pk=row.pk).update(
                    join_time=join_time or fleet.start_time,
                    updated_at=updated_at or end_time or fleet.start_time,
                )

    def _map_user(self, prod_user_id: int | None) -> User | None:
        if not prod_user_id:
            return User.objects.filter(is_superuser=True).first()
        cursor = connections[PROD].cursor()
        cursor.execute(
            "SELECT username FROM auth_user WHERE id = %s", [prod_user_id]
        )
        row = cursor.fetchone()
        if not row:
            return User.objects.filter(is_superuser=True).first()
        return (
            User.objects.filter(username=row[0]).first()
            or User.objects.filter(is_superuser=True).first()
        )

    def _reattribute(self, campaign: Campaign, days: int) -> int:
        """Attribute fresh prod mails without inventing timestamps."""
        CampaignKillmail.objects.filter(campaign=campaign).delete()
        since = timezone.now() - timedelta(days=days)
        attributed = 0
        rosters: dict = {}
        for mail in FeedKillmail.objects.filter(
            solar_system_id__in=campaign.system_ids(),
            killmail_time__gte=since,
            killmail_time__lte=timezone.now() + timedelta(hours=1),
        ).iterator():
            attributed += attribution.attribute_feed_killmail(
                mail, source="prod_refresh", rosters=rosters
            )
        self.stdout.write(f"  {campaign.slug}: attributed {attributed}")
        return attributed
