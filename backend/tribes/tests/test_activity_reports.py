"""Tests for the tribe group Activity queries and their showcase highlights."""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import MagicMock, patch

import factory
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import signals as django_signals
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from applications.models import EveCorporationApplication
from creators.models import (
    CreatorAccount,
    CreatorItem,
    CreatorItemKind,
    CreatorProvider,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from eveonline.models.characters import EvePlayer
from fittings.models import (
    DOCTRINE_TYPE_NON_STRATEGIC,
    ChangeRequestStatus,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveFitting,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from groups.models import UserCommunityStatus, UserCommunityStatusHistory
from help_tickets.models import HelpRequestCategory, HelpTicket
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)
from market.models import EveMarketContract
from posts.models import EvePost
from tribes import tasks as tribe_tasks
from tribes.helpers.showcase import build_group_showcase
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
)
from tribes.reports import ReportError
from tribes.reports.period import parse_period
from tribes.reports.queries.advocates import (
    ACADEMY_CORP_ID,
    advocates_highlights,
    run_advocates_report,
)
from tribes.reports.queries.blops import blops_highlights, run_blops_report
from tribes.reports.queries.help_desk import (
    help_desk_highlights,
    run_help_desk_report,
)
from tribes.reports.queries.lp_buyback import (
    lp_buyback_highlights,
    run_lp_buyback_report,
)
from tribes.reports.queries.market_sales import (
    market_sales_highlights,
    run_market_sales_report,
)
from tribes.reports.queries.publishing import (
    publishing_highlights,
    run_publishing_report,
)
from tribes.reports.queries.readiness import run_readiness_report
from tribes.reports.registry import (
    HIGHLIGHT_RUNNERS,
    REPORT_BINDINGS,
    get_binding,
)
from tribes.reports.types import ReportScope
from users.models import UserDesktopSettings

# Every test runs at this instant. The reports bucket by calendar day, week
# and 91-day block, so fixtures stamped relative to the real clock flip
# between buckets near midnight (and a period parsed at import time goes
# stale if the suite crosses midnight before this module runs).
FROZEN_NOW = datetime(2026, 5, 13, 12, 0, tzinfo=dt_timezone.utc)
MUTED = (
    django_signals.pre_save,
    django_signals.post_save,
    django_signals.m2m_changed,
)


def _eve_type(type_id: int, name: str, group_id: int, group_name: str):
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=6,
        defaults={"name": "Ship", "last_updated": now, "published": True},
    )
    group, _ = EveGroup.objects.get_or_create(
        id=group_id,
        defaults={
            "name": group_name,
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    return EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "last_updated": now,
            "published": True,
            "eve_group": group,
        },
    )[0]


class ActivityTestCase(TestCase):
    code = ""
    group_name = ""

    @factory.django.mute_signals(*MUTED)
    def setUp(self):
        super().setUp()
        cache.clear()
        clock = patch("django.utils.timezone.now", return_value=FROZEN_NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.now = timezone.now()
        self.period = parse_period("30d")
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name=self.group_name, code=self.code
        )
        self.member, self.member_char = self._pilot("member", 5001)
        self._join(self.member)
        self.outsider, self.outsider_char = self._pilot("outsider", 5002)

    def _pilot(self, username: str, character_id: int):
        user = User.objects.create_user(username=username)
        char = EveCharacter.objects.create(
            character_id=character_id,
            character_name=username.title(),
            user=user,
        )
        EvePlayer.objects.create(
            user=user, primary_character=char, nickname=username
        )
        return user, char

    @factory.django.mute_signals(*MUTED)
    def _join(self, user):
        TribeGroupMembership.objects.create(
            tribe_group=self.group,
            user=user,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )


