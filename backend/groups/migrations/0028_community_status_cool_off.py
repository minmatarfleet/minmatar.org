from django.db import migrations, models

STATUS_CHOICES = [
    ("active", "Active"),
    ("trial", "Trial"),
    ("on_leave", "On Leave"),
    ("cool_off", "Cool Off"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0027_drop_legacy_mumble_access_table"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usercommunitystatus",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, max_length=16),
        ),
        migrations.AlterField(
            model_name="usercommunitystatushistory",
            name="from_status",
            field=models.CharField(
                blank=True,
                choices=STATUS_CHOICES,
                max_length=16,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="usercommunitystatushistory",
            name="to_status",
            field=models.CharField(choices=STATUS_CHOICES, max_length=16),
        ),
    ]
