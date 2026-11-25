"""Bring the live server in line with the published records.

Runs every few seconds and whenever Django announces a change on
``voice:changed``. Each tick:

1. Ends branches whose lease changed or went away: kicks whoever is left,
   with a message, and resets the branch. Fleet 1 is open (layout.py), so
   community members may stay in it without a lease.
2. Runs queued commands (kicks from the website).
3. For every connected pilot: refuses those who lost access, keeps their
   branch groups (fleet, commanders, capitals) in step, places them once
   per lease, and marks commanders as priority speakers where they command.

Placement state is kept per lease in Redis (``voice:placed:<lease>``,
``voice:lastchannel:<lease>``), so it resets with the branch.
"""

from __future__ import annotations

import logging

from voice_auth import layout as L

logger = logging.getLogger(__name__)

PLACED_KEY = "voice:placed:{}"
LAST_CHANNEL_KEY = "voice:lastchannel:{}"

MSG_ENDED = "This fleet's voice has ended. Thanks for flying with us."
MSG_NO_ACCESS = "You no longer have access to fleet voice. See my.minmatar.org/voice."
MSG_LOST_CHANNEL = "You no longer have access to that channel. Moved you to {}."
WHY = {
    L.COMMAND: "you're a commander of this fleet",
    L.LOGISTICS: "you're flying logistics",
    L.MAINLINE: "that's where the fleet forms",
}


def _text(value):
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