class RegistryTestCase(TestCase):
    def test_only_tournaments_stays_manual(self):
        manual = {c for c, b in REPORT_BINDINGS.items() if b.manual}
        self.assertEqual(manual, {"pulse.tournaments"})

    def test_highlight_keys_resolve(self):
        for code, binding in REPORT_BINDINGS.items():
            if binding.highlights:
                self.assertIn(binding.highlights, HIGHLIGHT_RUNNERS, code)

    def test_thinkspeak_showcase_covers_ninety_days(self):
        binding = get_binding("pulse.thinkspeak")
        self.assertEqual(binding.presentation["showcase"]["period"], "90d")


class MarketSalesTestCase(ActivityTestCase):
    code = "supply.market"
    group_name = "Market"

    def setUp(self):
        super().setUp()
        _eve_type(587, "Rifter", 25, "Frigate")
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Rifter",
            ship_id=587,
            description="d",
            eft_format="[Rifter, [FL33T] Rifter]\n\n",
        )
        self._contract(1, self.member_char, completed_at=self.now)
        # Public contract that vanished: no completed_at, sold via last_updated.
        self._contract(2, self.member_char, completed_at=None)
        self._contract(3, self.member_char, status="expired")
        self._contract(4, self.outsider_char, completed_at=self.now)
        self._contract(
            5,
            self.member_char,
            completed_at=self.now - timedelta(days=90),
        )

    def _contract(self, pk, char, *, status="finished", completed_at=None):
        EveMarketContract.objects.create(
            id=pk,
            title=self.fitting.name,
            price=10_000_000,
            issuer_external_id=char.character_id,
            status=status,
            fitting=self.fitting,
            issued_at=self.now - timedelta(days=2),
            completed_at=completed_at,
            last_updated=completed_at or self.now,
        )

    def test_counts_roster_sales_including_vanished_public_contracts(self):
        rows, totals, _ = run_market_sales_report(
            self.group, self.period, ReportScope.ROSTER, {}
        )
        self.assertEqual(totals["fits_sold"], 2)
        self.assertEqual(totals["confirmed_sales"], 1)
        self.assertEqual(totals["isk_sold"], 20_000_000)
        self.assertEqual(totals["fits_listed"], 4)
        self.assertEqual(totals["sellers"], 1)
        self.assertEqual(rows[0]["primary_character_name"], "Member")

    def test_highlights_group_hulls_and_count_all_time(self):
        highlights = market_sales_highlights(self.group, self.period)
        self.assertEqual(
            highlights["hulls"],
            [{"type_id": 587, "name": "Rifter", "count": 2}],
        )
        self.assertEqual(highlights["all_time"]["fits_sold"], 3)
        self.assertEqual(highlights["all_time"]["next_milestone"], 10)


class LpBuybackTestCase(ActivityTestCase):
    code = "supply.loyalty-points"
    group_name = "Loyalty Points"

    def setUp(self):
        super().setUp()
        currency = IndustryLoyaltyPoint.objects.create(
            name="TLF LP", corporation_id=9100182
        )
        sell = self._order(currency, IndustryLoyaltyPointMarketOrder.Side.SELL)
        self._order(currency, IndustryLoyaltyPointMarketOrder.Side.BUY)
        IndustryLoyaltyPointMarketOrderClaim.objects.create(
            order=sell,
            amount=100_000,
            destination_character_name="Buyer",
            claimed_by=self.member,
        )

    def _order(self, currency, side):
        order = IndustryLoyaltyPointMarketOrder.objects.create(
            loyalty_point=currency,
            side=side,
            quantity=100_000,
            isk_per_lp=700,
            status=IndustryLoyaltyPointMarketOrder.Status.COMPLETED,
            created_by=self.outsider,
        )
        IndustryLoyaltyPointMarketOrder.objects.filter(pk=order.pk).update(
            created_at=self.now - timedelta(hours=30),
            completed_at=self.now - timedelta(hours=2),
        )
        return order

    def test_counts_sells_only_and_credits_the_converter(self):
        rows, totals, _ = run_lp_buyback_report(
            self.group, self.period, ReportScope.PROGRAM, {}
        )
        self.assertEqual(totals["completed"], 1)
        self.assertEqual(totals["lp_completed"], 100_000)
        self.assertEqual(totals["isk_completed"], 70_000_000)
        self.assertEqual(totals["pilots_paid"], 1)
        self.assertEqual(totals["paid_within_day_pct"], 0)
        self.assertEqual(rows[0]["user_id"], self.member.pk)
        self.assertEqual(rows[0]["lp"], 100_000)

    def test_highlights_all_time_and_record_week(self):
        highlights = lp_buyback_highlights(self.group, self.period)
        self.assertEqual(highlights["all_time"]["lp"], 100_000)
        self.assertEqual(highlights["all_time"]["pilots"], 1)
        self.assertEqual(highlights["record_week_lp"], 100_000)
        self.assertEqual(len(highlights["weekly"]), 12)


