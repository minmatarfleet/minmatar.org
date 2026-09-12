"""Inspect Discord roles/permissions for a guild the bot is in (read-only)."""

from django.core.management.base import BaseCommand, CommandError

from discord.client import DiscordClient, BASE_URL

PERM_BITS = {
    "CREATE_INSTANT_INVITE": 1 << 0,
    "KICK_MEMBERS": 1 << 1,
    "BAN_MEMBERS": 1 << 2,
    "ADMINISTRATOR": 1 << 3,
    "MANAGE_ROLES": 1 << 28,
}


class Command(BaseCommand):
    help = (
        "List bot membership + roles in a Discord guild "
        "(e.g. Fishermen 834087499658952735). Run on prod for the Fleet bot."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "guild_id",
            type=str,
            help="Discord guild snowflake to inspect",
        )

    def handle(self, *args, **options):
        guild_id = options["guild_id"]
        client = DiscordClient.for_guild(guild_id)
        me = client.get(f"{BASE_URL}/users/@me")
        self.stdout.write(f"bot={me.get('id')} {me.get('username')}")

        guilds = client.get(f"{BASE_URL}/users/@me/guilds")
        match = next(
            (g for g in guilds if str(g["id"]) == str(guild_id)), None
        )
        if match is None:
            raise CommandError(
                f"Bot is not in guild {guild_id}. Guilds: "
                + ", ".join(f"{g['id']}:{g['name']}" for g in guilds)
            )

        perms = int(match.get("permissions") or 0)
        flags = [name for name, bit in PERM_BITS.items() if perms & bit]
        self.stdout.write(f"guild={match.get('name')} permissions={flags}")

        try:
            member = client.get_user(me["id"])
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandError(f"Failed fetching bot member: {exc}") from exc

        self.stdout.write(f"bot_roles={member.get('roles')}")

        roles = client.get_roles()
        roles_sorted = sorted(
            roles, key=lambda role: role.get("position", 0), reverse=True
        )
        self.stdout.write("roles (high → low):")
        for role in roles_sorted:
            self.stdout.write(
                f"  pos={role['position']:3} id={role['id']} "
                f"name={role['name']!r} managed={role.get('managed')}"
            )
