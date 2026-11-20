# A tribe-group class requirement is a group code. Editors also typed the
# group's name ("Freighters"), and the check only queried the code
# (supply.freighters), so every member failed it. Rewrite a token that
# is a unique group name to that code. An unknown or shared name stays.

from django.db import migrations


def _codes_for_token(tribe_group, token):
    if tribe_group.objects.filter(code=token).exists():
        return [token]
    return list(
        tribe_group.objects.filter(name__iexact=token).values_list(
            "code", flat=True
        )
    )


def rewrite_tribe_group_requirement_names(apps, schema_editor):
    mentor_class_model = apps.get_model("learning", "MentorClass")
    tribe_group = apps.get_model("tribes", "TribeGroup")
    for mentor_class in mentor_class_model.objects.all():
        rows = mentor_class.requirements or []
        if not isinstance(rows, list):
            continue
        changed = False
        rewritten = []
        for row in rows:
            if not isinstance(row, dict) or row.get("kind") != "tribe_group":
                rewritten.append(row)
                continue
            tokens = [
                part.strip()
                for part in str(row.get("value", "")).split(",")
                if part.strip()
            ]
            codes = []
            seen = set()
            for token in tokens:
                matched = _codes_for_token(tribe_group, token)
                if len(matched) == 1:
                    token = matched[0]
                if token not in seen:
                    seen.add(token)
                    codes.append(token)
            value = ", ".join(codes)
            if value != row.get("value"):
                changed = True
                row = {**row, "value": value}
            rewritten.append(row)
        if changed:
            mentor_class.requirements = rewritten
            mentor_class.save(update_fields=["requirements"])


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0006_seed_fleet_role_learnings"),
        ("tribes", "0052_tribe_group_chief_seats"),
    ]

    operations = [
        migrations.RunPython(
            rewrite_tribe_group_requirement_names,
            migrations.RunPython.noop,
        ),
    ]