class AdvocatesTestCase(ActivityTestCase):
    code = "pulse.advocates"
    group_name = "Advocates"

    @factory.django.mute_signals(*MUTED)
    def setUp(self):
        super().setUp()
        self.recruit, self.recruit_char = self._pilot("recruit", 5003)
        self.leaver, _ = self._pilot("leaver", 5004)
        EveCorporationApplication.objects.create(
            user=self.recruit,
            corporation_id=ACADEMY_CORP_ID,
            status="accepted",
            processed_by=self.member,
        )
        EveCorporationApplication.objects.create(
            user=self.outsider,
            corporation_id=123,
            status="accepted",
            processed_by=self.outsider,
        )
        for user, reason in (
            (self.recruit, "passed trial"),
            (self.leaver, "No longer Alliance"),
        ):
            UserCommunityStatusHistory.objects.create(
                user=user,
                from_status=UserCommunityStatus.STATUS_TRIAL,
                to_status=UserCommunityStatus.STATUS_ACTIVE,
                reason=reason,
            )
        UserCommunityStatus.objects.create(
            user=self.recruit, status=UserCommunityStatus.STATUS_ACTIVE
        )
        fleet = EveFleet.objects.create(
            audience=EveFleetAudience.objects.create(name="Fleet"),
            start_time=self.now,
            type="strategic",
            description="First fleet",
        )
        instance = EveFleetInstance.objects.create(
            id=7001, eve_fleet=fleet, start_time=self.now
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=self.recruit_char.character_id,
            character_name="Recruit",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=587,
            ship_name="Rifter",
            solar_system_id=30000142,
            solar_system_name="Jita",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(
            character_id=self.recruit_char.character_id
        ).update(join_time=self.now + timedelta(hours=1))

    def test_welcome_totals_and_roster_recruiters(self):
        rows, totals, _ = run_advocates_report(
            self.group, self.period, ReportScope.PROGRAM, {}
        )
        self.assertEqual(totals["pilots_welcomed"], 2)
        self.assertEqual(totals["academy_pilots"], 1)
        self.assertEqual(totals["full_members"], 1)
        self.assertEqual(totals["first_fleets"], 1)
        self.assertEqual(
            [(r["user_id"], r["applications_accepted"]) for r in rows],
            [(self.member.pk, 1)],
        )

    def test_highlights_wall_skips_leavers(self):
        highlights = advocates_highlights(self.group, self.period)
        self.assertEqual(
            [w["character_name"] for w in highlights["welcomed"]],
            ["Recruit"],
        )
        self.assertEqual(highlights["all_time"]["pilots_welcomed"], 2)
        self.assertEqual(highlights["all_time"]["still_flying"], 1)


class ReadinessTestCase(ActivityTestCase):
    code = "pulse.readiness"
    group_name = "Readiness"

    @factory.django.mute_signals(*MUTED)
    def setUp(self):
        super().setUp()
        fitting = EveFitting.objects.create(
            name="[FL33T] Hurricane",
            ship_id=24702,
            description="d",
            eft_format="[Hurricane, [FL33T] Hurricane]\n\n",
        )
        doctrine = EveDoctrine.objects.create(
            name="Canes",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="test",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        EveDoctrineChangeRequest.objects.create(
            doctrine=doctrine,
            status=ChangeRequestStatus.APPROVED,
            tier="minor",
            payload={},
            submitted_by=self.member,
            reviewed_by=self.outsider,
            reviewed_at=self.now,
        )
        fleet = EveFleet.objects.create(
            audience=EveFleetAudience.objects.create(name="Fleet"),
            start_time=self.now,
            type="strategic",
            description="Doctrine fleet",
            doctrine=doctrine,
        )
        instance = EveFleetInstance.objects.create(
            id=7101, eve_fleet=fleet, start_time=self.now
        )
        for char_id, last_ship, flown in (
            (6001, 670, 24702),  # died in doctrine: capsule now
            (6002, 587, None),
        ):
            member = EveFleetInstanceMember.objects.create(
                eve_fleet_instance=instance,
                character_id=char_id,
                character_name=str(char_id),
                role="squad_member",
                role_name="Squad Member",
                ship_type_id=last_ship,
                ship_name="",
                solar_system_id=30000142,
                solar_system_name="Jita",
                squad_id=1,
                wing_id=1,
            )
            if flown:
                EveFleetInstanceMemberShipSnapshot.objects.create(
                    member=member,
                    ship_type_id=flown,
                    ship_name="Hurricane",
                    solar_system_id=30000142,
                    solar_system_name="Jita",
                )

    def test_doctrine_updates_and_fleet_discipline(self):
        rows, totals, _ = run_readiness_report(
            self.group, self.period, ReportScope.PROGRAM, {}
        )
        self.assertEqual(totals["doctrine_updates"], 1)
        self.assertEqual(totals["doctrine_fleets"], 1)
        self.assertEqual(totals["flew_in_doctrine_pct"], 50)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["changes_proposed"], 1)
        self.assertEqual(rows[0]["changes_reviewed"], 0)


class HelpDeskTestCase(ActivityTestCase):
    code = "pulse.technology"
    group_name = "Technology"

    def setUp(self):
        super().setUp()
        category = HelpRequestCategory.objects.create(
            title="Report a technology bug",
            code="pulse.technology",
            tribe_group=self.group,
        )
        other = HelpRequestCategory.objects.create(
            title="Diplomats", code="pulse.diplomats"
        )
        self._ticket(1, category, closer=self.outsider, hours=4)
        self._ticket(2, category, closer=self.outsider, hours=10)
        self._ticket(3, other, closer=self.member, hours=1)
        UserDesktopSettings.objects.create(user=self.member)

    def _ticket(self, pk, category, *, closer, hours):
        ticket = HelpTicket.objects.create(
            opener_discord_id=pk,
            thread_id=pk,
            thread_name=f"ticket-{pk}",
            body="help",
            category=category,
            opener=self.member,
            status=HelpTicket.STATUS_CLOSED,
            closed_by=closer,
            closed_at=self.now,
        )
        HelpTicket.objects.filter(pk=ticket.pk).update(
            opened_at=self.now - timedelta(hours=hours)
        )

    def test_credits_every_closer_of_the_groups_tickets(self):
        rows, totals, _ = run_help_desk_report(
            self.group, self.period, ReportScope.PROGRAM, {"desktop_app": True}
        )
        self.assertEqual(totals["tickets_resolved"], 2)
        self.assertEqual(totals["median_fix_hours"], 7.0)
        self.assertEqual(totals["pilots_helped"], 2)
        self.assertEqual(totals["desktop_app_pilots"], 1)
        self.assertEqual(
            [(r["user_id"], r["tickets_resolved"]) for r in rows],
            [(self.outsider.pk, 2)],
        )

    def test_highlights_name_the_pilot_helped(self):
        highlights = help_desk_highlights(self.group, self.period)
        self.assertEqual(len(highlights["fixed"]), 2)
        self.assertEqual(highlights["fixed"][0]["pilot_name"], "Member")
        self.assertEqual(highlights["fixed"][0]["closed_by"], "Outsider")
        self.assertEqual(highlights["all_time"]["pilots_helped"], 2)


class PublishingTestCase(ActivityTestCase):
    code = "pulse.thinkspeak"
    group_name = "Thinkspeak"

    def setUp(self):
        super().setUp()
        for title, user, state in (
            ("Member post", self.member, "published"),
            ("Member draft", self.member, "draft"),
            ("Outsider post", self.outsider, "published"),
        ):
            EvePost.objects.create(
                title=title,
                state=state,
                seo_description="x",
                slug=title.lower().replace(" ", "-"),
                content="x",
                user=user,
            )
        account = CreatorAccount.objects.create(
            user=self.member,
            provider=CreatorProvider.YOUTUBE,
            platform_user_id="yt",
            access_token="tok",
        )
        CreatorItem.objects.create(
            account=account,
            provider=CreatorProvider.YOUTUBE,
            external_id="v1",
            kind=CreatorItemKind.VIDEO,
            title="Town Hall",
            url="https://youtube.com/watch?v=v1",
            published_at=self.now + timedelta(minutes=5),
        )

    def test_counts_roster_posts_and_videos(self):
        rows, totals, _ = run_publishing_report(
            self.group, self.period, ReportScope.ROSTER, {}
        )
        self.assertEqual(totals["posts_published"], 1)
        self.assertEqual(totals["videos"], 1)
        self.assertEqual(totals["writers"], 1)
        self.assertEqual(totals["creators"], 1)
        self.assertEqual(rows[0]["pieces"], 2)

    def test_latest_work_mixes_posts_and_videos_newest_first(self):
        highlights = publishing_highlights(self.group, self.period)
        self.assertEqual(
            [w["kind"] for w in highlights["latest_work"]], ["video", "post"]
        )
        self.assertEqual(highlights["latest_work"][1]["title"], "Member post")
        self.assertEqual(highlights["all_time"], {"posts": 1, "videos": 1})
        self.assertEqual(highlights["best_quarter"], 2)


class BlopsTestCase(ActivityTestCase):
    code = "pulse.fishermen"
    group_name = "Fishermen"
    sin = 22430

    def setUp(self):
        super().setUp()
        _eve_type(self.sin, "Sin", 898, "Black Ops")
        _eve_type(23913, "Nyx", 659, "Supercarrier")
        _eve_type(587, "Rifter", 25, "Frigate")
        requirement = TribeGroupRequirement.objects.create(
            tribe_group=self.group
        )
        TribeGroupRequirementAssetType.objects.create(
            requirement=requirement, eve_type_id=self.sin
        )
        self._kill(1, victim_ship=23913, days_ago=40)
        self._kill(2, victim_ship=587, days_ago=1)
        self._kill(3, victim_ship=587, days_ago=1, attacker=self.outsider_char)

    def _kill(self, pk, *, victim_ship, days_ago, attacker=None):
        attacker = attacker or self.member_char
        killmail = EveCharacterKillmail.objects.create(
            id=pk,
            killmail_id=800000 + pk,
            killmail_hash=str(pk),
            killmail_time=self.now - timedelta(days=days_ago),
            solar_system_id=30001,
            ship_type_id=victim_ship,
            victim_character_id=99999,
            victim_corporation_id=42,
            attackers="[]",
            items="[]",
            character=attacker,
        )
        EveCharacterKillmailAttacker.objects.create(
            killmail=killmail,
            character_id=attacker.character_id,
            ship_type_id=self.sin,
        )

    def test_kills_hunters_and_capital_catches(self):
        rows, totals, _ = run_blops_report(
            self.group, self.period, ReportScope.ROSTER, {}
        )
        self.assertEqual(totals["kills"], 1)
        self.assertEqual(totals["hunters"], 1)
        self.assertEqual(totals["capitals_caught_12mo"], 1)
        self.assertEqual(totals["supers_titans_all_time"], 1)
        self.assertEqual(rows[0]["kill_count"], 1)
        self.assertEqual(rows[0]["capitals_caught"], 1)

    def test_highlights_list_the_super(self):
        highlights = blops_highlights(self.group, self.period)
        self.assertEqual(len(highlights["catches"]), 1)
        catch = highlights["catches"][0]
        self.assertEqual(catch["ship_name"], "Nyx")
        self.assertEqual(catch["ship_class"], "Supercarrier")
        self.assertEqual(
            highlights["all_time"], {"titans": 0, "supers": 1, "capitals": 1}
        )


class ShowcaseTestCase(HelpDeskTestCase):
    def test_showcase_ranks_contributors_by_binding_metric(self):
        payload = build_group_showcase(self.group)
        self.assertEqual(payload["period"], "30d")
        self.assertEqual(
            [c["metric_key"] for c in payload["contributors"]],
            ["tickets_resolved"],
        )
        self.assertEqual(
            payload["contributors"][0]["values"]["tickets_resolved"], 2
        )
        self.assertIn("fixed", payload["highlights"])

    def test_guest_gets_public_highlights_only(self):
        response = Client().get(
            f"/api/tribes/{self.tribe.pk}/groups/{self.group.pk}/showcase"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["contributors"], [])
        self.assertNotIn("fixed", data["highlights"])
        self.assertIn("all_time", data["highlights"])
        self.assertEqual(data["totals"]["tickets_resolved"], 2)


class ShowcaseCacheTestCase(HelpDeskTestCase):
    """The Activity tab never runs the report inside a request."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.url = (
            f"/api/tribes/{self.tribe.pk}/groups/{self.group.pk}/showcase"
        )

    def test_cold_cache_queues_a_refresh_and_answers_warming(self):
        with patch.object(
            tribe_tasks.refresh_tribe_group_showcase, "apply_async"
        ) as queued, patch(
            "tribes.helpers.showcase.run_group_report"
        ) as run_report:
            first = Client().get(self.url)
            second = Client().get(self.url)
        run_report.assert_not_called()
        queued.assert_called_once_with(args=[self.group.pk])
        for response in (first, second):
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["warming"])
            self.assertTrue(data["manual"])
            self.assertEqual(data["totals"], {})

    def test_cache_outage_answers_warming_not_500(self):
        with patch.multiple(
            "app.cache.cache",
            get=MagicMock(side_effect=ConnectionError("redis down")),
            add=MagicMock(side_effect=ConnectionError("redis down")),
        ), patch("tribes.helpers.showcase.run_group_report") as run_report:
            response = Client().get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["warming"])
        run_report.assert_not_called()

    def test_refresh_task_fills_the_cache_the_endpoint_serves(self):
        tribe_tasks.refresh_tribe_group_showcase(self.group.pk)
        with patch("tribes.helpers.showcase.run_group_report") as run_report:
            response = Client().get(self.url)
        run_report.assert_not_called()
        data = response.json()
        self.assertFalse(data["warming"])
        self.assertEqual(data["totals"]["tickets_resolved"], 2)

    def test_warm_task_fills_the_cache(self):
        tribe_tasks.warm_tribe_group_showcases()
        self.assertIsNotNone(
            cache.get(f"tribes:showcase:v1:{self.group.pk}:30d")
        )

    def test_cached_report_error_is_a_404(self):
        with patch(
            "tribes.helpers.showcase.run_group_report",
            side_effect=ReportError("No view 'town_hall' configured"),
        ):
            tribe_tasks.refresh_tribe_group_showcase(self.group.pk)
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 404)
