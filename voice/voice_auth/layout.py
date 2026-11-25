"""The channel tree and its ACLs (design section 3), applied idempotently.

Minmatar Fleet (root)
├─ Lobby          default channel; community members not in a fleet
├─ Open 1, Open 2 informal fleets: any community member
└─ Fleet 1..3     Command; Mainline, Logistics, Auxiliary A-C below.
                  Fleet 1 is open: any community member may enter its
                  subchannels; Fleet 2 and 3 are for their fleet only.

Nobody gets Ban or Write: Ban shows pilots' IP addresses. Text is off.
"""

from __future__ import annotations

from dataclasses import dataclass

ROOT = "Minmatar Fleet"
LOBBY = "Lobby"
OPEN_CHANNELS = ("Open 1", "Open 2")
COMMAND = "Command"
MAINLINE = "Mainline"
LOGISTICS = "Logistics"
AUXILIARY = ("Auxiliary A", "Auxiliary B", "Auxiliary C")
BRANCH_SUBCHANNELS = (MAINLINE, LOGISTICS, *AUXILIARY)
BRANCH_COUNT = 3
OPEN_BRANCH = 1

GROUP_ALL = "all"
GROUP_FLEET = "fleet"
GROUP_COMMANDERS = "commanders"
GROUP_CAPITALS = "capitals"
GROUP_COMMUNITY = "community"
GROUP_VOICEADMIN = "voiceadmin"
BRANCH_GROUPS = (GROUP_FLEET, GROUP_COMMANDERS, GROUP_CAPITALS)

# Murmur permission bits (MumbleServer.ice; Listen is ChanACL::Listen).
WRITE = 0x01
TRAVERSE = 0x02
ENTER = 0x04
SPEAK = 0x08
MUTE_DEAFEN = 0x10
MOVE = 0x20
MAKE_CHANNEL = 0x40
LINK_CHANNEL = 0x80
WHISPER = 0x100
TEXT_MESSAGE = 0x200
MAKE_TEMP_CHANNEL = 0x400
LISTEN = 0x800
KICK = 0x10000
BAN = 0x20000
REGISTER = 0x40000
REGISTER_SELF = 0x80000
RESET_USER_CONTENT = 0x100000

EVERYTHING = (
    WRITE
    | TRAVERSE
    | ENTER
    | SPEAK
    | MUTE_DEAFEN
    | MOVE
    | MAKE_CHANNEL
    | LINK_CHANNEL
    | WHISPER
    | TEXT_MESSAGE
    | MAKE_TEMP_CHANNEL
    | LISTEN
    | KICK
    | BAN
    | REGISTER
    | REGISTER_SELF
    | RESET_USER_CONTENT
)
MODERATE = MOVE | KICK | MUTE_DEAFEN


def branch_name(branch: int) -> str:
    return f"Fleet {int(branch)}"


@dataclass(frozen=True)
class Rule:
    group: str
    allow: int = 0
    deny: int = 0
    here: bool = True
    subs: bool = True


ROOT_RULES = (
    # Everyone may walk the tree, nothing else; text off everywhere.
    Rule(GROUP_ALL, allow=TRAVERSE, deny=EVERYTHING & ~TRAVERSE),
    Rule(GROUP_VOICEADMIN, allow=MODERATE),
)
COMMUNITY_RULES = (Rule(GROUP_COMMUNITY, allow=ENTER | SPEAK),)
COMMAND_RULES = (
    Rule(GROUP_ALL, deny=TRAVERSE | ENTER | SPEAK | WHISPER | LISTEN),
    Rule(GROUP_FLEET, allow=TRAVERSE),
    # Report: any fleet member may whisper up to Command, nowhere else.
    Rule(GROUP_FLEET, allow=WHISPER, subs=False),
    Rule(GROUP_CAPITALS, allow=WHISPER),
    Rule(
        GROUP_COMMANDERS,
        allow=ENTER | SPEAK | WHISPER | LISTEN | MODERATE | RESET_USER_CONTENT,
    ),
    Rule(GROUP_VOICEADMIN, allow=MODERATE),
)
SUBCHANNEL_RULES = (Rule(GROUP_FLEET, allow=ENTER | SPEAK, subs=False),)
# The open branch: community members may walk past Command into the
# subchannels, never into Command itself.
OPEN_COMMAND_RULES = (
    *COMMAND_RULES,
    Rule(GROUP_COMMUNITY, allow=TRAVERSE),
)
OPEN_SUBCHANNEL_RULES = (
    *SUBCHANNEL_RULES,
    Rule(GROUP_COMMUNITY, allow=ENTER | SPEAK, subs=False),
)


