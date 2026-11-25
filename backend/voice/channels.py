"""Mumble channel names shared with the voice service (voice/voice_auth/layout.py).

Changing a name is a voice-service change too. The backend writes these
names to voice/tests/contracts/channels.json (voice/tests/test_publisher.py),
and ``ContractTest`` in voice/tests/test_service.py fails until both sides
agree.
"""

ROOT = "Minmatar Fleet"
LOBBY = "Lobby"
OPEN_CHANNELS = ("Open 1", "Open 2")
COMMAND = "Command"  # the branch channel itself ("Fleet N")
MAINLINE = "Mainline"
LOGISTICS = "Logistics"
AUXILIARY = ("Auxiliary A", "Auxiliary B", "Auxiliary C")
BRANCH_SUBCHANNELS = (MAINLINE, LOGISTICS, *AUXILIARY)
# Where placement may send a pilot inside a branch.
PLACEMENT_CHANNELS = (COMMAND, *BRANCH_SUBCHANNELS)

# Fleet 1 is open: any community member may enter its subchannels, with or
# without a fleet (Command stays commanders only). Fleets the FC sets to
# open lease it; restricted fleets lease the others (voice/leases.py).
OPEN_BRANCH = 1

# Groups the voice service adds on each branch channel.
GROUP_FLEET = "fleet"
GROUP_COMMANDERS = "commanders"
GROUP_CAPITALS = "capitals"
# Server-wide groups returned by the authenticator at login.
GROUP_COMMUNITY = "community"
GROUP_VOICEADMIN = "voiceadmin"


def branch_name(branch: int) -> str:
    return f"Fleet {int(branch)}"
