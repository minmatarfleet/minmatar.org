"""A fake Murmur (the IceServer surface) and a fake Redis for tests."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.lists = {}
        self.hashes = {}

    def get(self, key):
        value = self.data.get(key)
        return None if value is None else value.encode()

    def set(self, key, value, ex=None):  # pylint: disable=unused-argument
        self.data[key] = value if isinstance(value, str) else str(value)

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)

    def lpop(self, key):
        items = self.lists.get(key) or []
        return items.pop(0).encode() if items else None

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def hget(self, key, field):
        value = self.hashes.get(key, {}).get(field)
        return None if value is None else value.encode()

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = str(value)

    def keys(self, pattern="*"):
        return [k for k in self.data if fnmatch.fnmatch(k, pattern)]

    def put_json(self, key, value):
        self.set(key, json.dumps(value))


class Broken:
    """A Redis that is down."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ConnectionError("redis down")

        return fail


@dataclass
class FakeUser:
    session: int
    userid: int
    channel: int
    name: str = ""
    priority: bool = False


class FakeMurmur:
    def __init__(self):
        self.next_id = 1
        self.chans = {0: ("Root", -1)}
        self.acls = {}
        self.groups = {}  # (channel, session) -> set
        self.user_map: dict[int, FakeUser] = {}
        self.kicked = []
        self.messages = []
        self.moves = []
        self.certificate = None

    # layout surface
    def channels(self):
        return dict(self.chans)

    def rename_channel(self, channel_id, name):
        self.chans[channel_id] = (name, self.chans[channel_id][1])

    def add_channel(self, name, parent):
        cid = self.next_id
        self.next_id += 1
        self.chans[cid] = (name, parent)
        return cid

    def set_acl(self, channel_id, rules, groups, inherit):
        self.acls[channel_id] = (tuple(rules), tuple(groups), inherit)
        for key in [k for k in self.groups if k[0] == channel_id]:
            del self.groups[key]  # temporary members reset with the ACL

    # reconcile surface
    def users(self):
        return {s: FakeUser(**vars(u)) for s, u in self.user_map.items()}

    def connect(self, session, userid, channel):
        self.user_map[session] = FakeUser(session, userid, channel)

    def move(self, session, channel_id):
        self.user_map[session].channel = channel_id
        self.moves.append((session, channel_id))

    def set_priority(self, session, value):
        self.user_map[session].priority = value

    def kick(self, session, reason):
        self.kicked.append((session, reason))
        self.user_map.pop(session, None)

    def message(self, session, text):
        self.messages.append((session, text))

    def add_group(self, channel_id, session, group):
        self.groups.setdefault((channel_id, session), set()).add(group)

    def remove_group(self, channel_id, session, group):
        self.groups.get((channel_id, session), set()).discard(group)

    def update_certificate(self, cert, key):
        self.certificate = (cert, key)
