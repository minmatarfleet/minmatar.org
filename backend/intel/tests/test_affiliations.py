from collections import Counter
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCharacter
from intel.affiliations import investigate as investigate_module
from intel.affiliations import resolve, score, sightings
from intel.affiliations.investigate import count_month, investigate
from intel.models import (
    IntelAffiliation,
    IntelBloc,
    IntelCoAttack,
    IntelEntity,
    IntelReport,
    IntelSampleMonth,
)
from intel.services import local as local_service

from .test_api import fake_esi, grant
from app.testing import auth_headers

MAIN = 99000001  # the big alliance
PET = 99000002  # leans on MAIN
RIVAL = 99000003  # third-parties MAIN's fights
MILITIA = 500003
TODAY = date(2026, 10, 20)
MONTHS = score.window(TODAY)

Kind = IntelEntity.Kind
Status = IntelAffiliation.Status


def attacker(alliance=None, corporation=98000001, character=None, **extra):
    return {
        "alliance_id": alliance,
        "corporation_id": corporation,
        "character_id": character,
        **extra,
    }


def kill(*attackers, victim=None):
    return {
        "attackers": list(attackers),
        "victim": victim or attacker(alliance=12345, character=1),
    }


def group(eve_id, kind=Kind.ALLIANCE, status=IntelEntity.Status.DONE, **kw):
    return IntelEntity.objects.create(
        kind=kind, eve_id=eve_id, name=f"Group {eve_id}", status=status, **kw
    )


def evidence(entity, kills_per_month, months, partners):
    """``partners``: {(kind, id): (shared, militia, against)} per month."""
    for month in months:
        IntelSampleMonth.objects.create(
            entity=entity, month=month, kills=kills_per_month, complete=True
        )
        for (kind, eve_id), (shared, militia, against) in partners.items():
            IntelCoAttack.objects.create(
                entity=entity,
                month=month,
                partner_kind=kind,
                partner_id=eve_id,
                shared=shared,
                militia_shared=militia,
                against=against,
            )


class CountMonthTests(TestCase):
    def test_counts_partners_characters_militia_and_losses(self):
        subject = (Kind.ALLIANCE, MAIN)
        kills = [
            kill(
                attacker(MAIN, character=10, faction_id=MILITIA),
                attacker(PET, character=20, faction_id=MILITIA),
                attacker(None, corporation=1000182, character=30),
            ),
            kill(attacker(MAIN, character=10), attacker(PET, character=20)),
            # Not on the mail: zKill can list a corp's old alliance mails.
            kill(attacker(RIVAL, character=40)),
            # A blob: everyone is on it.
            kill(*[attacker(MAIN, character=10)] * 61),
        ]
        losses = [
            kill(
                attacker(RIVAL, character=40),
                attacker(RIVAL, character=41),
                victim=attacker(MAIN, character=10),
            )
        ]
        count = count_month(subject, kills, losses)
        self.assertEqual(count.kills, 2)
        self.assertEqual(count.losses, 1)
        self.assertEqual(count.shared[(Kind.ALLIANCE, PET)], 2)
        self.assertEqual(count.militia_shared[(Kind.ALLIANCE, PET)], 1)
        # NPC corporations are not groups, but their pilots still count.
        self.assertNotIn((Kind.CORPORATION, 1000182), count.shared)
        self.assertEqual(count.shared[(Kind.CHARACTER, 30)], 1)
        self.assertIsNone(count.character_groups[30])
        self.assertEqual(count.character_groups[20], PET)
        self.assertEqual(count.against, Counter({(Kind.ALLIANCE, RIVAL): 1}))

    def test_a_corporation_inside_an_alliance(self):
        corp = (Kind.CORPORATION, 98000050)
        kills = [
            kill(
                attacker(PET, corporation=98000050, character=1),
                attacker(PET, corporation=98000051, character=2),
                attacker(MAIN, character=3),
            )
        ]
        count = count_month(corp, kills, [])
        self.assertEqual(count.kills, 1)
        # Its own alliance and alliance-mates are not partners.
        self.assertEqual(
            set(count.shared),
            {(Kind.ALLIANCE, MAIN), (Kind.CHARACTER, 3)},
        )


