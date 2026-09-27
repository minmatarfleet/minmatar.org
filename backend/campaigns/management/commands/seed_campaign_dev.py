"""Seed a local campaign from the feed data already in the dev database.

Development only. Production campaigns are scheduled before they start and
never backfilled; this command deliberately does backfill, so that a local
machine has something to render.
"""

from __future__ import annotations

import random
from datetime import timedelta

import factory
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import signals
from django.utils import timezone

from campaigns.helpers import campaign_day
from campaigns.models import (
    Campaign,
    CampaignAdvantageReading,
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEnlistmentPeriod,
    CampaignKillmail,
    CampaignStatus,
    CampaignSystem,
    CampaignSystemArc,
    CampaignSystemSnapshot,
    KillmailOutcome,
    OperationalState,
    SystemGoal,
    SystemRole,
)
from campaigns.services import (
    advantage,
    attribution,
    fleets,
    plan,
    sites,
    snapshots,
    stats,
)
from campaigns.services.sites import attribute_payouts, contested_factor
from eveonline.models import EveCharacter, EveCharacterFwLpPayout, EvePlayer
from feed.models import FeedKillmail, FeedMonitoredSystem
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember

SYSTEMS = [
    ("Kamela", SystemGoal.TAKE, SystemRole.PRIMARY, "flip"),
    ("Kourmonen", SystemGoal.HOLD, SystemRole.PRIMARY, "hold"),
    ("Auga", SystemGoal.HOLD, SystemRole.SECONDARY, "hold"),
]

MINMATAR_FACTION_ID = 500002
AMARR_FACTION_ID = 500003


