"""Every access rule in voice.access."""

from datetime import timedelta

from django.utils import timezone

from campaigns.models import (
    CampaignParty,
    CampaignStatus,
    PartyKind,
    PartySide,
)
from campaigns.tests.helpers import make_campaign
from groups.helpers.feature_access import clear_feature_cache
from groups.models import UserCommunityStatus
from eveonline.models import EveCorporation
from voice import channels
from voice.access import REASON_BANNED, REASON_NO_ACCESS, voice_record
from voice.models import VoiceBan, VoiceGrant, VoiceIdentity
from voice.tests.helpers import VoiceTestCase


class StandingAccessTest(VoiceTestCase):
    def test_alliance_and_associate_join_the_community(self):
        for affiliation in ("Alliance", "Associate"):
            with self.subTest(affiliation=affiliation):
                _, character = self.pilot(f"p_{affiliation}", affiliation)
                record = voice_record(character.character_id)
                self.assertTrue(record.admitted)
                self.assertEqual(
                    record.server_groups, [channels.GROUP_COMMUNITY]
                )
                self.assertEqual(record.branches, {})

    def test_militia_guest_and_unknown_pilots_are_refused(self):
        _, militia = self.pilot("militia", "Militia")
        _, guest = self.pilot("guest", "Guest")
        for character_id in (militia.character_id, guest.character_id, 777):
            with self.subTest(character_id=character_id):
                record = voice_record(character_id)
                self.assertFalse(record.admitted)
                self.assertEqual(record.reason, REASON_NO_ACCESS)

    def test_on_leave_members_lose_community_access(self):
        user, character = self.pilot("leave", "Alliance")
        UserCommunityStatus.objects.create(user=user, status="on_leave")
        clear_feature_cache()
        self.assertFalse(voice_record(character.character_id).admitted)

    def test_ban_beats_everything(self):
        user, character = self.pilot("banned", "Alliance")
        self.join(self.fc_group, user)
        fleet = self.fleet(user)
        self.lease(fleet)
        VoiceBan.objects.create(character_id=character.character_id)
        record = voice_record(character.character_id)
        self.assertFalse(record.admitted)
        self.assertTrue(record.banned)
        self.assertEqual(record.reason, REASON_BANNED)
        self.assertEqual(record.branches, {})
        self.assertEqual(record.server_groups, [])

    def test_expired_or_lifted_bans_no_longer_apply(self):
        _, character = self.pilot("was_banned", "Alliance")
        VoiceBan.objects.create(
            character_id=character.character_id,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        VoiceBan.objects.create(
            character_id=character.character_id, lifted_at=timezone.now()
        )
        self.assertTrue(voice_record(character.character_id).admitted)

    def test_display_name_carries_the_corporation_ticker(self):
        _, character = self.pilot("O'Neil Test", "Alliance", ticker="FL33T")
        self.assertEqual(
            voice_record(character.character_id).display_name,
            "[FL33T] O'Neil Test",
        )

    def test_guest_ticker_comes_from_their_sign_in_corporation(self):
        corp = EveCorporation.objects.create(
            corporation_id=98000001, name="Guest corp", ticker="NPSI"
        )
        VoiceIdentity.objects.create(
            character_id=91234567,
            character_name="Visiting Pilot",
            corporation_id=corp.corporation_id,
        )
        self.assertEqual(
            voice_record(91234567).display_name, "[NPSI] Visiting Pilot"
        )

    def test_voice_admins_are_superusers_only_by_default(self):
        user, character = self.pilot("plain", "Alliance")
        self.assertNotIn(
            channels.GROUP_VOICEADMIN,
            voice_record(character.character_id).server_groups,
        )
        user.is_superuser = True
        user.save()
        clear_feature_cache()
        self.assertIn(
            channels.GROUP_VOICEADMIN,
            voice_record(character.character_id).server_groups,
        )


class FleetAccessTest(VoiceTestCase):
    def setUp(self):
        super().setUp()
        self.fc_user, self.fc_char = self.pilot("fc", "Alliance")
        self.fleet_ = self.fleet(self.fc_user)

    def grant(self, character, **kw):
        return VoiceGrant.objects.create(
            character_id=character.character_id, fleet=self.fleet_, **kw
        )

    def test_a_grant_counts_only_while_the_fleet_holds_a_branch(self):
        _, neutral = self.pilot("npsi neutral", user=False)
        self.grant(neutral, source=VoiceGrant.SOURCE_IN_FLEET)
        self.assertFalse(voice_record(neutral.character_id).admitted)
        self.lease(self.fleet_, branch=2)
        record = voice_record(neutral.character_id)
        self.assertTrue(record.admitted)
        self.assertEqual(list(record.branches), ["2"])
        self.assertEqual(record.branches["2"].groups, [channels.GROUP_FLEET])
        self.assertEqual(record.branches["2"].placement, channels.MAINLINE)
        self.assertEqual(record.preferred_branch, 2)
        self.assertEqual(record.server_groups, [])

    def test_expired_grants_give_nothing(self):
        _, neutral = self.pilot("gone", user=False)
        self.lease(self.fleet_)
        self.grant(
            neutral,
            source=VoiceGrant.SOURCE_IN_FLEET,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(voice_record(neutral.character_id).admitted)

    def test_commanders_sit_in_command_and_hear_capitals(self):
        self.lease(self.fleet_)
        self.grant(
            self.fc_char,
            source=VoiceGrant.SOURCE_CREATOR,
            role=VoiceGrant.ROLE_COMMANDER,
        )
        branch = voice_record(self.fc_char.character_id).branches["1"]
        self.assertEqual(
            branch.groups,
            [
                channels.GROUP_FLEET,
                channels.GROUP_COMMANDERS,
                channels.GROUP_CAPITALS,
            ],
        )
        self.assertEqual(branch.placement, channels.COMMAND)
        self.assertTrue(branch.commander)

    def test_standing_fcs_command_every_mumble_fleet(self):
        user, character = self.pilot("roaming fc", "Alliance")
        self.join(self.fc_group, user)
        self.lease(self.fleet_, branch=1)
        self.lease(self.fleet(self.fc_user), branch=3)
        record = voice_record(character.character_id)
        self.assertEqual(sorted(record.branches), ["1", "3"])
        self.assertTrue(all(b.commander for b in record.branches.values()))
        # Not part of either fleet, and two are running: they pick.
        self.assertIsNone(record.preferred_branch)

    def test_capitals_tribe_is_on_standby_in_every_branch(self):
        user, character = self.pilot("dread pilot", "Alliance")
        self.join(self.capitals_group, user)
        self.lease(self.fleet_)
        branch = voice_record(character.character_id).branches["1"]
        self.assertEqual(
            branch.groups, [channels.GROUP_FLEET, channels.GROUP_CAPITALS]
        )
        # Placement never reveals capitals.
        self.assertEqual(branch.placement, channels.MAINLINE)

    def test_placement_logistics_then_wing_mapping_then_mainline(self):
        lease = self.lease(self.fleet_)
        lease.wing_channels = {"55": channels.AUXILIARY[0]}
        lease.save()
        _, logi = self.pilot("logi", user=False)
        _, scout = self.pilot("scout", user=False)
        _, line = self.pilot("line", user=False)
        self.grant(
            logi, source=VoiceGrant.SOURCE_IN_FLEET, logistics=True, wing_id=55
        )
        self.grant(scout, source=VoiceGrant.SOURCE_IN_FLEET, wing_id=55)
        self.grant(line, source=VoiceGrant.SOURCE_IN_FLEET, wing_id=66)
        self.assertEqual(
            voice_record(logi.character_id).branches["1"].placement,
            channels.LOGISTICS,
        )
        self.assertEqual(
            voice_record(scout.character_id).branches["1"].placement,
            channels.AUXILIARY[0],
        )
        self.assertEqual(
            voice_record(line.character_id).branches["1"].placement,
            channels.MAINLINE,
        )

    def test_the_fleet_a_pilot_is_part_of_wins_placement(self):
        user, character = self.pilot("fc and pilot", "Alliance")
        self.join(self.fc_group, user)
        other = self.fleet(self.fc_user)
        self.lease(self.fleet_, branch=1)
        self.lease(other, branch=2)
        VoiceGrant.objects.create(
            character_id=character.character_id,
            fleet=other,
            source=VoiceGrant.SOURCE_VOLUNTEER,
        )
        self.assertEqual(
            voice_record(character.character_id).preferred_branch, 2
        )

    def test_campaign_allies_join_that_campaigns_fleets_only(self):
        campaign = make_campaign(status=CampaignStatus.ACTIVE)
        self.fleet_.campaign = campaign
        self.fleet_.save()
        self.lease(self.fleet_)
        _, ally = self.pilot("ally", user=False)
        _, faction_only = self.pilot("faction", user=False)
        CampaignParty.objects.create(
            campaign=campaign,
            kind=PartyKind.CHARACTER,
            side=PartySide.ALLY,
            character_id=ally.character_id,
            name="ally",
        )
        CampaignParty.objects.create(
            campaign=campaign,
            kind=PartyKind.FACTION,
            side=PartySide.ALLY,
            faction_id=500002,
            name="Minmatar Republic",
        )
        self.assertIn("1", voice_record(ally.character_id).branches)
        self.assertFalse(voice_record(faction_only.character_id).admitted)
        campaign.status = CampaignStatus.COMPLETED
        campaign.save()
        self.assertFalse(voice_record(ally.character_id).admitted)

    def test_enemy_parties_never_get_in(self):
        campaign = make_campaign(status=CampaignStatus.ACTIVE)
        self.fleet_.campaign = campaign
        self.fleet_.save()
        self.lease(self.fleet_)
        _, enemy = self.pilot("enemy", user=False)
        CampaignParty.objects.create(
            campaign=campaign,
            kind=PartyKind.CHARACTER,
            side=PartySide.ENEMY,
            character_id=enemy.character_id,
            name="enemy",
        )
        self.assertFalse(voice_record(enemy.character_id).admitted)
