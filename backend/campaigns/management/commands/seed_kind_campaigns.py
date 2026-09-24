"""Seed Hed FW + CVA strategic campaigns from live Discord context (dev only).

Theatre and structure names come from alliance Discord (announcements / #fcs):
Hed constellation priority, Kamela Fortizar, and the Raa timers Bear pasted.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone

from campaigns.models import (
    AreaScope,
    Campaign,
    CampaignAdvantageReading,
    CampaignArea,
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEnlistmentPeriod,
    CampaignKillmail,
    CampaignKind,
    CampaignOpponent,
    CampaignStandingFleet,
    CampaignStatus,
    CampaignSystem,
    CampaignSystemArc,
    CampaignSystemSnapshot,
    StructureStatus,
    SystemGoal,
    SystemRole,
)
from campaigns.services import (
    advantage,
    attribution,
    plan,
    sites,
    snapshots,
    stats,
)
from campaigns.services import structures as structure_service
from eveonline.models import EveCharacter, EvePlayer
from feed.models import FeedKillmail
from structures.models import EveStructureTimer

# ESI constellation Hed (20000372) — Amamake, Vard, Siseide, Lantorn, Dal, Auga.
HED_SYSTEMS = [
    # name, system_id, goal, role, target_state
    ("Amamake", 30002537, SystemGoal.DEFEND, SystemRole.PRIMARY, "hold"),
    ("Auga", 30002542, SystemGoal.DEFEND, SystemRole.PRIMARY, "hold"),
    ("Siseide", 30002539, SystemGoal.DEFEND, SystemRole.PRIMARY, "hold"),
    ("Dal", 30002541, SystemGoal.CONTEST, SystemRole.SECONDARY, "flip"),
    ("Vard", 30002538, SystemGoal.CONTEST, SystemRole.SECONDARY, "flip"),
    ("Lantorn", 30002540, SystemGoal.CONTEST, SystemRole.SUPPORT, "flip"),
]

CVA_ALLIANCE_ID = 1988009451
SEV3RANCE_ALLIANCE_ID = 982284363

# Structure pastes from #fcs (2026-09-20) plus the known Kamela Fortizar.
CVA_STRUCTURES = [
    {
        "name": "Kamela Fortizar",
        "structure_type": "fortizar",
        "system_name": "Kamela",
        "solar_system_id": 30003069,
        "alliance_name": "Curatores Veritatis Alliance",
        "alliance_id": CVA_ALLIANCE_ID,
        "corporation_name": "Imperial Dreams",
        "status": StructureStatus.ANCHORED,
        "timer": None,
        "timer_state": None,
    },
    {
        "name": "I dunno why I still standin",
        "structure_type": "fortizar",
        "system_name": "Raa",
        "solar_system_id": 30002958,
        "alliance_name": "Curatores Veritatis Alliance",
        "alliance_id": CVA_ALLIANCE_ID,
        "corporation_name": "",
        "status": StructureStatus.REINFORCED,
        # Discord paste: Reinforced until 2026.09.22 18:33:01
        "timer": datetime(2026, 9, 22, 18, 33, 1, tzinfo=dt_timezone.utc),
        "timer_state": "armor",
    },
    {
        "name": "Sacriledge Fleet is OP 5 years",
        "structure_type": "azbel",
        "system_name": "Raa",
        "solar_system_id": 30002958,
        "alliance_name": "Sev3rance",
        "alliance_id": SEV3RANCE_ALLIANCE_ID,
        "corporation_name": "",
        "status": StructureStatus.REINFORCED,
        # Discord paste: Reinforced until 2026.09.24 18:11:37
        "timer": datetime(2026, 9, 24, 18, 11, 37, tzinfo=dt_timezone.utc),
        "timer_state": "armor",
    },
]


class Command(BaseCommand):
    help = (
        "Seed Hed constellation FW + CVA/Raa strategic campaigns "
        "(dev only; backfills attribution from local feed)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pilots", type=int, default=40)
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        days = options["days"]
        pilots = options["pilots"]
        if options["reset"]:
            Campaign.objects.filter(
                slug__in=["hed-constellation", "cva-pressure"]
            ).delete()
            self.stdout.write("Removed previous Hed / CVA campaigns")

        hed = self._seed_hed(days, pilots)
        cva = self._seed_cva(days, pilots)

        self.stdout.write(
            self.style.SUCCESS(
                f"Hed FW → /campaigns/{hed.slug}/  |  "
                f"CVA strategic → /campaigns/{cva.slug}/"
            )
        )

    def _seed_hed(self, days: int, pilots: int) -> Campaign:
        now = timezone.now()
        campaign, _ = Campaign.objects.update_or_create(
            slug="hed-constellation",
            defaults={
                "short_code": "HED",
                "name": "Hed Constellation Push",
                "kind": CampaignKind.FACTION_WARFARE,
                "tagline": (
                    "Hold Amamake, Auga and Siseide — contest Dal, Vard "
                    "and Lantorn."
                ),
                "description_md": (
                    "Faction warfare focus on the Hed constellation "
                    "(Amamake, Vard, Siseide, Lantorn, Dal, Auga). Drawn from "
                    "alliance priority callouts: Hed remains top FW theatre "
                    "alongside the Bleak Lands push.\n\n"
                    "Defend the home systems, keep plexing pressure on the "
                    "contest targets, and extract Amarr killmails across the "
                    "constellation."
                ),
                "status": CampaignStatus.ACTIVE,
                "start_at": now - timedelta(days=days),
                "end_at": now + timedelta(days=21),
                "visibility": "alliance",
                "commander_order_text": (
                    "Hed priority: hold Amamake / Auga / Siseide, push "
                    "Dal–Vard–Lantorn plexes."
                ),
                "commander_order_is_draft": False,
                "commander_order_set_at": now,
            },
        )
        CampaignStandingFleet.objects.get_or_create(
            campaign=campaign,
            defaults={"advert_name": "MINMATAR FLEET · Hed Constellation"},
        )
        CampaignOpponent.objects.update_or_create(
            campaign=campaign,
            name="Amarr Militia",
            defaults={
                "ticker": "AMARR",
                "faction_id": 500003,
                "alliance_id": None,
            },
        )

        for name, system_id, goal, role, target_state in HED_SYSTEMS:
            system, _ = CampaignSystem.objects.update_or_create(
                campaign=campaign,
                solar_system_id=system_id,
                defaults={
                    "name": name,
                    "goal": goal,
                    "role": role,
                    "is_fw_objective": True,
                },
            )
            CampaignSystemArc.objects.update_or_create(
                campaign_system=system,
                defaults={
                    "target_state": target_state,
                    "due_at": campaign.end_at,
                    "contest_ceiling": 25.0,
                    "advantage_floor": 10.0,
                },
            )
            structure_service.ensure_feed_monitoring(system_id, name)

        enlisted = self._enlist(campaign, pilots, days)
        attributed = self._attribute(campaign, days)
        shifted = self._bring_activity_current(campaign)
        self._snapshots(campaign)
        self._advantage(campaign)
        sites.seed_event_codes()
        plan.propose_week(campaign)
        plan.update_week_progress(campaign)
        plan.generate_orders(campaign)
        snapshots.mirror_feed_events(campaign, hours=24 * days)
        days_written = stats.materialise_recent(campaign, days=days)
        stats.rebuild_stats(campaign)
        plan.evaluate_orders(campaign)
        totals = stats.campaign_totals(campaign)

        self.stdout.write(
            f"  Hed: {enlisted} enlisted, {attributed} mails "
            f"(shifted {shifted}), {days_written} day rows, "
            f"{totals.get('kills', 0)} kills, "
            f"{campaign.systems.count()} systems"
        )
        return campaign

    def _seed_cva(self, days: int, pilots: int) -> Campaign:
        now = timezone.now()
        campaign, _ = Campaign.objects.update_or_create(
            slug="cva-pressure",
            defaults={
                "short_code": "CVA",
                "name": "CVA Pressure",
                "kind": CampaignKind.STRATEGIC,
                "tagline": (
                    "Bash CVA's Kamela Fortizar and their allies' structures "
                    "in Raa."
                ),
                "description_md": (
                    "Strategic structure campaign against Curatores Veritatis "
                    "Alliance and friends. Theatre is the Kamela Fortizar plus "
                    "CVA / Sev3rance structures in Raa that Fleet Command has "
                    'been reinforcing ("I dunno why I still standin", '
                    '"Sacriledge Fleet is OP 5 years").\n\n'
                    "Ops theaters guide structure hunting; structure and capital "
                    "kills on reported grids still score. Ship kills in ops "
                    "systems without a campaign structure do not."
                ),
                "status": CampaignStatus.ACTIVE,
                "start_at": now - timedelta(days=days),
                "end_at": now + timedelta(days=28),
                "visibility": "alliance",
                "commander_order_text": (
                    "Raa timers + Kamela Fortizar — form for armor, bring "
                    "dreads if called."
                ),
                "commander_order_is_draft": False,
                "commander_order_set_at": now,
            },
        )
        CampaignStandingFleet.objects.get_or_create(
            campaign=campaign,
            defaults={"advert_name": "MINMATAR FLEET · CVA Pressure"},
        )

        CampaignOpponent.objects.update_or_create(
            campaign=campaign,
            alliance_id=CVA_ALLIANCE_ID,
            defaults={
                "name": "Curatores Veritatis Alliance",
                "ticker": "CVA",
            },
        )
        CampaignOpponent.objects.update_or_create(
            campaign=campaign,
            alliance_id=SEV3RANCE_ALLIANCE_ID,
            defaults={
                "name": "Sev3rance",
                "ticker": "-7-",
            },
        )

        operator = User.objects.filter(is_superuser=True).first()
        for row in CVA_STRUCTURES:
            timer = None
            if row["timer"] is not None:
                timer, _ = EveStructureTimer.objects.update_or_create(
                    name=row["name"],
                    system_name=row["system_name"],
                    type=row["structure_type"],
                    defaults={
                        "state": row["timer_state"] or "armor",
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
                alliance_id=row["alliance_id"],
                status=row["status"],
                timer=timer,
                created_by=operator,
            )

        # Devoid (10000036) covers Kamela and Raa — ops guidance, not FW.
        CampaignArea.objects.update_or_create(
            campaign=campaign,
            scope=AreaScope.REGION,
            region_id=10000036,
            defaults={"name": "Devoid", "constellation_id": None},
        )
        plan.propose_week(campaign)
        plan.update_week_progress(campaign)

        enlisted = self._enlist(campaign, pilots, days)
        attributed = self._attribute(campaign, days)
        shifted = self._bring_activity_current(campaign)
        snapshots.mirror_feed_events(campaign, hours=24 * days)
        days_written = stats.materialise_recent(campaign, days=days)
        stats.rebuild_stats(campaign)
        totals = stats.campaign_totals(campaign)

        self.stdout.write(
            f"  CVA: {enlisted} enlisted, {attributed} mails "
            f"(shifted {shifted}), {days_written} day rows, "
            f"{totals.get('kills', 0)} kills, "
            f"{campaign.structures.count()} structures, "
            f"{campaign.systems.count()} systems"
        )
        return campaign

    def _bring_activity_current(self, campaign: Campaign) -> int:
        """Slide attributed mails forward so this-week boards are not empty.

        Local feed data often lags real time. The UI defaults to the current
        campaign week, so a Sept-9 mail looks like zero activity on Sept-24.
        """
        latest = CampaignKillmail.objects.filter(campaign=campaign).aggregate(
            v=Max("killmail_time")
        )["v"]
        if not latest:
            return 0
        delta = timezone.now() - latest
        if delta <= timedelta(hours=12):
            return 0
        updated = 0
        for mail in CampaignKillmail.objects.filter(
            campaign=campaign
        ).iterator():
            mail.killmail_time = mail.killmail_time + delta
            mail.save(update_fields=["killmail_time"])
            updated += 1
        return updated

    def _snapshots(self, campaign: Campaign) -> None:
        """Pull live ESI contested/VP for campaign systems (not invented %)."""
        # Drop any leftover synthetic rows so the card shows CCP's number.
        CampaignSystemSnapshot.objects.filter(
            campaign_system__campaign=campaign
        ).delete()
        result = snapshots.record_snapshots()
        self.stdout.write(
            f"  snapshots: wrote {result.get('written', 0)} from ESI"
        )

    def _advantage(self, campaign: Campaign) -> None:
        operator = User.objects.filter(is_superuser=True).first()
        if not operator:
            return
        random.seed(7)
        for system in campaign.systems.all():
            if CampaignAdvantageReading.objects.filter(
                campaign_system=system
            ).exists():
                continue
            for _ in range(3):
                advantage.record_reading(
                    system,
                    operator,
                    our_pct=random.uniform(20, 65),
                    enemy_pct=random.uniform(5, 40),
                    source="manager",
                )
            CampaignAdvantageReading.objects.filter(
                campaign_system=system
            ).update(reported_at=timezone.now() - timedelta(hours=2))
            advantage.recompute_state(system)

    def _enlist(self, campaign: Campaign, limit: int, days: int) -> int:
        since = timezone.now() - timedelta(days=days)
        system_ids = campaign.system_ids()
        character_ids: set[int] = set()
        for attackers, victim_id in FeedKillmail.objects.filter(
            solar_system_id__in=system_ids, killmail_time__gte=since
        ).values_list("attacker_summary", "victim_character_id"):
            if victim_id:
                character_ids.add(victim_id)
            for attacker in attackers or []:
                if attacker.get("character_id"):
                    character_ids.add(attacker["character_id"])

        characters = (
            EveCharacter.objects.filter(
                character_id__in=character_ids, user__isnull=False
            )
            .select_related("user")
            .order_by("character_name")
        )
        seen_users: dict[int, User] = {}
        for character in characters:
            seen_users.setdefault(character.user_id, character.user)
            if len(seen_users) >= limit:
                break

        enlisted = 0
        for user in seen_users.values():
            enlistment, created = CampaignEnlistment.objects.get_or_create(
                campaign=campaign,
                user=user,
                defaults={"status": "active", "source": "admin"},
            )
            if not enlistment.periods.exists():
                CampaignEnlistmentPeriod.objects.create(
                    enlistment=enlistment, enlisted_at=campaign.start_at
                )
            for character in EveCharacter.objects.filter(
                user=user, esi_deleted=False
            ):
                CampaignEnlistmentCharacter.objects.get_or_create(
                    enlistment=enlistment,
                    character=character,
                    defaults={"included_from": campaign.start_at},
                )
            enlisted += int(created)

        self._personas(campaign)
        return enlisted

    def _personas(self, campaign: Campaign) -> None:
        user_ids = list(
            CampaignEnlistment.objects.filter(
                campaign=campaign, status="active"
            ).values_list("user_id", flat=True)
        )
        faced = set(
            EvePlayer.objects.filter(
                user_id__in=user_ids, primary_character__isnull=False
            ).values_list("user_id", flat=True)
        )
        faceless = [
            user
            for user in User.objects.filter(id__in=user_ids).order_by("id")
            if user.id not in faced
        ]
        spare = list(
            EveCharacter.objects.filter(user__isnull=True, esi_deleted=False)
            .exclude(character_name="")
            .order_by("character_id")[: len(faceless)]
        )
        for user, character in zip(faceless, spare):
            character.user = user
            character.save(update_fields=["user"])
            player, _ = EvePlayer.objects.get_or_create(
                user=user, defaults={"nickname": user.username}
            )
            player.primary_character = character
            player.save(update_fields=["primary_character"])
            enlistment = CampaignEnlistment.objects.get(
                campaign=campaign, user=user
            )
            CampaignEnlistmentCharacter.objects.get_or_create(
                enlistment=enlistment,
                character=character,
                defaults={"included_from": campaign.start_at},
            )

    def _attribute(self, campaign: Campaign, days: int) -> int:
        since = timezone.now() - timedelta(days=days)
        attributed = 0
        rosters: dict = {}
        for mail in FeedKillmail.objects.filter(
            solar_system_id__in=campaign.system_ids(), killmail_time__gte=since
        ).iterator():
            attributed += attribution.attribute_feed_killmail(
                mail, source="seed", rosters=rosters
            )
        return attributed
