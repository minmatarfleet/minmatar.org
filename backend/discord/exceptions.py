"""Exceptions for Discord role / auth group sync."""


class DiscordRoleAssignmentError(Exception):
    """
    Raised when a Django auth.Group membership change cannot be mirrored
    on Discord. Callers must treat this as aborting the M2M change (and
    any source write that depends on it). See docs/auth/discord-groups.md.
    """
