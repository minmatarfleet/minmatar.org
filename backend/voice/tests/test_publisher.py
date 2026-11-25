"""Records, certificates and leases published to Redis, and the contract
files the voice service (top-level voice/) tests against."""

import json

from app import contracts
from voice import channels, publisher, store
from voice.models import VoiceCertificate, VoiceGrant
from voice.tests.helpers import VoiceTestCase

SERVICE_CONTRACTS = contracts.REPO / "voice" / "tests" / "contracts"


class PublisherTest(VoiceTestCase):
    def test_only_signed_in_characters_get_a_record(self):
        _, character = self.pilot("no identity", "Alliance")
        self.assertIsNone(publisher.publish_character(character.character_id))
        self.assertIsNone(
            store.memory_store().get(
                store.CHAR_KEY.format(character.character_id)
            )
        )

    def test_record_identity_and_certificates_are_published(self):
        _, character = self.pilot("signed in", "Alliance")
        identity = self.identity(character)
        VoiceCertificate.objects.create(identity=identity, cert_hash="abc123")
        VoiceCertificate.objects.create(identity=identity, cert_hash="")
        record = publisher.publish_character(character.character_id)
        memory = store.memory_store()
        self.assertTrue(record["admitted"])
        self.assertEqual(
            json.loads(
                memory.get(store.CHAR_KEY.format(character.character_id))
            ),
            record,
        )
        self.assertEqual(
            memory.get(store.IDENTITY_KEY.format(identity.id)).decode(),
            str(character.character_id),
        )
        self.assertEqual(
            memory.get(store.CERT_KEY.format("abc123")).decode(),
            str(identity.id),
        )
        # An empty certificate hash is never published.
        self.assertIsNone(memory.get(store.CERT_KEY.format("")))
        self.assertIn(
            (store.CHANGED_CHANNEL, str(character.character_id)),
            memory.published,
        )

    def test_rebuild_after_redis_lost_its_data(self):
        _, character = self.pilot("rebuilt", "Alliance")
        self.identity(character)
        memory = store.memory_store()
        memory.set(store.CERT_KEY.format("stale"), "999")
        self.assertTrue(publisher.records_missing())
        self.assertEqual(publisher.rebuild_all(), 1)
        self.assertFalse(publisher.records_missing())
        self.assertIsNone(memory.get(store.CERT_KEY.format("stale")))
        self.assertEqual(json.loads(memory.get(store.LEASES_KEY)), {})

    def test_kick_command_is_queued(self):
        publisher.queue_kick(7, "bye")
        items = store.memory_store().lrange(store.COMMANDS_KEY, 0, -1)
        self.assertEqual(
            json.loads(items[0]),
            {"action": "kick", "identity_id": 7, "message": "bye"},
        )


class ContractTest(VoiceTestCase):
    """voice/tests/contracts/*.json: what the voice service parses.

    Regenerate with UPDATE_CONTRACTS=1 when a change is intended, and keep
    it additive: a running voice service reads what Django publishes.
    """

    def test_record_and_leases_contract(self):
        fc_user, fc_char = self.pilot(
            "Contract FC", "Alliance", ticker="FL33T"
        )
        _, logi = self.pilot("Contract Logi", user=False)
        fleet = self.fleet(fc_user)
        lease = self.lease(fleet, branch=1)
        lease.wing_channels = {"2001": channels.AUXILIARY[0]}
        lease.save()
        VoiceGrant.objects.create(
            character_id=fc_char.character_id,
            fleet=fleet,
            source=VoiceGrant.SOURCE_CREATOR,
            role=VoiceGrant.ROLE_COMMANDER,
        )
        VoiceGrant.objects.create(
            character_id=logi.character_id,
            fleet=fleet,
            source=VoiceGrant.SOURCE_IN_FLEET,
            logistics=True,
        )
        fc_identity = self.identity(fc_char)
        logi_identity = self.identity(logi)

        def stable(record, identity_id, character_id):
            record = dict(record)
            assert record["identity_id"] == identity_id
            assert record["character_id"] == character_id
            record["identity_id"] = 1
            record["character_id"] = 90000001
            for branch in record["branches"].values():
                branch["fleet_id"] = 501
                branch["lease_id"] = 601
            return record

        commander = stable(
            publisher.publish_character(fc_char.character_id),
            fc_identity.id,
            fc_char.character_id,
        )
        pilot = stable(
            publisher.publish_character(logi.character_id),
            logi_identity.id,
            logi.character_id,
        )
        leases = publisher.leases_payload()
        leases = {
            key: {**value, "fleet_id": 501, "lease_id": 601}
            for key, value in leases.items()
        }
        contracts.check(
            self, SERVICE_CONTRACTS / "record_commander.json", commander
        )
        contracts.check(self, SERVICE_CONTRACTS / "record_pilot.json", pilot)
        contracts.check(self, SERVICE_CONTRACTS / "leases.json", leases)

    def test_channel_names_contract(self):
        contracts.check(
            self,
            SERVICE_CONTRACTS / "channels.json",
            {
                "root": channels.ROOT,
                "lobby": channels.LOBBY,
                "open": list(channels.OPEN_CHANNELS),
                "command": channels.COMMAND,
                "branch_subchannels": list(channels.BRANCH_SUBCHANNELS),
                "branch_names": [channels.branch_name(n) for n in (1, 2, 3)],
                "open_branch": channels.OPEN_BRANCH,
                "groups": {
                    "fleet": channels.GROUP_FLEET,
                    "commanders": channels.GROUP_COMMANDERS,
                    "capitals": channels.GROUP_CAPITALS,
                    "community": channels.GROUP_COMMUNITY,
                    "voiceadmin": channels.GROUP_VOICEADMIN,
                },
                "redis_keys": {
                    "char": store.CHAR_KEY,
                    "identity": store.IDENTITY_KEY,
                    "cert": store.CERT_KEY,
                    "leases": store.LEASES_KEY,
                    "changed": store.CHANGED_CHANNEL,
                    "commands": store.COMMANDS_KEY,
                    "heartbeat": store.HEARTBEAT_KEY,
                },
            },
        )
