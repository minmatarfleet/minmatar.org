import random
from collections import Counter
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from app.test import TestCase
from discord.models import DiscordUser
from django.contrib.auth.models import User
from eveonline.models import EveCharacter, EveCorporation
from reddit import rotation, schedule
from reddit.admin import SlotForm
from reddit.corporation_posts import post_settings
from reddit.models import (
    RedditPost,
    RedditPostTemplate,
    RedditSchedule,
    RedditScheduleChange,
)
from reddit.rotation import Member

UTC = dt_timezone.utc
NOVEMBER = date(2026, 11, 1)
# Before November is published on the 24th.
OCT_20 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

HIGH = [Member(1, 2), Member(2, 2), Member(3, 2)]
NORMAL = [Member(i, 1) for i in range(4, 10)]
NINE = HIGH + NORMAL


def gaps_ok(times: list[datetime]) -> bool:
    times = sorted(times)
    return all(b - a >= rotation.COOLDOWN for a, b in zip(times, times[1:]))


class SlotTestCase(TestCase):
    def test_slots_are_two_days_apart_across_months(self):
        october = rotation.slot_dates(date(2026, 10, 1))
        november = rotation.slot_dates(NOVEMBER)
        days = october + november
        self.assertEqual(date(2026, 10, 1), october[0])
        self.assertEqual(date(2026, 11, 2), november[0])
        self.assertEqual(
            {timedelta(days=2)}, {b - a for a, b in zip(days, days[1:])}
        )
        self.assertEqual(15, len(november))

    def test_slot_time_is_fixed_and_inside_its_window(self):
        for day in rotation.slot_dates(NOVEMBER):
            for window, (start, length) in rotation.WINDOWS.items():
                at = rotation.slot_time(day, window)
                self.assertEqual(at, rotation.slot_time(day, window))
                opens = datetime.combine(day, start, tzinfo=UTC)
                self.assertLessEqual(opens, at)
                self.assertLess(at, opens + length)
                self.assertEqual(0, at.minute % 5)

    def test_times_spread_from_downtime_to_us_evening(self):
        hours = {
            rotation.slot_time(day).hour
            for month in (NOVEMBER, date(2026, 12, 1), date(2027, 1, 1))
            for day in rotation.slot_dates(month)
        }
        self.assertTrue(hours & {11, 12, 13})
        self.assertTrue(hours & {22, 23, 0, 1})


class QuotaTestCase(TestCase):
    def test_shares_add_up_and_follow_weight(self):
        quota = rotation.quotas(NINE, 15, {})
        self.assertEqual(15, sum(quota.values()))
        for high in HIGH:
            for normal in NORMAL:
                self.assertGreater(quota[high.id], quota[normal.id])

    def test_owed_slots_carry_over(self):
        even = rotation.quotas(NORMAL, 12, {})
        self.assertEqual({2}, set(even.values()))
        owed = rotation.quotas(NORMAL, 12, {4: 1.0, 5: -1.0})
        self.assertEqual(3, owed[4])
        self.assertEqual(1, owed[5])
        self.assertEqual(12, sum(owed.values()))

    def test_no_one_gets_more_than_the_cooldown_allows(self):
        quota = rotation.quotas([Member(1, 2), Member(2, 1)], 15, {})
        self.assertEqual(4, rotation.max_posts(15))
        self.assertEqual({1: 4, 2: 4}, quota)


