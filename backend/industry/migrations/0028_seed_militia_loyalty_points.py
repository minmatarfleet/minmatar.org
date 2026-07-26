# Generated manually — seed FW militia IndustryLoyaltyPoint defaults.

from django.db import migrations

MILITIA = (
    (1000182, "Tribal Liberation Force"),
    (1000179, "24th Imperial Crusade"),
    (1000180, "State Protectorate"),
    (1000181, "Federal Defense Union"),
)


def seed_militia_loyalty_points(apps, schema_editor):
    IndustryLoyaltyPoint = apps.get_model("industry", "IndustryLoyaltyPoint")
    for corporation_id, name in MILITIA:
        IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=corporation_id,
            defaults={
                "name": name,
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )


def unseed_militia_loyalty_points(apps, schema_editor):
    IndustryLoyaltyPoint = apps.get_model("industry", "IndustryLoyaltyPoint")
    IndustryLoyaltyPoint.objects.filter(
        corporation_id__in=[c for c, _ in MILITIA]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("industry", "0027_industryloyaltypoint_and_contacts"),
    ]

    operations = [
        migrations.RunPython(
            seed_militia_loyalty_points,
            unseed_militia_loyalty_points,
        ),
    ]
