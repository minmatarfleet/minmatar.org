"""Entry point: connect to Murmur over Ice, register the authenticator,
lay out the channels, and reconcile until stopped.

Everything Ice-specific lives here; the logic it drives (authenticator,
layout, reconcile, certs) is plain Python and tested with fakes.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass

from voice_auth import authenticator, config, health as health_mod
from voice_auth.certs import CertWatcher
from voice_auth.layout import Layout
from voice_auth.reconcile import Reconciler
from voice_auth.records import CHANGED_CHANNEL, InternalClient, RecordStore

logger = logging.getLogger("voice_auth")

SLICE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MumbleServer.ice")


@dataclass
class UserState:
    session: int
    userid: int
    channel: int
    name: str
    priority: bool


def load_slice():
    import Ice  # pylint: disable=import-outside-toplevel,import-error

    # Ubuntu's zeroc-ice-slice puts the includes here; getSliceDir() is None.
    slice_dir = Ice.getSliceDir() or "/usr/share/ice/slice"
    Ice.loadSlice("", ["-I" + slice_dir, SLICE])
    import MumbleServer  # pylint: disable=import-outside-toplevel,import-error

    return Ice, MumbleServer


class IceServer:
    """The few Murmur calls the logic needs, over one server proxy."""

    def __init__(self, server, MumbleServer):  # noqa: N803
        self.server = server
        self.M = MumbleServer

    def users(self):
        return {
            session: UserState(
                session=u.session,
                userid=u.userid,
                channel=u.channel,
                name=u.name,
                priority=u.prioritySpeaker,
            )
            for session, u in self.server.getUsers().items()
        }

    def channels(self):
        return {cid: (c.name, c.parent) for cid, c in self.server.getChannels().items()}

    def rename_channel(self, channel_id, name):
        state = self.server.getChannelState(channel_id)
        state.name = name
        self.server.setChannelState(state)

    def add_channel(self, name, parent):
        return self.server.addChannel(name, parent)

    def set_acl(self, channel_id, rules, groups, inherit):
        acls = [
            self.M.ACL(
                applyHere=r.here,
                applySubs=r.subs,
                inherited=False,
                userid=-1,
                group=r.group,
                allow=r.allow,
                deny=r.deny,
            )
            for r in rules
        ]
        group_list = [
            self.M.Group(
                name=g,
                inherited=False,
                inherit=True,
                inheritable=True,
                add=[],
                remove=[],
                members=[],
            )
            for g in groups
        ]
        self.server.setACL(channel_id, acls, group_list, inherit)

    # A pilot can disconnect between getUsers() and any call for them:
    # Murmur then raises InvalidSessionException, which is nothing to do.

    def move(self, session, channel_id):
        try:
            state = self.server.getState(session)
            state.channel = channel_id
            self.server.setState(state)
        except self.M.InvalidSessionException:
            pass

    def set_priority(self, session, value):
        try:
            state = self.server.getState(session)
            state.prioritySpeaker = bool(value)
            self.server.setState(state)
        except self.M.InvalidSessionException:
            pass

    def kick(self, session, reason):
        try:
            self.server.kickUser(session, reason)
        except self.M.InvalidSessionException:
            pass

    def message(self, session, text):
        try:
            self.server.sendMessage(session, text)
        except self.M.InvalidSessionException:
            pass

    def add_group(self, channel_id, session, group):
        try:
            self.server.addUserToGroup(channel_id, session, group)
        except self.M.InvalidSessionException:
            pass

    def remove_group(self, channel_id, session, group):
        try:
            self.server.removeUserFromGroup(channel_id, session, group)
        except self.M.InvalidSessionException:
            pass

    def update_certificate(self, cert, key):
        self.server.updateCertificate(cert, key, "")


CALLBACK_ADAPTER = "Callback.Client"


def configure_properties(props, cfg: config.Config) -> None:
    """Set the Ice properties for the Murmur connection and the callback adapter.

    The callback adapter listens on every interface but publishes
    cfg.callback_host in its proxies. voice-auth sits on two Docker networks
    and voice-murmur on only one; binding to the service name would listen on
    whichever address it resolves to inside this container, which Murmur may
    not be able to reach (setAuthenticator then raises
    InvalidCallbackException). Murmur resolves the published name on the
    network it shares with us.
    """
    props.setProperty("Ice.ImplicitContext", "Shared")
    props.setProperty("Ice.Default.EncodingVersion", "1.0")
    props.setProperty("Ice.MessageSizeMax", "65536")
    props.setProperty(
        f"{CALLBACK_ADAPTER}.Endpoints", f"tcp -h 0.0.0.0 -p {cfg.callback_port}"
    )
    props.setProperty(
        f"{CALLBACK_ADAPTER}.PublishedEndpoints",
        f"tcp -h {cfg.callback_host} -p {cfg.callback_port}",
    )


def make_authenticator_servant(MumbleServer, store, health):  # noqa: N803
    class Authenticator(MumbleServer.ServerAuthenticator):
        def authenticate(  # pylint: disable=too-many-arguments
            self, name, pw, certificates, certhash, certstrong, current=None
        ):
            decision = authenticator.authenticate(name, pw, certhash, store)
            logger.info(
                "Voice login %s (%s)",
                "accepted" if decision.accepted else "refused",
                decision.reason,
            )
            return decision.as_ice()

        def getInfo(self, id, current=None):  # noqa: N802,A002
            return False, {}

        def nameToId(self, name, current=None):  # noqa: N802
            return -2

        def idToName(self, id, current=None):  # noqa: N802,A002
            return ""

        def idToTexture(self, id, current=None):  # noqa: N802,A002
            return []

    return Authenticator()


def _listen_for_changes(redis, wake: threading.Event):
    while True:
        try:
            pubsub = redis.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(CHANGED_CHANNEL)
            for _ in pubsub.listen():
                wake.set()
        except Exception:  # pylint: disable=broad-exception-caught
            time.sleep(5)


def run(cfg: config.Config) -> None:  # pragma: no cover - needs Murmur
    import redis as redis_lib  # pylint: disable=import-outside-toplevel,import-error

    Ice, MumbleServer = load_slice()  # noqa: N806
    redis = redis_lib.Redis.from_url(cfg.redis_url, socket_timeout=5)
    store = RecordStore(redis, InternalClient(cfg.internal_url, cfg.internal_secret))
    health = health_mod.Health()
    health_mod.serve(health, cfg.health_port)
    wake = threading.Event()
    threading.Thread(
        target=_listen_for_changes, args=(redis, wake), daemon=True
    ).start()

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    while not stop.is_set():
        props = Ice.createProperties()
        configure_properties(props, cfg)
        init = Ice.InitializationData()
        init.properties = props
        communicator = Ice.initialize(init)
        try:
            communicator.getImplicitContext().put("secret", cfg.ice_secret)
            meta = MumbleServer.MetaPrx.checkedCast(
                communicator.stringToProxy(
                    f"Meta:tcp -h {cfg.ice_host} -p {cfg.ice_port}"
                )
            )
            adapter = communicator.createObjectAdapter(CALLBACK_ADAPTER)
            adapter.activate()
            server = meta.getServer(cfg.server_id)
            servant = make_authenticator_servant(MumbleServer, store, health)
            proxy = MumbleServer.ServerAuthenticatorPrx.uncheckedCast(
                adapter.addWithUUID(servant)
            )
            server.setAuthenticator(proxy)
            health.ice_connected = True
            health.authenticator = True
            ice = IceServer(server, MumbleServer)
            layout = Layout(ice)
            ids = layout.ensure()
            certs = CertWatcher(ice, cfg.cert_file, cfg.key_file)
            certs.check(force=True)
            reconciler = Reconciler(ice, store, redis, ids, layout)
            logger.info("Voice service connected; authenticator registered")
            while not stop.is_set():
                health.sessions = reconciler.tick()
                health.beat(redis)
                certs.check()
                wake.wait(cfg.tick_seconds)
                wake.clear()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Lost the voice server; reconnecting in 5 s")
            health.ice_connected = False
            health.authenticator = False
            health.beat(redis)
            stop.wait(5)
        finally:
            communicator.destroy()


def main() -> int:  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = config.from_env()
    if cfg.sentry_dsn:
        import sentry_sdk  # pylint: disable=import-outside-toplevel,import-error

        sentry_sdk.init(dsn=cfg.sentry_dsn, send_default_pii=False)
    run(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