class PlanTestCase(TestCase):
    def plan_months(self, members, months=12, changes=None):
        history: dict[int, list[datetime]] = {}
        earlier = []
        totals = Counter()
        month = NOVEMBER
        for index in range(months):
            if changes and index in changes:
                members = changes[index](members)
            days = rotation.slot_dates(month)
            carry = rotation.carry_from(earlier[-3:], {m.id for m in members})
            quota = rotation.quotas(members, len(days), carry)
            assigned = rotation.plan(days, members, quota, history)
            got = Counter(assigned.values())
            earlier.append(({m.id: m.weight for m in members}, got))
            totals += got
            windows = {m.id: m.window for m in members}
            for day, i in assigned.items():
                history.setdefault(i, []).append(
                    rotation.slot_time(day, windows[i])
                )
            month = rotation.next_month(month)
        return totals, history

    def test_everyone_gets_their_weighted_share(self):
        totals, _ = self.plan_months(NINE)
        slots = sum(totals.values())
        for m in NINE:
            share = slots * m.weight / sum(x.weight for x in NINE)
            self.assertLessEqual(abs(totals[m.id] - share), 1.5, m)

    def test_never_twice_within_a_week(self):
        members = NINE[:4] + [Member(20, 1, rotation.US)]
        _, history = self.plan_months(members)
        for times in history.values():
            self.assertTrue(gaps_ok(times))

    def test_corporation_added_later_is_not_flooded(self):
        totals, history = self.plan_months(
            NINE, changes={6: lambda ms: ms + [Member(50, 1)]}
        )
        self.assertTrue(gaps_ok(history[50]))
        # Six months at a normal share, with no catching up on the first six.
        share = 6 * 15 / (sum(m.weight for m in NINE) + 1)
        self.assertLessEqual(abs(totals[50] - share), 1.5)

    def test_every_slot_is_used_while_anyone_is_clear(self):
        # Corp 5 has a post just after these days, so only the first one is
        # clear for it; when it misses that, the last slot still goes to
        # someone instead of standing empty.
        days = rotation.slot_dates(NOVEMBER)[:5]
        members = [Member(i, 1) for i in range(1, 6)]
        soon = rotation.slot_time(days[-1]) + timedelta(days=1)
        history = {5: [soon]}
        quota = {m.id: 1 for m in members}
        assigned = rotation.plan(days, members, quota, history)
        self.assertEqual(days, list(assigned))
        self.assertNotIn(5, assigned.values())
        for i in set(assigned.values()):
            times = [
                rotation.slot_time(d) for d, j in assigned.items() if j == i
            ]
            self.assertTrue(gaps_ok(times))

    def test_same_inputs_same_plan(self):
        days = rotation.slot_dates(NOVEMBER)
        quota = rotation.quotas(NINE, len(days), {})
        first = rotation.plan(days, NINE, quota, {})
        self.assertEqual(first, rotation.plan(days, NINE, quota, {}))
        self.assertEqual(
            first, rotation.plan(days, NINE, quota, {}, previous=first)
        )

    def test_one_change_moves_few_slots(self):
        rng = random.Random(7)
        days = rotation.slot_dates(NOVEMBER)
        moved = []
        for _ in range(200):
            carry = {m.id: rng.uniform(-1, 1) for m in NINE}
            quota = rotation.quotas(NINE, len(days), carry)
            before = rotation.plan(days, NINE, quota, {})
            members = list(NINE)
            kind = rng.choice(["priority", "add", "pause"])
            if kind == "priority":
                i = rng.randrange(len(members))
                m = members[i]
                members[i] = Member(m.id, 3 - m.weight)
            elif kind == "add":
                members.append(Member(99, 1))
            else:
                members.pop(rng.randrange(len(members)))
            quota = rotation.quotas(members, len(days), carry)
            after = rotation.plan(days, members, quota, {}, previous=before)
            moved.append(sum(before.get(d) != after.get(d) for d in days))
        self.assertLessEqual(max(moved), 3)
        self.assertLess(sum(moved) / len(moved), 2)

    def test_fingerprint_ignores_order_and_follows_inputs(self):
        days = rotation.slot_dates(NOVEMBER)
        base = rotation.fingerprint(NOVEMBER, days, NINE, {}, {})
        self.assertEqual(
            base,
            rotation.fingerprint(NOVEMBER, days, NINE[::-1], {}, {}),
        )
        changed = [Member(1, 1)] + NINE[1:]
        self.assertNotEqual(
            base, rotation.fingerprint(NOVEMBER, days, changed, {}, {})
        )


