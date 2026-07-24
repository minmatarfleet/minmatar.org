import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_contacts_to_accounts(apps, schema_editor):
    IndustryLoyaltyPointAccount = apps.get_model(
        "industry", "IndustryLoyaltyPointAccount"
    )
    IndustryLoyaltyPointContact = apps.get_model(
        "industry", "IndustryLoyaltyPointContact"
    )
    for contact in IndustryLoyaltyPointContact.objects.all():
        account = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point_id=contact.loyalty_point_id,
            name=contact.character_name,
            role="seller",
            eve_character_id=contact.eve_character_id,
            user_id=contact.user_id,
            is_active=contact.is_active,
            notes=contact.notes or "",
        )
        contact.account = account
        contact.save(update_fields=["account"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0097_industry_job_status_blueprint_id_idx"),
        ("industry", "0028_seed_militia_loyalty_points"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IndustryLoyaltyPointAccount",
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
                ("name", models.CharField(max_length=128)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("seller", "Seller"),
                            ("stockpile", "Stockpile"),
                        ],
                        db_index=True,
                        default="seller",
                        max_length=16,
                    ),
                ),
                (
                    "isk_per_lp",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text=(
                            "Current offer ISK/LP for this holder. Falls back "
                            "to the currency default when empty. Lot history "
                            "uses each ledger entry's price."
                        ),
                        null=True,
                    ),
                ),
                (
                    "corporation_name",
                    models.CharField(blank=True, max_length=128),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "eve_character",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="loyalty_point_accounts",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "loyalty_point",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounts",
                        to="industry.industryloyaltypoint",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="loyalty_point_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Industry loyalty point account",
                "verbose_name_plural": "Industry loyalty point accounts",
                "ordering": ["loyalty_point__name", "name"],
            },
        ),
        migrations.CreateModel(
            name="IndustryLoyaltyPointLedgerEntry",
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
                    "amount",
                    models.BigIntegerField(
                        help_text=(
                            "Signed LP change: positive credit, negative debit."
                        ),
                    ),
                ),
                (
                    "isk_per_lp",
                    models.PositiveIntegerField(
                        help_text=(
                            "ISK/LP for this lot (required; e.g. 825 or 850)."
                        ),
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "balance_after",
                    models.BigIntegerField(
                        help_text=(
                            "Account balance after this entry was posted."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ledger_entries",
                        to="industry.industryloyaltypointaccount",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="loyalty_point_ledger_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Industry loyalty point ledger entry",
                "verbose_name_plural": (
                    "Industry loyalty point ledger entries"
                ),
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="industryloyaltypointcontact",
            name="account",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contacts",
                to="industry.industryloyaltypointaccount",
            ),
        ),
        migrations.RunPython(migrate_contacts_to_accounts, noop_reverse),
        migrations.RemoveField(
            model_name="industryloyaltypointcontact",
            name="loyalty_point",
        ),
        migrations.AlterField(
            model_name="industryloyaltypointcontact",
            name="account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contacts",
                to="industry.industryloyaltypointaccount",
            ),
        ),
        migrations.AlterModelOptions(
            name="industryloyaltypointcontact",
            options={
                "ordering": [
                    "account__loyalty_point__name",
                    "character_name",
                ],
                "verbose_name": "Industry loyalty point contact",
                "verbose_name_plural": "Industry loyalty point contacts",
            },
        ),
        migrations.AddConstraint(
            model_name="industryloyaltypointaccount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("loyalty_point", "name"),
                name="uniq_active_lp_account_name_per_currency",
            ),
        ),
    ]
