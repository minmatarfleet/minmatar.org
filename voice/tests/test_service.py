"""The voice service against a fake Murmur and fake Redis.

Contract files in tests/contracts/ are written by the backend
(backend/voice/tests/test_publisher.py); these tests read them, so a
record shape change fails here as well as there.
"""

import concurrent.futures
import json
import logging
import os
import tempfile
import threading
import unittest
from pathlib import Path

from tests.fakes import Broken, FakeMurmur, FakeRedis
from voice_auth import authenticator, config, layout as L
from voice_auth.certs import CertWatcher
from voice_auth.health import Health, Watchdog
from voice_auth.main import (
    CALLBACK_ADAPTER,
    SERVER_THREADS,
    TimedProxy,
    configure_properties,
)
from voice_auth.records import (
    CERT_KEY,
    CHAR_KEY,
    COMMANDS_KEY,
    IDENTITY_KEY,
    LEASES_KEY,
    RecordStore,
    Unavailable,
)
from voice_auth.reconcile import Reconciler

CONTRACTS = Path(__file__).parent / "contracts"


def contract(name):
    return json.loads((CONTRACTS / name).read_text())


class FakeInternal:
    def __init__(self, records=None, fail=False):
        self.records = records or {}
        self.fail = fail
        self.redeemed = []

    def lookup(self, **query):
        if self.fail:
            raise Unavailable("down")
        return self.records.get(json.dumps(query, sort_keys=True))

    def redeem(self, password, cert_hash):
        if self.fail:
            raise Unavailable("down")
        self.redeemed.append((password, cert_hash))
        return self.records.get(f"token:{password}")


def publish(redis, record, certs=()):
    redis.put_json(CHAR_KEY.format(record["character_id"]), record)
    redis.set(IDENTITY_KEY.format(record["identity_id"]), str(record["character_id"]))
    for cert in certs:
        redis.set(CERT_KEY.format(cert), str(record["identity_id"]))


class ContractTest(unittest.TestCase):
    def test_channel_names_match_django(self):
        names = contract("channels.json")
        self.assertEqual(names["root"], L.ROOT)
        self.assertEqual(names["lobby"], L.LOBBY)
        self.assertEqual(names["open"], list(L.OPEN_CHANNELS))
        self.assertEqual(names["command"], L.COMMAND)
        self.assertEqual(names["branch_subchannels"], list(L.BRANCH_SUBCHANNELS))
        self.assertEqual(names["branch_names"], [L.branch_name(n) for n in (1, 2, 3)])
        self.assertEqual(names["open_branch"], L.OPEN_BRANCH)
        self.assertEqual(
            names["groups"],
            {
                "fleet": L.GROUP_FLEET,
                "commanders": L.GROUP_COMMANDERS,
                "capitals": L.GROUP_CAPITALS,
                "community": L.GROUP_COMMUNITY,
                "voiceadmin": L.GROUP_VOICEADMIN,
            },
        )
        keys = names["redis_keys"]
        self.assertEqual(keys["char"], CHAR_KEY)
        self.assertEqual(keys["identity"], IDENTITY_KEY)
        self.assertEqual(keys["cert"], CERT_KEY)
        self.assertEqual(keys["leases"], LEASES_KEY)
        self.assertEqual(keys["commands"], COMMANDS_KEY)