@patch("reddit.scheduling.DiscordClient")
class ScheduleTestCase(TestCase):
    """Drafts, publishing and changes against the database."""

    def setUp(self):
        super().setUp()
        self.templates = [
            self.make_template(98100000 + i, priority)
            for i, priority in enumerate(["high"] * 3 + ["normal"] * 6)
        ]

    def make_template(self, corporation_id, priority="normal", ceo=False):
        corporation = EveCorporation.objects.create(
            corporation_id=corporation_id, name=f"Corp {corporation_id}"
        )
        if ceo:
            user = User.objects.create(username=f"ceo-{corporation_id}")
            corporation.ceo = EveCharacter.objects.create(
                character_id=corporation_id + 1,
                character_name=f"CEO {corporation_id}",
                user=user,
            )
            corporation.save()
            DiscordUser.objects.create(
                id=corporation_id, discord_tag="ceo", user=user
            )
        return RedditPostTemplate.objects.create(
            corporation=corporation,
            title=f"Join {corporation_id}",
            content="We fly.",
            priority=priority,
        )

    def november(self):
        return RedditSchedule.objects.get(month=NOVEMBER)

    def slots(self, month=NOVEMBER):
        return {
            post.slot_date: post.template_id
            for post in RedditPost.objects.filter(schedule__month=month)
        }

    def dm_texts(self, discord):
        return [c.kwargs["message"] for c in discord().send_dm.call_args_list]

    def test_drafts_this_month_and_next(self, discord):
        schedule.refresh_drafts(OCT_20)
        november = self.november()
        self.assertEqual(RedditSchedule.DRAFT, november.status)
        slots = self.slots()
        self.assertEqual(15, len(slots))
        got = Counter(slots.values())
        high = {t.pk for t in self.templates[:3]}
        self.assertTrue(
            min(got[i] for i in high)
            > max(got[t.pk] for t in self.templates[3:])
        )
        october = self.slots(date(2026, 10, 1))
        self.assertTrue(october)
        self.assertTrue(all(day > OCT_20.date() for day in october))
        self.assertTrue(
            all(p.status == RedditPost.DRAFT for p in RedditPost.objects.all())
        )
        discord().send_dm.assert_not_called()

    def test_draft_holds_still_until_an_input_changes(self, discord):
        schedule.refresh_drafts(OCT_20)
        first = self.november().generated_at
        rows = set(RedditPost.objects.values_list("pk", "template_id"))
        later = OCT_20 + timedelta(hours=6)
        schedule.refresh_drafts(later)
        self.assertEqual(first, self.november().generated_at)
        # Words aren't a scheduling input.
        self.templates[0].content = "New words"
        self.templates[0].save()
        schedule.refresh_drafts(later)
        self.assertEqual(first, self.november().generated_at)
        self.assertEqual(
            rows, set(RedditPost.objects.values_list("pk", "template_id"))
        )

    def test_priority_change_moves_a_few_slots_and_says_why(self, discord):
        schedule.refresh_drafts(OCT_20)
        before = self.slots()
        promoted = self.templates[5]
        promoted.priority = "high"
        promoted.save()
        schedule.refresh_drafts(OCT_20 + timedelta(hours=1))
        after = self.slots()
        moved = [d for d in before if before[d] != after.get(d)]
        self.assertTrue(1 <= len(moved) <= 3)
        self.assertGreater(
            Counter(after.values())[promoted.pk],
            Counter(before.values())[promoted.pk],
        )
        change = RedditScheduleChange.objects.filter(
            schedule=self.november()
        ).first()
        self.assertEqual(RedditScheduleChange.ROTATION, change.reason)
        self.assertIn("set to high priority", change.detail)

    def test_paused_post_leaves_the_draft(self, discord):
        schedule.refresh_drafts(OCT_20)
        paused = self.templates[0]
        lost = {d for d, i in self.slots().items() if i == paused.pk}
        paused.paused = True
        paused.save()
        schedule.refresh_drafts(OCT_20 + timedelta(hours=1))
        self.assertNotIn(paused.pk, self.slots().values())
        recorded = set(
            RedditScheduleChange.objects.filter(
                schedule=self.november(), from_template=paused
            ).values_list("slot_date", flat=True)
        )
        self.assertEqual(lost, recorded)

    def test_publishing_confirms_without_dms(self, discord):
        ceo_template = self.make_template(98200000, ceo=True)
        schedule.refresh_drafts(OCT_20)
        november = self.november()
        mine = [
            p.scheduled_for
            for p in november.slots.filter(template=ceo_template)
        ]
        self.assertTrue(mine)
        schedule.publish(november, OCT_20)
        november.refresh_from_db()
        self.assertTrue(november.is_published)
        self.assertEqual(
            {RedditPost.CONFIRMED},
            set(november.slots.values_list("status", flat=True)),
        )
        self.assertEqual([], self.dm_texts(discord))

        # Published months only move by hand.
        before = self.slots()
        self.templates[4].priority = "high"
        self.templates[4].save()
        schedule.refresh_drafts(OCT_20 + timedelta(hours=1))
        self.assertEqual(before, self.slots())

    def test_publishing_drops_slots_without_notice(self, discord):
        now = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
        schedule.refresh_drafts(now)
        november = self.november()
        schedule.publish(november, now)
        first = november.slots.order_by("scheduled_for").first()
        self.assertGreaterEqual(first.scheduled_for - now, schedule.MIN_NOTICE)

    def test_next_month_publishes_on_the_24th(self, discord):
        day_23 = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
        schedule.refresh_drafts(day_23)
        self.assertEqual([], schedule.publish_due(day_23))
        published = schedule.publish_due(day_23 + timedelta(days=1))
        self.assertEqual([NOVEMBER], [s.month for s in published])
        # October predates the rotation going live; an admin publishes it.
        october = RedditSchedule.objects.get(month=date(2026, 10, 1))
        self.assertEqual(RedditSchedule.DRAFT, october.status)

    def test_paused_corporation_hands_its_slot_on(self, discord):
        schedule.refresh_drafts(OCT_20)
        schedule.publish(self.november(), OCT_20)
        leaver = self.templates[3]
        slot = (
            RedditPost.objects.filter(
                template=leaver, schedule__month=NOVEMBER
            )
            .order_by("scheduled_for")
            .first()
        )
        leaver.paused = True
        leaver.save()

        self.assertEqual(
            len(self.slots()), len(self.slots())
        )  # nothing moves until the scheduler runs
        schedule.reconcile_published(OCT_20)
        slot.refresh_from_db()
        self.assertNotEqual(leaver.pk, slot.template_id)
        self.assertEqual(RedditPost.CONFIRMED, slot.status)
        times = list(
            RedditPost.objects.filter(
                template_id=slot.template_id,
                status__in=schedule.LIVE_STATUSES,
            ).values_list("scheduled_for", flat=True)
        )
        self.assertTrue(gaps_ok(times))
        change = RedditScheduleChange.objects.get(slot_date=slot.slot_date)
        self.assertEqual(RedditScheduleChange.PAUSED, change.reason)

    def test_slot_too_close_to_hand_on_is_skipped(self, discord):
        schedule.refresh_drafts(OCT_20)
        schedule.publish(self.november(), OCT_20)
        slot = (
            RedditPost.objects.filter(schedule__month=NOVEMBER)
            .order_by("scheduled_for")
            .first()
        )
        slot.template.paused = True
        slot.template.save()
        schedule.reconcile_published(slot.scheduled_for - timedelta(hours=5))
        slot.refresh_from_db()
        self.assertEqual(RedditPost.SKIPPED, slot.status)
        self.assertEqual("paused", slot.fallback_reason)

    def test_heads_up_the_day_before_once(self, discord):
        template = self.make_template(98200001, ceo=True)
        when = OCT_20 + timedelta(hours=20)
        RedditPost.objects.create(
            template=template,
            slot_date=when.date(),
            scheduled_for=when,
            status=RedditPost.CONFIRMED,
        )
        self.assertEqual(1, schedule.send_heads_ups(OCT_20))
        self.assertEqual(
            0, schedule.send_heads_ups(OCT_20 + timedelta(hours=1))
        )
        (message,) = self.dm_texts(discord)
        self.assertIn("Reddit post tomorrow", message)

    @patch("reddit.scheduling.deliver", return_value="reminded")
    def test_two_months_of_runs(self, deliver_mock, discord):
        now = OCT_20
        end = datetime(2027, 1, 1, 6, 0, tzinfo=UTC)
        while now < end:
            schedule.run(now)
            now += timedelta(hours=3)
        delivered = [c.args[1] for c in deliver_mock.call_args_list]
        self.assertEqual(len(delivered), len({post.pk for post in delivered}))
        by_template: dict[int, list[datetime]] = {}
        for post in delivered:
            by_template.setdefault(post.template_id, []).append(
                post.scheduled_for
            )
        self.assertEqual(9, len(by_template))
        for times in by_template.values():
            self.assertTrue(gaps_ok(times))
        delivered_days = sorted(p.slot_date for p in delivered)
        # November and December went out in full, one slot every two days.
        self.assertEqual(
            rotation.slot_dates(NOVEMBER)
            + rotation.slot_dates(date(2026, 12, 1)),
            [d for d in delivered_days if NOVEMBER <= d < date(2027, 1, 1)],
        )

    def test_ceo_sees_confirmed_dates_then_estimates(self, discord):
        template = self.templates[0]
        schedule.refresh_drafts(OCT_20)
        schedule.publish(self.november(), OCT_20)
        schedule.refresh_drafts(OCT_20)
        with patch(
            "reddit.corporation_posts.timezone.now", return_value=OCT_20
        ):
            data = post_settings(template.corporation, self.user)
        upcoming = data["upcoming"]
        self.assertTrue(any(u["confirmed"] for u in upcoming))
        self.assertEqual(
            sorted(u["scheduled_for"] for u in upcoming),
            [u["scheduled_for"] for u in upcoming],
        )
        self.assertEqual(12, data["interval_days"])
        self.assertEqual("high", data["priority"])

    def test_ceo_sees_slots_gained_and_lost(self, discord):
        schedule.refresh_drafts(OCT_20)
        promoted = self.templates[6]
        promoted.priority = "high"
        promoted.save()
        schedule.refresh_drafts(OCT_20 + timedelta(hours=1))
        changes = schedule.recent_changes(
            promoted, OCT_20 + timedelta(hours=2)
        )
        self.assertTrue(any(c["gained"] for c in changes))

    def test_admin_cannot_break_the_cooldown(self, discord):
        schedule.refresh_drafts(OCT_20)
        schedule.publish(self.november(), OCT_20)
        posts = list(
            RedditPost.objects.filter(schedule__month=NOVEMBER).order_by(
                "scheduled_for"
            )
        )
        first, second = posts[0], posts[1]
        form = SlotForm(
            data={
                "template": first.template_id,
                "scheduled_for": second.scheduled_for.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            },
            instance=second,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("at least 7 days apart", str(form.errors))

    def test_admin_move_tells_both_ceos(self, discord):
        giver = self.make_template(98200002, ceo=True)
        taker = self.make_template(98200003, ceo=True)
        when = OCT_20 + timedelta(days=5)
        post = RedditPost.objects.create(
            template=giver,
            slot_date=when.date(),
            scheduled_for=when,
            status=RedditPost.CONFIRMED,
        )
        post.template = taker
        post.save()
        schedule.move_slot(post, taker, when, giver, when)
        texts = self.dm_texts(discord)
        self.assertEqual(2, len(texts))
        self.assertIn("moved your", texts[0])
        self.assertIn("Extra Reddit slot", texts[1])
