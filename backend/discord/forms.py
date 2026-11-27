from django import forms
from django.core.exceptions import ValidationError

from discord.channels import (
    ADMIN_PICKER_CHANNEL_TYPES,
    AMARR_FLEET_PING_CHANNEL_TYPES,
    BUYBACK_CHANNEL_TYPES,
    CAPITAL_PING_CHANNEL_TYPES,
    LP_BUYBACK_CHANNEL_TYPES,
    LP_CONVERSION_ALERT_CHANNEL_TYPES,
    RECRUITER_ALERT_CHANNEL_TYPES,
    VOICE_TRACKING_CHANNEL_TYPES,
    admin_picker_guilds,
    fetch_active_guild_channels,
    get_guild_channel,
)
from discord.models import DiscordChannel, DiscordGuild

# (flag, channel types it allows, error when set on another type)
CHANNEL_FLAG_TYPES = (
    (
        "hide_from_fleets",
        VOICE_TRACKING_CHANNEL_TYPES,
        "Only voice and stage channels are listed for fleets.",
    ),
    (
        "track_voice_activity",
        VOICE_TRACKING_CHANNEL_TYPES,
        "Voice activity tracking is only supported for voice and stage channels.",
    ),
    (
        "receive_capital_pings",
        CAPITAL_PING_CHANNEL_TYPES,
        "Capital pings are only supported for text and forum channels.",
    ),
    (
        "receive_amarr_fleet_pings",
        AMARR_FLEET_PING_CHANNEL_TYPES,
        "Amarr fleet pings are only supported for text and forum channels.",
    ),
    (
        "receive_lp_buyback",
        LP_BUYBACK_CHANNEL_TYPES,
        "LP buyback order threads require a forum channel.",
    ),
    (
        "receive_buyback",
        BUYBACK_CHANNEL_TYPES,
        "Hangar buyback purchase-order threads require a forum channel.",
    ),
    (
        "receive_lp_conversion_alerts",
        LP_CONVERSION_ALERT_CHANNEL_TYPES,
        "Conversion Team alerts require a text channel.",
    ),
    (
        "receive_recruiter_alerts",
        RECRUITER_ALERT_CHANNEL_TYPES,
        "Recruiter alerts require a text channel.",
    ),
)


class DiscordChannelAdminForm(forms.ModelForm):
    discord_channel_pick = forms.ChoiceField(
        choices=[],
        required=False,
        label="Discord channel",
        help_text="Select a channel from an active synced guild.",
    )

    class Meta:
        model = DiscordChannel
        fields = (
            "track_voice_activity",
            "hide_from_fleets",
            "receive_capital_pings",
            "receive_amarr_fleet_pings",
            "receive_lp_buyback",
            "receive_buyback",
            "receive_lp_conversion_alerts",
            "receive_recruiter_alerts",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        channels = fetch_active_guild_channels()
        channel_guild_names = {
            guild.guild_id: guild.name for guild in admin_picker_guilds()
        }
        choices = [("", "---------")]
        for channel in channels:
            if channel["type"] not in ADMIN_PICKER_CHANNEL_TYPES:
                continue
            guild_name = channel_guild_names.get(
                channel["guild_id"], "Unknown guild"
            )
            label = f"{guild_name} / {channel['name']} ({channel['type']})"
            choices.append((str(channel["id"]), label))

        self.fields["discord_channel_pick"].choices = choices

        if self.instance.pk:
            del self.fields["discord_channel_pick"]
            self.fields["guild"] = forms.ModelChoiceField(
                queryset=DiscordGuild.objects.all(),
                disabled=True,
                required=False,
                initial=self.instance.guild,
            )
            self.fields["name"] = forms.CharField(
                disabled=True,
                required=False,
                initial=self.instance.name,
            )
            self.fields["channel_type"] = forms.CharField(
                disabled=True,
                required=False,
                initial=self.instance.get_channel_type_display(),
            )
            self.fields["channel_id"] = forms.IntegerField(
                disabled=True,
                required=False,
                initial=self.instance.channel_id,
            )
        elif not channels:
            self.fields["discord_channel_pick"].help_text = (
                "No channels found. Sync Discord guilds first, then try again."
            )

    def clean(self):
        cleaned_data = super().clean()
        channel_type = self._channel_type(cleaned_data)
        for flag, allowed_types, message in CHANNEL_FLAG_TYPES:
            if cleaned_data.get(flag, False) and (
                channel_type not in allowed_types
            ):
                raise ValidationError({flag: message})
        return cleaned_data

    def _channel_type(self, cleaned_data) -> str:
        """Type of the edited channel, or of the picked one (validated)."""
        if self.instance.pk:
            channel_type = self.instance.channel_type
        else:
            channel_id_raw = cleaned_data.get("discord_channel_pick")
            if not channel_id_raw:
                raise ValidationError(
                    {"discord_channel_pick": "Select a Discord channel."}
                )
            channel = get_guild_channel(int(channel_id_raw))
            if channel is None:
                raise ValidationError(
                    {
                        "discord_channel_pick": "Selected channel was not found on Discord."
                    }
                )
            cleaned_data["_selected_channel"] = channel
            channel_type = channel["type"]
            guild = DiscordGuild.objects.filter(
                guild_id=channel["guild_id"], is_active=True
            ).first()
            if guild is None:
                raise ValidationError(
                    {
                        "discord_channel_pick": (
                            "Selected channel belongs to a guild that is not synced yet."
                        )
                    }
                )
            cleaned_data["_selected_guild"] = guild
            if DiscordChannel.objects.filter(
                channel_id=channel["id"]
            ).exists():
                raise ValidationError(
                    {
                        "discord_channel_pick": (
                            "This Discord channel is already registered."
                        )
                    }
                )
        return channel_type

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected_channel = self.cleaned_data.get("_selected_channel")
        selected_guild = self.cleaned_data.get("_selected_guild")
        if selected_channel:
            instance.channel_id = selected_channel["id"]
            instance.name = selected_channel["name"]
            instance.channel_type = selected_channel["type"]
        if selected_guild:
            instance.guild = selected_guild

        if commit:
            instance.save()
        return instance
