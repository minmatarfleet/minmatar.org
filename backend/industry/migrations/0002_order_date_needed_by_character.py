# Generated manually

from datetime import date

from django.db import migrations, models
import django.db.models.deletion


def set_order_character(apps, schema_editor):
    IndustryOrder = apps.get_model("industry", "IndustryOrder")
    EveCharacter = apps.get_model("eveonline", "EveCharacter")
    first_char = EveCharacter.objects.first()
    if first_char:
        IndustryOrder.objects.filter(character_id__isnull=True).update(
            character_id=first_char.id
        )


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0001_add_industry_order_models"),
    ]

    operations = [
        migrations.RemoveField(model_name="industryorder", name="name"),
        migrations.AddField(
            model_name="industryorder",
            name="needed_by",
            field=models.DateField(default=date(2000, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="industryorder",
            name="character",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="industry_orders",
                to="eveonline.evecharacter",
            ),
        ),
        migrations.RunPython(set_order_character, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="industryorder",
            name="character",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="industry_orders",
                to="eveonline.evecharacter",
            ),
        ),
        migrations.AlterField(
            model_name="industryorder",
            name="needed_by",
            field=models.DateField(),
        ),
    ]
