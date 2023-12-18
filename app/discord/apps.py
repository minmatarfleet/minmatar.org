from django.apps import AppConfig


class DiscordConfig(AppConfig):
    name = "discord"

    def ready(self):
        import discord.signals  # noqa # pylint: disable=unused-import, import-outside-toplevel