class InvestigateTests(TestCase):
    def setUp(self):
        self.entity = group(MAIN, status=IntelEntity.Status.QUEUED)
        self.fetched = []

        def fake_fetch(kind, eve_id, month, sleep_seconds):
            self.fetched.append(month)
            kills = [
                kill(attacker(MAIN, character=10), attacker(PET, character=2))
            ] * 3
            return kills, []

        self.patches = [
            patch.object(
                investigate_module, "fetch_month", side_effect=fake_fetch
            ),
            patch.object(investigate_module, "_refresh_profile"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_reads_each_finished_month_once(self):
        investigate(self.entity, today=TODAY, sleep_seconds=0)
        self.assertEqual(len(self.fetched), len(MONTHS))
        self.entity.refresh_from_db()
        self.assertEqual(self.entity.status, IntelEntity.Status.DONE)
        row = IntelCoAttack.objects.get(
            entity=self.entity, month=MONTHS[0], partner_id=PET
        )
        self.assertEqual(row.shared, 3)
        self.assertFalse(
            IntelSampleMonth.objects.get(
                entity=self.entity, month=MONTHS[0]
            ).complete
        )

        self.fetched.clear()
        investigate(self.entity, today=TODAY, sleep_seconds=0)
        # Only this month is read again; the finished ones never change.
        self.assertEqual(self.fetched, [MONTHS[0]])
        self.assertEqual(
            IntelCoAttack.objects.filter(
                entity=self.entity, month=MONTHS[0], partner_id=PET
            ).count(),
            1,
        )

    def test_zkill_down_keeps_what_was_read(self):
        calls = {"n": 0}

        def flaky(kind, eve_id, month, sleep_seconds):
            calls["n"] += 1
            if calls["n"] > 2:
                raise investigate_module.ZkillUnavailable("down")
            return [kill(attacker(MAIN, character=10))], []

        with patch.object(
            investigate_module, "fetch_month", side_effect=flaky
        ):
            stats = investigate(self.entity, today=TODAY, sleep_seconds=0)
        self.assertEqual(stats["failed"], 1)
        self.entity.refresh_from_db()
        self.assertEqual(self.entity.status, IntelEntity.Status.FAILED)
        self.assertEqual(
            IntelSampleMonth.objects.filter(entity=self.entity).count(), 2
        )


class ScoreTests(TestCase):
    def setUp(self):
        cache.clear()
        self.main = group(MAIN)
        self.pet = group(PET)
        months = MONTHS[:6]
        # The pet has MAIN on 25 of its 40 kills a month; MAIN has the pet
        # on 25 of its 400.
        evidence(self.pet, 40, months, {(Kind.ALLIANCE, MAIN): (25, 0, 0)})
        evidence(self.main, 400, months, {(Kind.ALLIANCE, PET): (25, 0, 0)})

    def test_suggests_a_pet_in_a_bloc_named_after_the_main(self):
        row = score.score_group(self.pet, MONTHS)
        self.assertEqual(row.relation, IntelAffiliation.Relation.PET)
        self.assertEqual(row.status, Status.SUGGESTED)
        self.assertEqual(row.bloc.anchor, self.main)
        self.assertEqual(row.bloc.name, "Group 99000001")
        self.assertEqual(row.evidence["months_together"], 6)
        self.assertAlmostEqual(row.evidence["share"], 0.625)
        self.assertEqual(row.last_month, MONTHS[0])
        # The main itself leans on nobody.
        self.assertIsNone(score.score_group(self.main, MONTHS))

    def test_a_recent_lean_is_not_diluted_by_older_months(self):
        # A year before they met: lots of kills, none together.
        for month in MONTHS[12:24]:
            IntelSampleMonth.objects.create(
                entity=self.pet, month=month, kills=200, complete=True
            )
        row = score.score_group(self.pet, MONTHS)
        self.assertEqual(row.evidence["months_sampled"], 12)
        self.assertAlmostEqual(row.evidence["share"], 0.625)

    def test_a_rejection_sticks(self):
        row = score.score_group(self.pet, MONTHS)
        row.status = Status.REJECTED
        row.save()
        self.assertIsNone(score.score_group(self.pet, MONTHS))
        row.refresh_from_db()
        self.assertEqual(row.status, Status.REJECTED)
        score.score_all(TODAY)
        self.assertTrue(IntelBloc.objects.filter(pk=row.bloc_id).exists())
        self.assertEqual(
            IntelAffiliation.objects.get(pk=row.pk).status, Status.REJECTED
        )

    def test_kills_against_each_other_lower_then_rule_it_out(self):
        clean = score.score_group(self.pet, MONTHS).confidence
        # 18 of 150 shared: lowsec brawls happen, so only less sure.
        IntelCoAttack.objects.filter(entity=self.main).update(against=3)
        self.assertLess(score.score_group(self.pet, MONTHS).confidence, clean)
        # 36 of 150: they fight each other; not a pet.
        IntelCoAttack.objects.filter(entity=self.main).update(against=6)
        self.assertIsNone(score.score_group(self.pet, MONTHS))

    def test_militia_allies_are_not_pets(self):
        IntelCoAttack.objects.filter(entity=self.pet).update(militia_shared=20)
        self.assertIsNone(score.score_group(self.pet, MONTHS))

    def test_waits_for_the_partners_own_history(self):
        self.main.status = IntelEntity.Status.NEW
        self.main.save()
        self.assertIsNone(score.score_group(self.pet, MONTHS))
        self.main.refresh_from_db()
        self.assertEqual(self.main.status, IntelEntity.Status.QUEUED)

    def test_equal_partners_are_allies(self):
        IntelSampleMonth.objects.filter(entity=self.main).update(kills=50)
        row = score.score_group(self.pet, MONTHS)
        self.assertEqual(row.relation, IntelAffiliation.Relation.ALLY)

    def test_associates_and_endings(self):
        score.score_group(self.pet, MONTHS)
        ours = User.objects.create(username="member")
        EveCharacter.objects.create(
            character_id=777, character_name="Ours", user=ours
        )
        for month in MONTHS[:4]:
            for character, group_id in ((555, None), (777, None), (20, PET)):
                IntelCoAttack.objects.create(
                    entity=self.main,
                    month=month,
                    partner_kind=Kind.CHARACTER,
                    partner_id=character,
                    partner_group=group_id,
                    shared=3,
                )
        with patch.object(score, "names_for", return_value={555: "Alt Pilot"}):
            stats = score.score_all(TODAY)
        # 555 flies with the bloc from an NPC corp; 20 is in the pet (already
        # in the bloc) and 777 is one of ours (see the members check).
        self.assertEqual(stats["associates"], 1)
        associate = IntelAffiliation.objects.get(entity__eve_id=555)
        self.assertEqual(associate.relation, "associate")
        self.assertEqual(associate.entity.name, "Alt Pilot")

        # Nothing new for six months: the inferred rows end.
        later = date(2027, 12, 1)
        score.end_stale(score.window(later))
        self.assertTrue(IntelAffiliation.objects.get(pk=associate.pk).ended)

    def test_queue_partners_reaches_small_pets(self):
        other = 99000009
        evidence(
            self.main, 0, MONTHS[10:12], {(Kind.ALLIANCE, other): (5, 0, 0)}
        )
        score.queue_partners(self.main, MONTHS)
        self.assertEqual(
            IntelEntity.objects.get(eve_id=other).status,
            IntelEntity.Status.QUEUED,
        )


class ResolveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.main = group(MAIN)
        self.bloc = IntelBloc.objects.create(
            name="Main Bloc", anchor=self.main
        )

    def affiliate(self, kind, eve_id, status=Status.SUGGESTED, **kw):
        entity, _ = IntelEntity.objects.get_or_create(kind=kind, eve_id=eve_id)
        return IntelAffiliation.objects.create(
            entity=entity,
            bloc=self.bloc,
            relation="pet",
            status=status,
            confidence=0.7,
            **kw,
        )

    def test_anchor_shows_once_the_bloc_has_a_member(self):
        self.assertIsNone(resolve.bloc_for(alliance_id=MAIN))
        self.affiliate(Kind.ALLIANCE, PET)
        resolve.invalidate()
        self.assertEqual(
            resolve.bloc_for(alliance_id=MAIN)["relation"], "anchor"
        )
        pet = resolve.bloc_for(alliance_id=PET)
        self.assertEqual(pet["name"], "Main Bloc")
        self.assertEqual(resolve.public_entry(pet)["likely"], True)
        self.assertIsNone(
            resolve.bloc_for(alliance_id=PET, confirmed_only=True)
        )

    def test_pilot_beats_corp_beats_alliance(self):
        other = IntelBloc.objects.create(name="Other", manual=True)
        self.affiliate(Kind.CHARACTER, 42, status=Status.CONFIRMED)
        IntelAffiliation.objects.create(
            entity=group(98000005, kind=Kind.CORPORATION),
            bloc=other,
            relation="pet",
            status=Status.CONFIRMED,
        )
        resolve.invalidate()
        self.assertEqual(
            resolve.bloc_for(
                character_id=42, corporation_id=98000005, alliance_id=RIVAL
            )["name"],
            "Main Bloc",
        )
        self.assertEqual(
            resolve.bloc_for(
                character_id=43, corporation_id=98000005, alliance_id=MAIN
            )["name"],
            "Other",
        )

    def test_rejected_and_ended_rows_do_not_resolve(self):
        self.affiliate(Kind.ALLIANCE, PET, status=Status.REJECTED)
        self.affiliate(Kind.ALLIANCE, RIVAL, ended=True)
        resolve.invalidate()
        self.assertIsNone(resolve.bloc_for(alliance_id=PET))
        self.assertIsNone(resolve.bloc_for(alliance_id=RIVAL))
        self.assertIsNone(resolve.bloc_for(alliance_id=MAIN))


class SightingsTests(TestCase):
    def test_queues_after_enough_sightings_and_requeues_stale(self):
        key = (Kind.ALLIANCE, MAIN)
        sightings.note_sightings(Counter({key: 1}))
        entity = IntelEntity.objects.get(eve_id=MAIN)
        self.assertEqual(entity.status, IntelEntity.Status.NEW)
        sightings.note_sightings(Counter({key: 2}))
        entity.refresh_from_db()
        self.assertEqual(entity.sightings, 3)
        self.assertEqual(entity.status, IntelEntity.Status.QUEUED)

        entity.status = IntelEntity.Status.DONE
        entity.investigated_at = timezone.now() - timedelta(days=40)
        entity.save()
        sightings.note_sightings(Counter({key: 1}))
        entity.refresh_from_db()
        self.assertEqual(entity.status, IntelEntity.Status.QUEUED)

    def test_local_reports_queue_their_groups_at_once(self):
        IntelReport.objects.create(
            kind=IntelReport.Kind.LOCAL,
            raw="x",
            summary={
                "alliances": [{"id": MAIN}, {"id": None}],
                "corporations": [{"id": 98000007}],
            },
        )
        stats = sightings.collect()
        self.assertEqual(stats["queued"], 2)
        self.assertEqual(
            IntelEntity.objects.get(eve_id=98000007).kind, Kind.CORPORATION
        )


class LocalBlocTests(TestCase):
    def setUp(self):
        cache.clear()
        main = group(MAIN)
        bloc = IntelBloc.objects.create(name="Snuffed Bloc", anchor=main)
        IntelAffiliation.objects.create(
            entity=group(PET),
            bloc=bloc,
            relation="pet",
            status=Status.SUGGESTED,
        )
        IntelAffiliation.objects.create(
            entity=IntelEntity.objects.create(kind=Kind.CHARACTER, eve_id=13),
            bloc=bloc,
            relation="associate",
            status=Status.CONFIRMED,
        )

    def test_local_groups_pilots_into_blocs(self):
        patches, _ = fake_esi(
            ids={"a": 11, "b": 12, "c": 13, "d": 14},
            affiliations={
                11: {"corporation_id": 1, "alliance_id": MAIN},
                12: {"corporation_id": 2, "alliance_id": PET},
                13: {"corporation_id": 1000182, "alliance_id": None},
                14: {"corporation_id": 98000020, "alliance_id": None},
            },
            names={MAIN: "Main", PET: "Pet", 98000020: "Loners"},
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        summary = local_service.summarize_local(["a", "b", "c", "d"])
        bloc = summary["blocs"][0]
        self.assertEqual(bloc["name"], "Snuffed Bloc")
        self.assertEqual(bloc["count"], 3)
        self.assertFalse(bloc["likely"])
        likely = {g["id"]: g["likely"] for g in bloc["groups"]}
        self.assertEqual(likely, {MAIN: False, PET: True, 1000182: False})
        rows = {row["id"]: row for row in summary["alliances"]}
        self.assertEqual(rows[PET]["bloc"]["likely"], True)
        self.assertIsNone(rows[None]["bloc"])
        corporations = {row["id"]: row for row in summary["corporations"]}
        self.assertEqual(corporations[98000020]["name"], "Loners")


class AffiliationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create(username="intel")
        grant(self.user, "change_intelaffiliation")
        self.headers = auth_headers(self.user)
        self.main = group(MAIN)
        self.pet = group(PET)
        evidence(
            self.pet,
            40,
            score.window()[:6],
            {(Kind.ALLIANCE, MAIN): (25, 0, 0)},
        )
        evidence(
            self.main,
            400,
            score.window()[:6],
            {(Kind.ALLIANCE, PET): (25, 0, 0)},
        )
        self.row = score.score_group(self.pet, score.window())

    def get(self, path):
        return self.client.get(f"/api/intel{path}", **self.headers)

    def send(self, method, path, body):
        return getattr(self.client, method)(
            f"/api/intel{path}",
            body,
            content_type="application/json",
            **self.headers,
        )

    def test_needs_the_feature(self):
        outsider = User.objects.create(username="pilot")
        response = self.client.get(
            "/api/intel/affiliations/review", **auth_headers(outsider)
        )
        self.assertEqual(response.status_code, 403)

    def test_review_confirm_and_profile(self):
        review = self.get("/affiliations/review").json()
        self.assertEqual(review["suggestions"][0]["entity"]["id"], PET)
        self.assertEqual(review["queue"]["investigated"], 2)

        response = self.send(
            "post",
            f"/affiliations/{self.row.id}/decision",
            {"status": "confirmed", "relation": "alt", "note": "same CEO"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["relation"], "alt")
        self.assertEqual(
            resolve.bloc_for(alliance_id=PET)["status"], "confirmed"
        )

        profile = self.get(f"/entities/alliance/{PET}").json()
        self.assertEqual(profile["kills_sampled"], 240)
        self.assertEqual(profile["partners"][0]["id"], MAIN)
        self.assertEqual(profile["partners"][0]["share"], 0.625)
        self.assertEqual(profile["bloc"]["name"], "Group 99000001")

        blocs = self.get("/blocs").json()["blocs"]
        self.assertEqual(blocs[0]["groups"], 1)

    def test_manual_affiliation_rename_and_merge(self):
        response = self.send(
            "post",
            "/affiliations",
            {
                "kind": "alliance",
                "eve_id": RIVAL,
                "new_bloc_name": "Rivals",
                "relation": "member",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        rivals = response.json()["bloc"]["id"]
        renamed = self.send(
            "patch", f"/blocs/{self.row.bloc_id}", {"name": "Snuffed Out"}
        )
        self.assertEqual(renamed.json()["name"], "Snuffed Out")
        merged = self.send(
            "post",
            f"/blocs/{rivals}/merge",
            {"into_bloc_id": self.row.bloc_id},
        )
        self.assertEqual(merged.status_code, 200, merged.content)
        self.assertEqual(
            resolve.bloc_for(alliance_id=RIVAL)["name"], "Snuffed Out"
        )
        self.assertFalse(IntelBloc.objects.filter(pk=rivals).exists())

    def test_investigate_now_jumps_the_queue(self):
        response = self.send(
            "post", "/entities/corporation/98000099/investigate", {}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "queued")
        self.assertEqual(response.json()["priority"], 100)

    def test_members_flying_with_another_bloc(self):
        member = User.objects.create(username="member")
        EveCharacter.objects.create(
            character_id=777, character_name="Ours", user=member
        )
        for month in score.window()[:4]:
            IntelCoAttack.objects.create(
                entity=self.main,
                month=month,
                partner_kind=Kind.CHARACTER,
                partner_id=777,
                shared=3,
            )
        rows = self.get("/affiliations/members").json()["members"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["character_name"], "Ours")
        self.assertEqual(rows[0]["shared"], 12)
        self.assertEqual(rows[0]["bloc"]["name"], "Group 99000001")
