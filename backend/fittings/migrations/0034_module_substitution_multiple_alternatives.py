from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0033_evefittingchangerequest_refit_set_null"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="evefittingmodulesubstitution",
            name="unique_fitting_preferred_module_substitution",
        ),
        migrations.AddConstraint(
            model_name="evefittingmodulesubstitution",
            constraint=models.UniqueConstraint(
                fields=(
                    "fitting",
                    "preferred_module",
                    "substitute_module",
                ),
                name="unique_fitting_preferred_substitute_module",
            ),
        ),
        migrations.AlterModelOptions(
            name="evefittingmodulesubstitution",
            options={
                "ordering": [
                    "preferred_module__name",
                    "substitute_module__name",
                ],
                "verbose_name": "module substitution",
                "verbose_name_plural": "module substitutions",
            },
        ),
    ]
