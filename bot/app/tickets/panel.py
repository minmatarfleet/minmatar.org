import discord

from .api import HelpTicketPanelConfig

HELP_TICKET_SELECT_CUSTOM_ID = "help_ticket_select"


def build_panel_embed(config: HelpTicketPanelConfig) -> discord.Embed:
    return discord.Embed(
        title=config.embed_title,
        description=config.embed_description,
        color=0xB50000,
    )


def _build_select_options(config: HelpTicketPanelConfig) -> list[discord.SelectOption]:
    options: list[discord.SelectOption] = []
    for category in config.categories:
        options.append(
            discord.SelectOption(
                label=category.title[:100],
                value=str(category.id),
                description=category.section[:100],
            )
        )
    return options[:25]


class HelpTicketPanelView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption] | None = None):
        super().__init__(timeout=None)
        self.add_item(HelpTicketSelect(options))


class HelpTicketSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption] | None = None):
        super().__init__(
            custom_id=HELP_TICKET_SELECT_CUSTOM_ID,
            placeholder="Select a team...",
            min_values=1,
            max_values=1,
            options=options
            or [
                discord.SelectOption(
                    label="Loading teams...",
                    value="0",
                )
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        category_id = int(self.values[0])
        if category_id == 0:
            await interaction.response.send_message(
                "The help panel is still loading. Try again in a moment.",
                ephemeral=True,
            )
            return

        # pylint: disable=import-outside-toplevel
        from .modals import HelpRequestModal

        await interaction.response.send_modal(HelpRequestModal(category_id))


def register_help_ticket_panel_view(client: discord.Client) -> None:
    client.add_view(HelpTicketPanelView())


def build_panel_view(config: HelpTicketPanelConfig) -> HelpTicketPanelView:
    return HelpTicketPanelView(_build_select_options(config))
