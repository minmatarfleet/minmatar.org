# Migration to run sync_user_community_groups for every user with UserCommunityStatus.
# The backfill in 0018 created UserCommunityStatus (including trial) but did not run
# sync, so those users never got the Trial/On Leave Django groups or Discord roles.

from django.db import migrations


def run_sync_after_backfill(apps, schema_editor):
    from django.contrib.auth import get_user_model
    from groups.helpers import sync_user_community_groups

    User = get_user_model()
    UserCommunityStatus = apps.get_model("groups", "UserCommunityStatus")
    for ucs in UserCommunityStatus.objects.all():
        user = User.objects.get(pk=ucs.user_id)
        sync_user_community_groups(user)


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0018_user_community_status_and_requires_trial"),
    ]

    operations = [
        migrations.RunPython(
            run_sync_after_backfill, migrations.RunPython.noop
        ),
    ]