@dataclass
class ChannelIds:
    root: int
    lobby: int
    open: dict[str, int]
    branches: dict[int, int]  # branch -> Command (the "Fleet N" channel)
    subchannels: dict[int, dict[str, int]]  # branch -> name -> id

    def branch_of(self, channel_id: int) -> int | None:
        for branch, command in self.branches.items():
            if channel_id == command or channel_id in self.subchannels[branch].values():
                return branch
        return None

    def placement_channel(self, branch: int, placement: str) -> int:
        if placement == COMMAND:
            return self.branches[branch]
        return (
            self.subchannels[branch].get(placement)
            or self.subchannels[branch][MAINLINE]
        )

    def name_of(self, branch: int, channel_id: int) -> str:
        if channel_id == self.branches.get(branch):
            return COMMAND
        for name, cid in self.subchannels.get(branch, {}).items():
            if cid == channel_id:
                return name
        return ""


class Layout:
    """Creates missing channels and rewrites their ACLs.

    ``ice`` is a small adapter over the Murmur server proxy (see main.py
    and tests/fakes.py): channels(), add_channel(name, parent),
    set_acl(channel_id, rules, groups, inherit).
    """

    def __init__(self, ice):
        self.ice = ice

    def _child(self, existing, name, parent):
        for cid, (cname, cparent) in existing.items():
            if cname == name and cparent == parent:
                return cid
        cid = self.ice.add_channel(name, parent)
        existing[cid] = (name, parent)
        return cid

    def ensure(self) -> ChannelIds:
        existing = self.ice.channels()  # id -> (name, parent)
        root = 0
        if existing.get(root, ("", -1))[0] != ROOT:
            self.ice.rename_channel(root, ROOT)  # Murmur calls it "Root"
        self.ice.set_acl(root, ROOT_RULES, (), inherit=False)
        lobby = self._child(existing, LOBBY, root)
        self.ice.set_acl(lobby, COMMUNITY_RULES, (), inherit=True)
        opened = {}
        for name in OPEN_CHANNELS:
            opened[name] = self._child(existing, name, root)
            self.ice.set_acl(opened[name], COMMUNITY_RULES, (), inherit=True)
        branches, subchannels = {}, {}
        for branch in range(1, BRANCH_COUNT + 1):
            command = self._child(existing, branch_name(branch), root)
            branches[branch] = command
            subchannels[branch] = {
                name: self._child(existing, name, command)
                for name in BRANCH_SUBCHANNELS
            }
            self.reset_branch(command, subchannels[branch], branch=branch)
        return ChannelIds(root, lobby, opened, branches, subchannels)

    def reset_branch(
        self, command: int, subchannels: dict[str, int], branch: int = 0
    ) -> None:
        """Rewrite a branch's ACLs; this also clears its temporary groups."""
        is_open = branch == OPEN_BRANCH
        command_rules = OPEN_COMMAND_RULES if is_open else COMMAND_RULES
        sub_rules = OPEN_SUBCHANNEL_RULES if is_open else SUBCHANNEL_RULES
        self.ice.set_acl(command, command_rules, BRANCH_GROUPS, inherit=True)
        for cid in subchannels.values():
            self.ice.set_acl(cid, sub_rules, (), inherit=True)
