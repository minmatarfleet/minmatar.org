"""
Refactors TribeGroupMembership status (approved→active, denied/left/removed→inactive),
strips audit columns from TribeGroupMembershipCharacter (committed_at, left_at,
leave_reason), and adds TribeGroupMembershipHistory and
TribeGroupMembershipCharacterHistory audit tables.

A data migration runs after the new history tables are created but before the
old columns are dropped so we can backfill history from them.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_history(apps, schema_editor):
    """
    1. Map TribeGroupMembership status values:
         approved  → active
         denied / left / removed → inactive
    2. Backfill TribeGroupMembershipCharacterHistory from the (still-present)
       committed_at / left_at / leave_reason columns:
         - Always write an action='added' row.
         - If left_at is set, also write action='removed', then delete the
           TribeGroupMembershipCharacter row (it is not current).
    """
    TribeGroupMembership = apps.get_model("tribes", "TribeGroupMembership")
    TribeGroupMembershipCharacter = apps.get_model(
        "tribes", "TribeGroupMembershipCharacter"
    )
    TribeGroupMembershipCharacterHistory = apps.get_model(
        "tribes", "TribeGroupMembershipCharacterHistory"
    )

    # --- 1. Status mapping -------------------------------------------------
    STATUS_MAP = {
        "approved": "active",
        "denied": "inactive",
        "left": "inactive",
        "removed": "inactive",
    }
    for old_status, new_status in STATUS_MAP.items():
        TribeGroupMembership.objects.filter(status=old_status).update(
            status=new_status
        )

    # --- 2. Character history backfill ------------------------------------
    # Use raw SQL to access committed_at / left_at / leave_reason that are
    # still present in the database at this point in the migration.
    db_alias = schema_editor.connection.alias
    from django.db import connections

    conn = connections[db_alias]
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, membership_id, character_id,
                   committed_at, left_at, leave_reason
            FROM tribes_tribegroupmembershipcharacter
            """
        )
        rows = cursor.fetchall()

    to_add = []
    to_delete_ids = []
    now = timezone.now()

    for (
        row_id,
        membership_id,
        character_id,
        committed_at,
        left_at,
        leave_reason,
    ) in rows:
        # 'added' history row (always)
        to_add.append(
            TribeGroupMembershipCharacterHistory(
                membership_id=membership_id,
                character_id=character_id,
                action="added",
                at=committed_at or now,
            )
        )
        if left_at:
            # 'removed' history row
            reason = leave_reason or ""
            to_add.append(
                TribeGroupMembershipCharacterHistory(
                    membership_id=membership_id,
                    character_id=character_id,
                    action="removed",
                    at=left_at,
                    leave_reason=reason,
                )
            )
            to_delete_ids.append(row_id)

    TribeGroupMembershipCharacterHistory.objects.bulk_create(to_add)

    # Remove departed characters from the current-roster table.
    if to_delete_ids:
        TribeGroupMembershipCharacter.objects.filter(
            pk__in=to_delete_ids
        ).delete()


def reverse_backfill(apps, schema_editor):
    """Reverse: map active→approved, inactive→left. History rows are dropped."""
    TribeGroupMembership = apps.get_model("tribes", "TribeGroupMembership")
    TribeGroupMembership.objects.filter(status="active").update(
        status="approved"
    )
    TribeGroupMembership.objects.filter(status="inactive").update(
        status="left"
    )
    apps.get_model(
        "tribes", "TribeGroupMembershipCharacterHistory"
    ).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0090_evelocation_is_structure"),
        ("tribes", "0011_remove_tribe_group_outreach"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── 1. Create audit tables (without FK fields yet) ─────────────────
        migrations.CreateModel(
            name="TribeGroupMembershipCharacterHistory",
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
                    "action",
                    models.CharField(
                        choices=[("added", "Added"), ("removed", "Removed")],
                        max_length=8,
                    ),
                ),
                ("at", models.DateTimeField(default=timezone.now)),
                (
                    "leave_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("voluntary", "Voluntary"),
                            ("removed", "Removed"),
                        ],
                        help_text="Only set when action='removed'.",
                        max_length=16,
                    ),
                ),
            ],
            options={"ordering": ["at"]},
        ),
        migrations.CreateModel(
            name="TribeGroupMembershipHistory",
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
                ("from_status", models.CharField(blank=True, max_length=16)),
                ("to_status", models.CharField(max_length=16)),
                ("changed_at", models.DateTimeField(default=timezone.now)),
                (
                    "reason",
                    models.CharField(
                        blank=True,
                        help_text="Optional machine-readable reason (e.g. 'denied', 'left', 'removed', 'approved').",
                        max_length=32,
                    ),
                ),
            ],
            options={"ordering": ["changed_at"]},
        ),
        # ── 2. Add FK fields to make history tables queryable ──────────────
        migrations.AddField(
            model_name="tribegroupmembershipcharacterhistory",
            name="by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tribe_character_history_actions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="tribegroupmembershipcharacterhistory",
            name="character",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tribe_character_history",
                to="eveonline.evecharacter",
            ),
        ),
        migrations.AddField(
            model_name="tribegroupmembershipcharacterhistory",
            name="membership",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="character_history",
                to="tribes.tribegroupmembership",
            ),
        ),
        migrations.AddField(
            model_name="tribegroupmembershiphistory",
            name="changed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tribe_membership_changes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="tribegroupmembershiphistory",
            name="membership",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="history",
                to="tribes.tribegroupmembership",
            ),
        ),
        # ── 3. Data migration (while old columns still exist) ──────────────
        migrations.RunPython(backfill_history, reverse_backfill),
        # ── 4. Remove old unique constraints ─────────────────────────────
        migrations.RemoveConstraint(
            model_name="tribegroupmembership",
            name="tribes_tribegroupmembership_one_active_per_user_group",
        ),
        migrations.RemoveConstraint(
            model_name="tribegroupmembershipcharacter",
            name="tribes_tribegroupmembershipchar_one_active_per_character",
        ),
        # ── 5. Drop old columns from TribeGroupMembershipCharacter ─────────
        migrations.RemoveField(
            model_name="tribegroupmembershipcharacter",
            name="committed_at",
        ),
        migrations.RemoveField(
            model_name="tribegroupmembershipcharacter",
            name="leave_reason",
        ),
        migrations.RemoveField(
            model_name="tribegroupmembershipcharacter",
            name="left_at",
        ),
        # ── 6. Update TribeGroupMembership fields ─────────────────────────
        migrations.AlterField(
            model_name="tribegroupmembership",
            name="left_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Set when status becomes inactive.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="tribegroupmembership",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        # ── 7. Update Meta options on character roster model ──────────────
        migrations.AlterModelOptions(
            name="tribegroupmembershipcharacter",
            options={},
        ),
        # ── 8. Add new constraints ─────────────────────────────────────────
        migrations.AddConstraint(
            model_name="tribegroupmembership",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="active"),
                fields=("tribe_group", "user"),
                name="tribes_tribegroupmembership_one_active_per_user_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="tribegroupmembershipcharacter",
            constraint=models.UniqueConstraint(
                fields=("membership", "character"),
                name="tribes_tribegroupmembershipchar_unique_per_membership",
            ),
        ),
    ]
