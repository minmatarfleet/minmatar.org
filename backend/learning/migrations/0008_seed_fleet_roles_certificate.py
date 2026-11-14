# Seed the Fleet Roles certificate: earned with any three of the five role
# certificates that migration 0006 seeds.

from django.db import migrations

SLUG = "fleet-roles"
ROLE_CERTIFICATES = [
    "fleet-role-damage",
    "fleet-role-remote-repair",
    "fleet-role-capacitor-warfare",
    "fleet-role-electronic-warfare",
    "fleet-role-positioning-warfare",
]
REQUIRED_COUNT = 3


def seed(apps, schema_editor):
    Certificate = apps.get_model("learning", "Certificate")
    certificate, _ = Certificate.objects.update_or_create(
        slug=SLUG,
        defaults={
            "title": "Fleet Roles",
            "summary": (
                "Earn any three of the five role certificates: Damage, "
                "Remote Repair, Capacitor Warfare, Electronic Warfare and "
                "Positioning Warfare. A pilot who can fill three jobs can "
                "fill whatever the fleet is short of."
            ),
            "personas": ["alliance", "militia"],
            "sort_order": 9,
            "published": True,
            "required_count": REQUIRED_COUNT,
        },
    )
    certificate.required_certificates.set(
        Certificate.objects.filter(slug__in=ROLE_CERTIFICATES)
    )


def unseed(apps, schema_editor):
    Certificate = apps.get_model("learning", "Certificate")
    Certificate.objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0007_certificate_required_certificates"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
