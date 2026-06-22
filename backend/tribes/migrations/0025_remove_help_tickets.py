from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tribes", "0024_help_tickets"),
        ("help_tickets", "0002_migrate_from_tribes"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tribegroup",
            name="help_ticket_title",
        ),
        migrations.DeleteModel(
            name="HelpTicket",
        ),
        migrations.DeleteModel(
            name="HelpTicketPanel",
        ),
    ]
