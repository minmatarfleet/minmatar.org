"""Mumble channel names shared with the voice service (voice/voice_auth/layout.py).

Changing a name is a voice-service change too: the contract test in
voice/tests/test_contracts.py fails until both sides agree.
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

# Groups the voice service adds on each branch channel.
GROUP_FLEET = "fleet"
GROUP_COMMANDERS = "commanders"
GROUP_CAPITALS = "capitals"
# Server-wide groups returned by the authenticator at login.
GROUP_COMMUNITY = "community"
GROUP_VOICEADMIN = "voiceadmin"


def branch_name(branch: int) -> str:
    return f"Fleet {int(branch)}"