class Reconciler:
    def __init__(self, ice, store, redis, ids: L.ChannelIds, layout: L.Layout):
        self.ice = ice
        self.store = store
        self.redis = redis
        self.ids = ids
        self.layout = layout
        self.known_leases: dict[int, int] | None = None
        self.applied: dict[tuple[int, int], set[str]] = {}
        self.sessions: set[int] = set()

    # -- leases ---------------------------------------------------------

    def _current_leases(self) -> dict[int, dict]:
        return {int(b): v for b, v in (self.store.leases() or {}).items()}

    def _end_branch(self, branch: int, lease_id: int, users) -> None:
        for user in users.values():
            if self.ids.branch_of(user.channel) == branch:
                self.ice.kick(user.session, MSG_ENDED)
        self.layout.reset_branch(
            self.ids.branches[branch], self.ids.subchannels[branch], branch=branch
        )
        for key in list(self.applied):
            if key[1] == branch:
                del self.applied[key]
        self.redis.delete(
            PLACED_KEY.format(lease_id), LAST_CHANNEL_KEY.format(lease_id)
        )
        logger.info("Voice branch %s reset (lease %s ended)", branch, lease_id)

    # -- one pilot --------------------------------------------------------

    def _access(self, record, branch, leases):
        """The record's access to a branch, if it matches the live lease."""
        access = (record.get("branches") or {}).get(str(branch))
        if not access or branch not in leases:
            return None
        if access.get("lease_id") != leases[branch].get("lease_id"):
            return None
        return access

    def _sync_groups(self, user, record, leases, is_new):
        for branch, command in self.ids.branches.items():
            access = self._access(record, branch, leases)
            want = set(access["groups"]) if access else set()
            key = (user.session, branch)
            have = self.applied.get(key, set())
            for group in sorted(want - have):
                self.ice.add_group(command, user.session, group)
            for group in sorted(have - want):
                self.ice.remove_group(command, user.session, group)
            if not is_new and L.GROUP_COMMANDERS in want - have and have:
                self.ice.message(
                    user.session,
                    f"You're now a commander of {L.branch_name(branch)}.",
                )
            self.applied[key] = want

    def _guard_channel(self, user, record, leases) -> bool:
        """Move a pilot out of a channel they lost. False if kicked."""
        branch = self.ids.branch_of(user.channel)
        if branch is None:
            return True
        access = self._access(record, branch, leases)
        community = L.GROUP_COMMUNITY in (record.get("server_groups") or [])
        if access is None and community and branch == L.OPEN_BRANCH:
            # The open branch: any community member, but not in Command.
            if user.channel == self.ids.branches[branch]:
                mainline = self.ids.subchannels[branch][L.MAINLINE]
                self.ice.move(user.session, mainline)
                self.ice.message(user.session, MSG_LOST_CHANNEL.format(L.MAINLINE))
                user.channel = mainline
            return True
        if access is None:
            if community:
                self.ice.move(user.session, self.ids.lobby)
                self.ice.message(user.session, MSG_LOST_CHANNEL.format(L.LOBBY))
                user.channel = self.ids.lobby
                return True
            self.ice.kick(user.session, MSG_NO_ACCESS)
            return False
        if user.channel == self.ids.branches[branch] and not access.get("commander"):
            mainline = self.ids.subchannels[branch][L.MAINLINE]
            self.ice.move(user.session, mainline)
            self.ice.message(user.session, MSG_LOST_CHANNEL.format(L.MAINLINE))
            user.channel = mainline
        return True

    def _place(self, user, record, leases, is_new):
        branch = record.get("preferred_branch")
        access = self._access(record, branch, leases) if branch else None
        if access is None:
            return
        lease_id = access["lease_id"]
        ident = str(user.userid)
        placed_key = PLACED_KEY.format(lease_id)
        last_key = LAST_CHANNEL_KEY.format(lease_id)
        in_branch = self.ids.branch_of(user.channel)
        idle = user.channel in (self.ids.root, self.ids.lobby)

        if in_branch == branch:
            name = self.ids.name_of(branch, user.channel)
            if name:
                self.redis.hset(last_key, ident, name)
            self.redis.hset(placed_key, ident, "1")
            return
        if not idle:
            # In an Open channel or another fleet's branch: never pulled.
            return
        if _text(self.redis.hget(placed_key, ident)):
            if not is_new:
                return  # they chose Lobby themselves
            name = _text(self.redis.hget(last_key, ident)) or access["placement"]
            target = self.ids.placement_channel(branch, name)
            if name == L.COMMAND and not access.get("commander"):
                target = self.ids.subchannels[branch][L.MAINLINE]
            self.ice.move(user.session, target)
            user.channel = target
            return
        placement = access.get("placement") or L.MAINLINE
        target = self.ids.placement_channel(branch, placement)
        self.ice.move(user.session, target)
        user.channel = target
        why = WHY.get(placement, "your FC sent your wing here")
        self.ice.message(user.session, f"Moved you to {placement}: {why}. Move freely.")
        self.redis.hset(placed_key, ident, "1")
        self.redis.hset(last_key, ident, placement)

    def _priority(self, user, record, leases):
        branch = self.ids.branch_of(user.channel)
        access = self._access(record, branch, leases) if branch else None
        want = bool(access and access.get("commander"))
        if want != bool(user.priority):
            self.ice.set_priority(user.session, want)
            user.priority = want

    # -- the tick ---------------------------------------------------------

    def _end_changed_leases(self, current, users):
        if self.known_leases is None:
            return users
        ended = False
        for branch, old in self.known_leases.items():
            if old is not None and current.get(branch) != old:
                self._end_branch(branch, old, users)
                ended = True
        return self.ice.users() if ended else users

    def _run_commands(self, users):
        by_identity: dict[int, list] = {}
        for user in users.values():
            by_identity.setdefault(user.userid, []).append(user)
        for command in self.store.pop_commands():
            if command.get("action") != "kick":
                continue
            message = command.get("message") or MSG_NO_ACCESS
            for user in by_identity.get(int(command.get("identity_id", -1)), []):
                self.ice.kick(user.session, message)
                users.pop(user.session, None)

    def _reconcile_user(self, user, leases) -> None:
        is_new = user.session not in self.sessions
        if user.userid is None or user.userid < 0:
            self.ice.kick(user.session, MSG_NO_ACCESS)
            return
        record = self.store.by_identity(user.userid, fallback=False)
        if record is None:
            # Redis lost it; Django republishes within the minute. A
            # connected pilot isn't dropped for that.
            return
        if not record.get("admitted") or record.get("banned"):
            self.ice.kick(user.session, MSG_NO_ACCESS)
            return
        self._sync_groups(user, record, leases, is_new)
        if self._guard_channel(user, record, leases):
            self._place(user, record, leases, is_new)
            self._priority(user, record, leases)

    def tick(self) -> int:
        """Reconcile once. Returns the number of connected pilots."""
        leases = self._current_leases()
        current = {b: v.get("lease_id") for b, v in leases.items()}
        users = self._end_changed_leases(current, self.ice.users())
        self.known_leases = current
        self._run_commands(users)

        live = set(users)
        for key in [k for k in self.applied if k[0] not in live]:
            del self.applied[key]
        for user in users.values():
            # One pilot's failure (a record that can't be read, a session
            # that just ended) must not stop the pilots after them.
            try:
                self._reconcile_user(user, leases)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "Reconciling session %s failed; retrying next tick",
                    user.session,
                )
        self.sessions = live
        return len(users)
