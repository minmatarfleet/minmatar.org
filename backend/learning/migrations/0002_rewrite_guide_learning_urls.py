from django.db import migrations, models


def rewrite_guide_urls(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")
    for learning in Learning.objects.filter(
        url__startswith="/guides/"
    ).iterator():
        learning.url = "/learning/guides/" + learning.url[len("/guides/") :]
        learning.save(update_fields=["url"])


def revert_guide_urls(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")
    for learning in Learning.objects.filter(
        url__startswith="/learning/guides/"
    ).iterator():
        learning.url = "/guides/" + learning.url[len("/learning/guides/") :]
        learning.save(update_fields=["url"])


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rewrite_guide_urls, revert_guide_urls),
        migrations.AlterField(
            model_name="learning",
            name="url",
            field=models.CharField(
                help_text="Site-relative path (e.g. /learning/guides/…) or absolute URL.",
                max_length=500,
            ),
        ),
    ]