class Command(BaseCommand):
    help = "Seed a demo FW campaign from local feed data (dev only)."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="bleak-lands-push")
        parser.add_argument("--pilots", type=int, default=40)
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        slug = options["slug"]
        if options["reset"]:
            Campaign.objects.filter(slug=slug).delete()
            self.stdout.write("Removed the previous campaign")

        campaign = self._campaign(slug, options["days"])
        self._systems(campaign)
        self._snapshots(campaign)
        enlisted = self._enlist(campaign, options["pilots"], options["days"])
        self._personas(campaign)
        attributed = self._attribute(campaign, options["days"])
        self._fleets(campaign)
        self._advantage(campaign)
        sites.seed_event_codes()
        payouts = self._payouts(campaign)

        plan.propose_week(campaign)
        plan.update_week_progress(campaign)
        plan.generate_orders(campaign)
        campaign.commander_order_text = plan.draft_commander_order(campaign)
        campaign.save(update_fields=["commander_order_text"])

        snapshots.mirror_feed_events(campaign, hours=24 * options["days"])

        days_written = stats.materialise_recent(campaign, days=options["days"])
        stats.rebuild_stats(campaign)
        plan.evaluate_orders(campaign)

        totals = stats.campaign_totals(campaign)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {campaign.name}: {enlisted} pilots enlisted, "
                f"{attributed} mails attributed, {payouts} LP payouts, "
                f"{days_written} day rows, {totals['kills']} kills, "
                f"{totals['complexes']} complexes"
            )
        )
        self.stdout.write(f"Open /campaigns/{campaign.slug}/")

    def _campaign(self, slug: str, days: int) -> Campaign:
        now = timezone.now()
        campaign, _ = Campaign.objects.update_or_create(
            slug=slug,
            defaults={
                "short_code": "BLP",
                "name": "Bleak Lands Push",
                "tagline": "Take Kamela, hold the line at Kourmonen and Auga.",
                "description_md": (
                    "A six-week push into the Bleak Lands. Kamela is the "
                    "objective; Kourmonen and Auga stay ours while we take it."
                ),
                "status": CampaignStatus.ACTIVE,
                "start_at": now - timedelta(days=days),
                "end_at": now + timedelta(days=21),
                "visibility": "alliance",
            },
        )
        return campaign

    def _systems(self, campaign: Campaign):
        for name, goal, role, target_state in SYSTEMS:
            monitored = FeedMonitoredSystem.objects.filter(name=name).first()
            if not monitored:
                self.stdout.write(
                    f"  no monitored system called {name}, skipping"
                )
                continue
            system, _ = CampaignSystem.objects.update_or_create(
                campaign=campaign,
                solar_system_id=monitored.solar_system_id,
                defaults={"name": name, "goal": goal, "role": role},
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

    def _snapshots(self, campaign: Campaign):
        """A week of hourly readings so the trends on the cards have shape."""
        now = timezone.now()
        random.seed(42)
        for system in campaign.systems.all():
            if CampaignSystemSnapshot.objects.filter(
                campaign_system=system
            ).exists():
                continue
            ours = system.goal == SystemGoal.HOLD
            contested = 14.0 if ours else 38.0
            threshold = 3000
            for hours_ago in range(7 * 24, -1, -3):
                drift = random.uniform(-1.2, 1.6 if not ours else 0.9)
                contested = max(0.5, min(97.0, contested + drift))
                CampaignSystemSnapshot.objects.create(
                    campaign_system=system,
                    captured_at=now - timedelta(hours=hours_ago),
                    victory_points=int(threshold * contested / 100),
                    victory_points_threshold=threshold,
                    contested_percent=contested,
                    occupier_faction_id=(
                        MINMATAR_FACTION_ID if ours else AMARR_FACTION_ID
                    ),
                    owner_faction_id=(
                        MINMATAR_FACTION_ID if ours else AMARR_FACTION_ID
                    ),
                    contested_state="contested",
                    operational_state=OperationalState.FRONTLINE,
                )

    def _enlist(self, campaign: Campaign, limit: int, days: int) -> int:
        """Enlist the pilots who actually fought in these systems."""
        since = timezone.now() - timedelta(days=days)
        system_ids = campaign.system_ids()

        character_ids: set[int] = set()
        mails = FeedKillmail.objects.filter(
            solar_system_id__in=system_ids, killmail_time__gte=since
        ).values_list("attacker_summary", "victim_character_id")
        for attackers, victim_id in mails.iterator():
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

        return enlisted

    def _personas(self, campaign: Campaign) -> int:
        """Give every enlisted pilot a face.

        The boards show a pilot's primary character, so a synthetic pilot
        with no character would render as a bare username. The dev database
        carries real characters nobody has claimed; each faceless pilot
        adopts one as their main. No token is involved, so nothing about
        them is tracked; they only exist to be looked at.
        """
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
        if not faceless:
            return 0

        spare = list(
            EveCharacter.objects.filter(user__isnull=True, esi_deleted=False)
            .exclude(character_name="")
            .order_by("character_id")[: len(faceless)]
        )
        adopted = 0
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
            adopted += 1
        return adopted

    def _attribute(self, campaign: Campaign, days: int) -> int:
        since = timezone.now() - timedelta(days=days)
        attributed = 0
        rosters: dict = {}
        mails = FeedKillmail.objects.filter(
            solar_system_id__in=campaign.system_ids(), killmail_time__gte=since
        ).iterator()
        for mail in mails:
            attributed += attribution.attribute_feed_killmail(
                mail, source="seed", rosters=rosters
            )
        return attributed

    SEEDED_FLEET_MARK = "Seeded campaign fleet"

    def _fleets(self, campaign: Campaign) -> int:
        """Fleets that flew the fights the killmails already record.

        Take the three busiest kill hours in the campaign, put a strategic
        fleet up around each one led by the pilot with the most kills, seat
        every enlisted pilot who was on those mails in it, and let the real
        fleet linker attach the kills. The Fleets tab then shows pilots and
        ISK the way it would after a real op.
        """
        if campaign.fleets.filter(description=self.SEEDED_FLEET_MARK).exists():
            return 0

        mails = list(
            CampaignKillmail.objects.filter(
                campaign=campaign, outcome=KillmailOutcome.KILL
            ).prefetch_related("participants")
        )
        if not mails:
            return 0

        by_hour: dict = {}
        for mail in mails:
            hour = mail.killmail_time.replace(
                minute=0, second=0, microsecond=0
            )
            by_hour.setdefault(hour, []).append(mail)
        busiest = sorted(by_hour.items(), key=lambda item: -len(item[1]))[:3]

        created = 0
        for index, (hour, hour_mails) in enumerate(busiest):
            pilots: dict = {}
            for mail in hour_mails:
                for participant in mail.participants.all():
                    if participant.role == "attacker" and participant.user_id:
                        pilots.setdefault(participant.user_id, set()).add(
                            participant.character_id
                        )
            if not pilots:
                continue
            leader_id = max(pilots.items(), key=lambda item: len(item[1]))[0]
            start = hour - timedelta(minutes=30)
            end = hour + timedelta(hours=2)

            with factory.django.mute_signals(
                signals.pre_save, signals.post_save
            ):
                fleet = EveFleet.objects.create(
                    type="strategic",
                    description=self.SEEDED_FLEET_MARK,
                    objective=f"{campaign.name} op {index + 1}",
                    start_time=start,
                    status="complete",
                    campaign=campaign,
                    created_by_id=leader_id,
                )
            instance = EveFleetInstance.objects.create(
                id=900_000_000 + fleet.id, eve_fleet=fleet, end_time=end
            )
            EveFleetInstance.objects.filter(pk=instance.pk).update(
                start_time=start, last_updated=end
            )
            names = dict(
                EveCharacter.objects.filter(
                    character_id__in=[
                        cid for cids in pilots.values() for cid in cids
                    ]
                ).values_list("character_id", "character_name")
            )
            system = hour_mails[0].solar_system_id
            for cids in pilots.values():
                for character_id in cids:
                    member = EveFleetInstanceMember.objects.create(
                        eve_fleet_instance=instance,
                        character_id=character_id,
                        character_name=names.get(character_id, ""),
                        role="squad_member",
                        role_name="Squad Member",
                        ship_type_id=587,
                        ship_name="Rifter",
                        solar_system_id=system,
                        solar_system_name="",
                        squad_id=1,
                        wing_id=1,
                    )
                    EveFleetInstanceMember.objects.filter(pk=member.pk).update(
                        join_time=start, updated_at=end
                    )
            fleets.link_killmails_to_fleets(campaign, campaign_day(hour))
            created += 1
        return created

    def _advantage(self, campaign: Campaign):
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

    def _payouts(self, campaign: Campaign) -> int:
        """Synthetic LP payout notifications.

        The dev database has no character notifications, so nothing would
        exercise site attribution or complex-class inference. These rows are
        shaped exactly like the real ``FacWarLPPayout`` notifications, with
        amounts taken from the observed live pull: complexes at several base
        tiers, advantage sites at a flat 10,000 and one supply cache at
        15,000.
        """
        characters = list(
            CampaignEnlistmentCharacter.objects.filter(
                enlistment__campaign=campaign
            ).select_related("character")[:25]
        )
        if not characters:
            return 0

        systems = list(campaign.systems.all())
        if not systems:
            return 0

        random.seed(11)
        now = timezone.now()
        created = 0
        notification_id = 900_000_000
        site_ref = 5_000_000

        # A complex capture is one site instance, shared between the pilots
        # who were inside it, which is what makes the split count recoverable.
        for index in range(60):
            system = random.choice(systems)
            base = random.choice([10_000, 15_000, 20_000, 25_000, 30_000])
            inside = random.choice([1, 1, 1, 2, 3])
            occurred_at = now - timedelta(
                hours=random.uniform(0, 24 * 10), minutes=random.uniform(0, 59)
            )
            # Derive the amount from the contested reading that the inference
            # will later read back, so the seeded data is self-consistent and
            # the class actually comes out of the algorithm.
            contested = contested_factor(system, occurred_at)
            share = int(base * 1.5 * contested / inside)
            site_ref += 1

            for slot in range(inside):
                row = characters[(index * 3 + slot) % len(characters)]
                notification_id += 1
                EveCharacterFwLpPayout.objects.update_or_create(
                    notification_id=notification_id,
                    defaults={
                        "character": row.character,
                        "notification_type": "FacWarLPPayoutEvent",
                        "occurred_at": occurred_at,
                        "amount_lp": share,
                        "corp_id": 1000182,
                        "event_code": 371,
                        "location_id": system.solar_system_id,
                        "ref_id": site_ref,
                        "char_ref_id": row.character.character_id,
                    },
                )
                created += 1

        # Advantage sites pay a flat 10,000 to the pilot who ran them.
        for index in range(35):
            row = characters[index % len(characters)]
            system = random.choice(systems)
            notification_id += 1
            EveCharacterFwLpPayout.objects.update_or_create(
                notification_id=notification_id,
                defaults={
                    "character": row.character,
                    "notification_type": "FacWarLPPayoutEvent",
                    "occurred_at": now
                    - timedelta(hours=random.uniform(0, 24 * 10)),
                    "amount_lp": 10_000 if index % 7 else 15_000,
                    "corp_id": 1000182,
                    "event_code": 516,
                    "location_id": system.solar_system_id,
                },
            )
            created += 1

        payouts = EveCharacterFwLpPayout.objects.filter(
            location_id__in=campaign.system_ids()
        ).select_related("character")
        attribute_payouts(payouts)
        sites.build_complex_completions(since_hours=24 * 30)
        return created
