from django.db import migrations, models
import django.db.models.deletion


def forwards_tribe_to_group(apps, schema_editor):
    TribeExternalGuild = apps.get_model("tribes", "TribeExternalGuild")
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    preferred = (
        TribeGroup.objects.filter(code="pulse.fishermen").first()
        or TribeGroup.objects.filter(code__endswith=".fishermen").first()
        or TribeGroup.objects.filter(name="Fishermen").first()
    )
    for binding in TribeExternalGuild.objects.all():
        group = preferred or (
            TribeGroup.objects.filter(tribe_id=binding.tribe_id)
            .order_by("id")
            .first()
        )
        if group is None:
            binding.delete()
            continue
        binding.tribe_group_id = group.id
        binding.save(update_fields=["tribe_group_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0035_remove_external_guild_invite_channel"),
    ]

    operations = [
        migrations.AddField(
            model_name="tribeexternalguild",
            name="tribe_group",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="external_guild",
                to="tribes.tribegroup",
            ),
        ),
        migrations.RunPython(
            forwards_tribe_to_group, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="tribeexternalguild",
            name="tribe",
        ),
        migrations.AlterField(
            model_name="tribeexternalguild",
            name="tribe_group",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="external_guild",
                to="tribes.tribegroup",
            ),
        ),
        migrations.AlterField(
            model_name="tribeexternalguild",
            name="guild",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tribe_group_bindings",
                to="discord.discordguild",
            ),
        ),
        migrations.AlterModelOptions(
            name="tribeexternalguild",
            options={"ordering": ["tribe_group__name"]},
        ),
    ]