class AuthenticatorTest(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.record = contract("record_pilot.json")
        publish(self.redis, self.record, certs=["bound-cert"])
        self.internal = FakeInternal({"token:good": self.record})
        self.store = RecordStore(self.redis, self.internal)

    def auth(self, name="Pilot", pw="", cert=""):
        return authenticator.authenticate(name, pw, cert, self.store)

    def test_superuser_is_always_refused(self):
        self.assertEqual(self.auth("SuperUser", "good", "bound-cert").result, -1)

    def test_bound_certificate_gets_in_and_ignores_the_token(self):
        decision = self.auth(pw="spent-token", cert="bound-cert")
        self.assertEqual(decision.result, self.record["identity_id"])
        self.assertEqual(decision.name, self.record["display_name"])
        self.assertEqual(self.internal.redeemed, [])

    def test_token_redeems_and_passes_the_certificate(self):
        decision = self.auth(pw="good", cert="new-cert")
        self.assertTrue(decision.accepted)
        self.assertEqual(self.internal.redeemed, [("good", "new-cert")])

    def test_empty_hash_is_never_matched(self):
        self.redis.set(CERT_KEY.format(""), str(self.record["identity_id"]))
        self.assertEqual(self.auth(cert="").result, -1)

    def test_no_access_or_ban_refuses(self):
        for change in ({"admitted": False}, {"banned": True}):
            with self.subTest(change=change):
                publish(self.redis, {**self.record, **change}, certs=["bound-cert"])
                self.assertEqual(self.auth(cert="bound-cert").result, -1)

    def test_record_missing_and_django_down_says_try_later(self):
        store = RecordStore(Broken(), FakeInternal(fail=True))
        decision = authenticator.authenticate("Pilot", "tok", "some-cert", store)
        self.assertEqual(decision.result, -3)

    def test_unknown_token_refused(self):
        self.assertEqual(self.auth(pw="bad").result, -1)

    def test_refused_certificate_lets_a_fresh_token_move_it(self):
        # The certificate's character is no longer the account's main; the
        # new main's token may take it over (Django checks the account).
        publish(
            self.redis,
            {**self.record, "admitted": False, "reason": "not_main"},
            certs=["bound-cert"],
        )
        new_main = {**self.record, "identity_id": 7, "character_id": 7}
        self.internal.records["token:fresh"] = new_main
        decision = self.auth(pw="fresh", cert="bound-cert")
        self.assertEqual(decision.result, 7)
        self.assertEqual(self.internal.redeemed, [("fresh", "bound-cert")])

    def test_refused_certificate_stays_refused_without_a_valid_token(self):
        publish(
            self.redis,
            {**self.record, "admitted": False, "reason": "not_main"},
            certs=["bound-cert"],
        )
        decision = self.auth(pw="bad", cert="bound-cert")
        self.assertEqual(decision.result, -1)
        self.assertEqual(decision.reason, "not_main")

    def test_server_groups_come_from_the_record(self):
        commander = contract("record_commander.json")
        publish(self.redis, commander, certs=["fc-cert"])
        decision = self.auth(cert="fc-cert")
        self.assertEqual(decision.groups, ["community"])


class LayoutTest(unittest.TestCase):
    def test_layout_is_idempotent_and_never_grants_ban_or_write(self):
        murmur = FakeMurmur()
        ids = L.Layout(murmur).ensure()
        count = len(murmur.chans)
        again = L.Layout(murmur).ensure()
        self.assertEqual(len(murmur.chans), count)
        self.assertEqual(ids, again)
        self.assertEqual(count, 1 + 1 + 2 + 3 * (1 + 5))
        self.assertEqual(murmur.chans[0][0], L.ROOT)
        for rules, _, _ in murmur.acls.values():
            for rule in rules:
                self.assertFalse(rule.allow & (L.BAN | L.WRITE), rule)
        root_rules = murmur.acls[0][0]
        self.assertTrue(root_rules[0].deny & L.TEXT_MESSAGE)
        self.assertFalse(murmur.acls[0][2])  # root doesn't inherit defaults

    def test_report_whisper_is_branch_channel_only(self):
        report = [
            r
            for r in L.COMMAND_RULES
            if r.group == L.GROUP_FLEET and r.allow & L.WHISPER
        ]
        self.assertEqual(len(report), 1)
        self.assertFalse(report[0].subs)

    def test_only_the_open_branch_lets_community_in(self):
        murmur = FakeMurmur()
        ids = L.Layout(murmur).ensure()

        def community_allowed(channel_id):
            return {
                rule.allow
                for rule in murmur.acls[channel_id][0]
                if rule.group == L.GROUP_COMMUNITY
            }

        open_command = ids.branches[L.OPEN_BRANCH]
        self.assertEqual(community_allowed(open_command), {L.TRAVERSE})
        for cid in ids.subchannels[L.OPEN_BRANCH].values():
            self.assertEqual(community_allowed(cid), {L.ENTER | L.SPEAK})
        for branch in (2, 3):
            self.assertEqual(community_allowed(ids.branches[branch]), set())
            for cid in ids.subchannels[branch].values():
                self.assertEqual(community_allowed(cid), set())


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.murmur = FakeMurmur()
        self.layout = L.Layout(self.murmur)
        self.ids = self.layout.ensure()
        self.redis = FakeRedis()
        self.store = RecordStore(self.redis, FakeInternal())
        self.reconciler = Reconciler(
            self.murmur, self.store, self.redis, self.ids, self.layout
        )
        self.leases = contract("leases.json")
        self.redis.put_json(LEASES_KEY, self.leases)
        self.fc = contract("record_commander.json")
        self.pilot = {
            **contract("record_pilot.json"),
            "identity_id": 2,
            "character_id": 2,
        }
        publish(self.redis, self.fc)
        publish(self.redis, self.pilot)

    def test_first_connect_places_by_role(self):
        self.murmur.connect(10, self.fc["identity_id"], self.ids.lobby)
        self.murmur.connect(11, 2, self.ids.lobby)
        self.reconciler.tick()
        users = self.murmur.users()
        self.assertEqual(users[10].channel, self.ids.branches[1])
        self.assertEqual(users[11].channel, self.ids.subchannels[1][L.LOGISTICS])
        self.assertEqual(
            self.murmur.groups[(self.ids.branches[1], 10)],
            {"fleet", "commanders", "capitals"},
        )
        self.assertEqual(self.murmur.groups[(self.ids.branches[1], 11)], {"fleet"})
        self.assertTrue(users[10].priority)
        self.assertFalse(users[11].priority)
        self.assertTrue(
            any("Moved you to Logistics" in m for _, m in self.murmur.messages)
        )

    def test_own_moves_are_never_overridden_and_reconnect_restores(self):
        self.murmur.connect(11, 2, self.ids.lobby)
        self.reconciler.tick()
        mainline = self.ids.subchannels[1][L.MAINLINE]
        self.murmur.move(11, mainline)
        self.reconciler.tick()
        self.assertEqual(self.murmur.users()[11].channel, mainline)
        # Reconnect during the same lease: back to Mainline, not Logistics.
        self.murmur.user_map.pop(11)
        self.reconciler.tick()
        self.murmur.connect(12, 2, self.ids.lobby)
        self.reconciler.tick()
        self.assertEqual(self.murmur.users()[12].channel, mainline)

    def test_never_pulled_out_of_an_open_channel(self):
        open_1 = self.ids.open["Open 1"]
        self.murmur.connect(11, 2, open_1)
        self.reconciler.tick()
        self.assertEqual(self.murmur.users()[11].channel, open_1)

    def test_lost_access_kicks_or_moves_to_lobby(self):
        self.murmur.connect(11, 2, self.ids.lobby)
        self.reconciler.tick()
        publish(self.redis, {**self.pilot, "admitted": False, "branches": {}})
        self.reconciler.tick()
        self.assertIn(11, [s for s, _ in self.murmur.kicked])

    def test_community_stays_in_the_open_branch_without_a_fleet(self):
        member = {
            **self.pilot,
            "identity_id": 3,
            "character_id": 3,
            "branches": {},
            "preferred_branch": None,
            "server_groups": ["community"],
        }
        publish(self.redis, member)
        self.redis.put_json(LEASES_KEY, {})
        mainline = self.ids.subchannels[L.OPEN_BRANCH][L.MAINLINE]
        self.murmur.connect(30, 3, mainline)
        self.murmur.connect(31, 3, self.ids.subchannels[2][L.MAINLINE])
        self.murmur.connect(32, 3, self.ids.branches[L.OPEN_BRANCH])
        self.reconciler.tick()
        users = self.murmur.users()
        self.assertEqual(users[30].channel, mainline)
        self.assertEqual(users[31].channel, self.ids.lobby)
        self.assertEqual(users[32].channel, mainline)
        self.assertEqual(self.murmur.kicked, [])

    def test_losing_commander_moves_out_of_command(self):
        self.murmur.connect(10, self.fc["identity_id"], self.ids.lobby)
        self.reconciler.tick()
        branch = dict(self.fc["branches"]["1"], commander=False, groups=["fleet"])
        publish(self.redis, {**self.fc, "branches": {"1": branch}})
        self.reconciler.tick()
        self.assertEqual(
            self.murmur.users()[10].channel, self.ids.subchannels[1][L.MAINLINE]
        )
        self.assertFalse(self.murmur.users()[10].priority)

    def test_lease_end_kicks_the_branch_and_resets_it(self):
        self.murmur.connect(11, 2, self.ids.lobby)
        self.murmur.connect(20, self.fc["identity_id"], self.ids.lobby)
        self.reconciler.tick()
        self.redis.put_json(LEASES_KEY, {})
        self.reconciler.tick()
        self.assertEqual(sorted(s for s, _ in self.murmur.kicked), [11, 20])
        self.assertFalse(
            [
                k
                for k in self.murmur.groups
                if k[0] == self.ids.branches[1] and self.murmur.groups[k]
            ]
        )

    def test_kick_commands_from_the_website(self):
        self.murmur.connect(11, 2, self.ids.lobby)
        self.redis.rpush(
            COMMANDS_KEY,
            json.dumps({"action": "kick", "identity_id": 2, "message": "bye"}),
        )
        self.reconciler.tick()
        self.assertEqual(self.murmur.kicked, [(11, "bye")])

    def test_one_failing_pilot_does_not_stop_the_others(self):
        self.murmur.connect(10, self.fc["identity_id"], self.ids.lobby)
        self.murmur.connect(11, 2, self.ids.lobby)
        original = self.reconciler._reconcile_user
        seen = []

        def flaky(user, leases):
            seen.append(user.session)
            if user.session == 10:
                raise RuntimeError("session ended mid-tick")
            original(user, leases)

        self.reconciler._reconcile_user = flaky
        self.reconciler.tick()
        self.assertEqual(sorted(seen), [10, 11])
        self.assertEqual(
            self.murmur.users()[11].channel, self.ids.subchannels[1][L.LOGISTICS]
        )

    def test_a_missing_record_does_not_drop_a_connected_pilot(self):
        self.murmur.connect(30, 999, self.ids.lobby)
        self.reconciler.tick()
        self.assertEqual(self.murmur.kicked, [])


class CertTest(unittest.TestCase):
    def test_loads_on_start_and_on_change(self):
        murmur = FakeMurmur()
        with tempfile.TemporaryDirectory() as folder:
            cert, key = os.path.join(folder, "c.pem"), os.path.join(folder, "k.pem")
            Path(cert).write_text("CERT1")
            Path(key).write_text("KEY1")
            watcher = CertWatcher(murmur, cert, key)
            self.assertTrue(watcher.check(force=True))
            self.assertFalse(watcher.check())
            Path(cert).write_text("CERT2")
            os.utime(cert, ns=(1, 10**18))
            self.assertTrue(watcher.check())
            self.assertEqual(murmur.certificate, ("CERT2", "KEY1"))


class FakeProperties:
    def __init__(self):
        self.values = {}

    def setProperty(self, key, value):  # noqa: N802
        self.values[key] = value


class IcePropertiesTest(unittest.TestCase):
    def setUp(self):
        os.environ["VOICE_CALLBACK_HOST"] = "voice-auth"
        os.environ["VOICE_CALLBACK_PORT"] = "6503"
        self.addCleanup(os.environ.pop, "VOICE_CALLBACK_HOST", None)
        self.addCleanup(os.environ.pop, "VOICE_CALLBACK_PORT", None)

    def test_callback_adapter_listens_everywhere_and_publishes_the_service_name(self):
        # voice-auth is on two Docker networks and Murmur on one: binding to
        # the service name would listen on an address Murmur cannot reach.
        props = FakeProperties()
        configure_properties(props, config.from_env())
        self.assertEqual(
            props.values[f"{CALLBACK_ADAPTER}.Endpoints"], "tcp -h 0.0.0.0 -p 6503"
        )
        self.assertEqual(
            props.values[f"{CALLBACK_ADAPTER}.PublishedEndpoints"],
            "tcp -h voice-auth -p 6503",
        )

    def test_every_murmur_call_has_an_invocation_timeout(self):
        # Without it a Murmur that stops answering hangs the main loop
        # forever (2026-11-24).
        props = FakeProperties()
        configure_properties(props, config.from_env())
        self.assertEqual(props.values["Ice.Default.InvocationTimeout"], "10000")

    def test_invocation_timeout_is_configurable(self):
        os.environ["VOICE_ICE_TIMEOUT_MS"] = "2500"
        self.addCleanup(os.environ.pop, "VOICE_ICE_TIMEOUT_MS", None)
        props = FakeProperties()
        configure_properties(props, config.from_env())
        self.assertEqual(props.values["Ice.Default.InvocationTimeout"], "2500")

    def test_server_thread_pool_runs_more_than_one_login(self):
        props = FakeProperties()
        configure_properties(props, config.from_env())
        self.assertEqual(
            props.values["Ice.ThreadPool.Server.Size"], str(SERVER_THREADS)
        )
        self.assertEqual(
            props.values["Ice.ThreadPool.Server.SizeMax"], str(SERVER_THREADS)
        )
        self.assertGreater(SERVER_THREADS, 1)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class StallTest(unittest.TestCase):
    def healthy(self, clock):
        health = Health(stall_seconds=60, clock=clock)
        health.ice_connected = health.authenticator = health.redis_ok = True
        return health

    def test_a_ticking_loop_is_healthy(self):
        clock = FakeClock()
        health = self.healthy(clock)
        clock.now += 59
        self.assertTrue(health.healthy)
        health.tick()
        clock.now += 59
        self.assertTrue(health.healthy)
        self.assertFalse(health.payload()["stalled"])

    def test_a_stalled_loop_is_unhealthy_even_when_connected(self):
        clock = FakeClock()
        health = self.healthy(clock)
        clock.now += 61
        self.assertTrue(health.stalled)
        self.assertFalse(health.healthy)
        payload = health.payload()
        self.assertTrue(payload["stalled"])
        self.assertEqual(payload["loop_age"], 61.0)

    def test_stall_threshold_is_three_ticks_and_at_least_a_minute(self):
        self.assertEqual(config.stall_seconds_for(5), 60)
        self.assertEqual(config.stall_seconds_for(30), 90)
        self.assertEqual(config.from_env().stall_seconds, 60)

    def test_watchdog_exits_only_after_the_threshold(self):
        clock = FakeClock()
        health = self.healthy(clock)
        exits, dumps = [], []
        dog = Watchdog(health, exit_process=exits.append, dump=lambda: dumps.append(1))
        clock.now += 60
        self.assertFalse(dog.check())
        self.assertEqual(exits, [])
        clock.now += 1
        with self.assertLogs("voice_auth.health", "CRITICAL"):
            self.assertTrue(dog.check())
        self.assertEqual(exits, [1])
        self.assertEqual(dumps, [1])

    def test_watchdog_leaves_a_reconnecting_loop_alone(self):
        # Murmur down: the loop keeps failing and retrying, which is progress.
        clock = FakeClock()
        health = Health(stall_seconds=60, clock=clock)
        exits = []
        dog = Watchdog(health, exit_process=exits.append, dump=lambda: None)
        for _ in range(10):
            clock.now += 15
            health.tick()
            self.assertFalse(dog.check())
        self.assertEqual(exits, [])
        self.assertFalse(health.healthy)  # still 503: not connected


class AuthDeadlineTest(unittest.TestCase):
    def setUp(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.addCleanup(self.executor.shutdown, wait=False)

    def test_a_slow_check_answers_try_later_by_the_deadline(self):
        release = threading.Event()
        self.addCleanup(release.set)

        class SlowStore:
            def by_certificate(self, cert_hash):
                release.wait(5)

        with self.assertLogs("voice_auth.authenticator", "WARNING"):
            decision = authenticator.authenticate_within(
                "pilot", "", "abc", SlowStore(), self.executor, 0.05
            )
        self.assertEqual(decision.result, authenticator.UNAVAILABLE)

    def test_an_unexpected_error_answers_try_later(self):
        # An exception would make Murmur drop the authenticator entirely.
        class BrokenStore:
            def by_certificate(self, cert_hash):
                raise ValueError("bad record")

        with self.assertLogs("voice_auth.authenticator", "ERROR"):
            decision = authenticator.authenticate_within(
                "pilot", "", "abc", BrokenStore(), self.executor, 1
            )
        self.assertEqual(decision.result, authenticator.UNAVAILABLE)

    def test_a_quick_decision_passes_through(self):
        decision = authenticator.authenticate_within(
            "SuperUser", "", "", None, self.executor, 1
        )
        self.assertEqual(decision.result, authenticator.REFUSE)


class TimedProxyTest(unittest.TestCase):
    class Target:
        value = 3

        def getUsers(self):  # noqa: N802
            return {"a": 1}

        def fail(self):
            raise RuntimeError("timeout")

    def test_logs_each_call_at_debug(self):
        proxy = TimedProxy(self.Target())
        with self.assertLogs("voice_auth.ice", "DEBUG") as logs:
            self.assertEqual(proxy.getUsers(), {"a": 1})
            with self.assertRaises(RuntimeError):
                proxy.fail()
        self.assertEqual(len(logs.records), 4)
        self.assertIn("getUsers: start", logs.output[0])
        self.assertIn("fail: RuntimeError", logs.output[3])
        self.assertEqual(proxy.value, 3)

    def test_silent_by_default(self):
        logging.getLogger("voice_auth.ice").setLevel(logging.INFO)
        self.addCleanup(logging.getLogger("voice_auth.ice").setLevel, logging.NOTSET)
        proxy = TimedProxy(self.Target())
        self.assertEqual(proxy.getUsers.__name__, "getUsers")  # not wrapped
        self.assertEqual(proxy.getUsers(), {"a": 1})


if __name__ == "__main__":
    unittest.main()
