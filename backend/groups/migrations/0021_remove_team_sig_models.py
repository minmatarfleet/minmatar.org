# Generated manually: remove Team, TeamRequest, Sig, SigRequest (replaced by tribes)

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0020_fix_trial_status_by_affiliation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="TeamRequest"),
        migrations.DeleteModel(name="SigRequest"),
        migrations.DeleteModel(name="Team"),
        migrations.DeleteModel(name="Sig"),
    ]
