"""Group chiefs become timezone seats (US, EU, AU).

Each group's single chief takes the seat of their PilotTimezone home
(else their first bracket, else US). Pending group volunteers get the same
region, moved to a free seat when theirs is taken.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from tribes.helpers.chief_regions import (
    FALLBACK_REGION,
    home_region,
    pick_region,
)


def _regions_by_user(apps, user_ids):
    pilot_timezone = apps.get_model("timezones", "PilotTimezone")
    return {
        row.user_id: home_region(row.home, row.brackets)
        for row in pilot_timezone.objects.filter(user_id__in=set(user_ids))
    }


def seat_existing_chiefs(apps, schema_editor):
    tribe_group = apps.get_model("tribes", "TribeGroup")
    seat = apps.get_model("tribes", "TribeGroupChief")
    volunteer = apps.get_model("tribes", "TribeChiefVolunteer")
    groups = list(tribe_group.objects.filter(chief_id__isnull=False))
    offers = list(
        volunteer.objects.filter(
            tribe_group_id__isnull=False, status="pending"
        ).order_by("created_at")
    )
    regions = _regions_by_user(
        apps,
        [g.chief_id for g in groups] + [o.user_id for o in offers],
    )
    taken = {}
    for group in groups:
        region = regions.get(group.chief_id) or FALLBACK_REGION
        seat.objects.create(
            tribe_group_id=group.pk, region=region, user_id=group.chief_id
        )
        taken[group.pk] = {region}
    for offer in offers:
        region = pick_region(
            regions.get(offer.user_id), taken.get(offer.tribe_group_id, ())
        )
        offer.region = region or FALLBACK_REGION
        offer.save(update_fields=["region"])


def unseat_chiefs(apps, schema_editor):
    """Reverse: the first seat (US, EU, AU order) becomes the chief."""
    tribe_group = apps.get_model("tribes", "TribeGroup")
    seat = apps.get_model("tribes", "TribeGroupChief")
    order = {"US": 0, "EU": 1, "AU": 2}
    first = {}
    for row in seat.objects.all():
        best = first.get(row.tribe_group_id)
        if best is None or order[row.region] < order[best.region]:
            first[row.tribe_group_id] = row
    for group_id, row in first.items():
        tribe_group.objects.filter(pk=group_id).update(chief_id=row.user_id)


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0051_move_fanfest_into_pulse"),
        ("timezones", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="tribechiefvolunteer",
            name="region",
            field=models.CharField(
                blank=True,
                default="",
                help_text="A group seat's timezone region (US, EU, AU). Empty for the tribe chief seat.",
                max_length=2,
            ),
        ),
        migrations.CreateModel(
            name="TribeGroupChief",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "region",
                    models.CharField(
                        choices=[
                            ("US", "USTZ"),
                            ("EU", "EUTZ"),
                            ("AU", "AUTZ"),
                        ],
                        max_length=2,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tribe_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chief_seats",
                        to="tribes.tribegroup",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tribe_group_chief_seats",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["tribe_group_id", "region"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tribe_group", "region"),
                        name="tribes_group_chief_one_per_region",
                    ),
                    models.UniqueConstraint(
                        fields=("tribe_group", "user"),
                        name="tribes_group_chief_one_seat_per_pilot",
                    ),
                ],
            },
        ),
        migrations.RunPython(seat_existing_chiefs, unseat_chiefs),
        migrations.RemoveField(
            model_name="tribegroup",
            name="chief",
        ),
    ]
