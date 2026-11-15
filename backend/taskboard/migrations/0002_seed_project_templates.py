"""The three starting project templates: campaign, new doctrine, town hall.

Admins change them in the Django admin. Repeating tasks ("weekly:<day>",
Monday is 0) open their next copy only when the last one closes.
"""

from django.db import migrations

TEMPLATES = [
    (
        "campaign",
        "Campaign",
        "Orders, weekly fleets and targets, and the results write-up",
        [
            ("Before it starts", "Write the campaign orders", "lead", -7, ""),
            (
                "Before it starts",
                "Pick the systems and targets",
                "lead",
                -7,
                "",
            ),
            (
                "Before it starts",
                "Schedule the first week's Strategic fleets",
                "lead",
                -5,
                "",
            ),
            ("Before it starts", "Announce the campaign", "lead", -1, ""),
            (
                "While it runs",
                "Accept the week's targets",
                "screen:campaigns",
                0,
                "weekly:0",
            ),
            (
                "While it runs",
                "Schedule next week's Strategic fleets",
                "lead",
                0,
                "weekly:3",
            ),
            ("While it runs", "Post a project update", "lead", 0, "weekly:4"),
            (
                "While it runs",
                "Check the roster for pilots who stopped flying",
                "lead",
                14,
                "",
            ),
            (
                "Wrap up",
                "Write the campaign results for Fleet Dispatch",
                "lead",
                None,
                "",
            ),
            (
                "Wrap up",
                "Present the results at the next town hall",
                "lead",
                None,
                "",
            ),
        ],
    ),
    (
        "doctrine",
        "New doctrine",
        "Agree the fits, review and publish, then support the fleet",
        [
            ("Decide", "Agree the fits with the FCs", "lead", 3, ""),
            ("Decide", "Send the doctrine for review", "lead", 5, ""),
            (
                "Publish",
                "Review the doctrine change",
                "screen:doctrines",
                7,
                "",
            ),
            ("Publish", "Set the SRP amount", "screen:srp_amounts", 8, ""),
            ("Publish", "Publish the doctrine", "lead", 10, ""),
            ("Support", "Seed fitted hulls on the market", "lead", None, ""),
            ("Support", "Write the doctrine guide", "lead", None, ""),
        ],
    ),
    (
        "town_hall",
        "Town hall",
        "Collect the slides, build the deck, hold it and cut the highlights",
        [
            (
                "Prepare",
                "Book the date and post the announcement",
                "lead",
                -14,
                "",
            ),
            ("Prepare", "Ask each tribe for its slides", "lead", -10, ""),
            ("Prepare", "Collect the tribe slides", "lead", -4, ""),
            ("Prepare", "Build the deck", "lead", -2, ""),
            ("Prepare", "Test the stream and voice setup", "lead", -1, ""),
            ("Afterwards", "Post the recording", "lead", 2, ""),
            ("Afterwards", "Cut the highlights video", "lead", None, ""),
            ("Afterwards", "Answer the questions left over", "lead", None, ""),
        ],
    ),
]


def seed(apps, schema_editor):
    ProjectTemplate = apps.get_model("taskboard", "ProjectTemplate")
    TemplateTask = apps.get_model("taskboard", "TemplateTask")
    for position, (kind, name, description, tasks) in enumerate(TEMPLATES):
        template, created = ProjectTemplate.objects.get_or_create(
            kind=kind,
            defaults={
                "name": name,
                "description": description,
                "position": position,
            },
        )
        if not created:
            continue
        for index, (stage, title, goes_to, offset, recurrence) in enumerate(
            tasks
        ):
            TemplateTask.objects.create(
                template=template,
                stage=stage,
                position=index,
                title=title,
                goes_to=goes_to,
                offset_days=offset,
                recurrence=recurrence,
            )


def unseed(apps, schema_editor):
    ProjectTemplate = apps.get_model("taskboard", "ProjectTemplate")
    ProjectTemplate.objects.filter(
        kind__in=[row[0] for row in TEMPLATES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("taskboard", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
