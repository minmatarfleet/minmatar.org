from django import forms
from django.core.exceptions import ValidationError

from discord.channels import (
    ADMIN_PICKER_CHANNEL_TYPES,
    CAPITAL_PING_CHANNEL_TYPES,
    VOICE_TRACKING_CHANNEL_TYPES,
    fetch_active_guild_channels,
    get_guild_channel,
)
from discord.models import DiscordChannel, DiscordGuild


class DiscordChannelAdminForm(forms.ModelForm):
    discord_channel_pick = forms.ChoiceField(
        choices=[],
        required=False,
        label="Discord channel",
        help_text="Select a channel from an active synced guild.",
    )

    class Meta:
        model = DiscordChannel
        fields = ("track_voice_activity", "receive_capital_pings")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        channels = fetch_active_guild_channels()
        channel_guild_names = {
            guild.guild_id: guild.name
            for guild in DiscordGuild.objects.filter(is_active=True)
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
        track_voice_activity = cleaned_data.get("track_voice_activity", False)
        receive_capital_pings = cleaned_data.get(
            "receive_capital_pings", False
        )

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

        if (
            track_voice_activity
            and channel_type not in VOICE_TRACKING_CHANNEL_TYPES
        ):
            raise ValidationError(
                {
                    "track_voice_activity": (
                        "Voice activity tracking is only supported for voice and stage channels."
                    )
                }
            )

        if (
            receive_capital_pings
            and channel_type not in CAPITAL_PING_CHANNEL_TYPES
        ):
            raise ValidationError(
                {
                    "receive_capital_pings": (
                        "Capital pings are only supported for text and forum channels."
                    )
                }
            )

        return cleaned_data

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
