from django.db import migrations


def migrate_from_tribes(apps, schema_editor):
    TribeGroup = apps.get_model("tribes", "TribeGroup")
    HelpRequestCategory = apps.get_model("help_tickets", "HelpRequestCategory")
    OldHelpTicket = apps.get_model("tribes", "HelpTicket")
    NewHelpTicket = apps.get_model("help_tickets", "HelpTicket")
    OldHelpTicketPanel = apps.get_model("tribes", "HelpTicketPanel")
    NewHelpTicketPanel = apps.get_model("help_tickets", "HelpTicketPanel")

    category_by_tribe_group: dict[int, int] = {}
    for tribe_group in TribeGroup.objects.all():
        title = getattr(tribe_group, "help_ticket_title", "") or ""
        if not title:
            continue
        category, _ = HelpRequestCategory.objects.get_or_create(
            tribe_group_id=tribe_group.pk,
            defaults={
                "title": title,
                "description": tribe_group.description or "",
                "code": tribe_group.code,
                "sort_order": tribe_group.pk,
                "is_active": tribe_group.is_active,
            },
        )
        category_by_tribe_group[tribe_group.pk] = category.pk

    for old in OldHelpTicket.objects.all():
        category_id = category_by_tribe_group.get(old.tribe_group_id)
        if category_id is None:
            continue
        NewHelpTicket.objects.update_or_create(
            pk=old.pk,
            defaults={
                "category_id": category_id,
                "opener_discord_id": old.opener_discord_id,
                "opener_id": old.opener_id,
                "thread_id": old.thread_id,
                "thread_name": old.thread_name,
                "body": old.body,
                "status": old.status,
                "opened_at": old.opened_at,
                "closed_at": old.closed_at,
                "closed_by_discord_id": old.closed_by_discord_id,
                "closed_by_id": old.closed_by_id,
                "close_reason": old.close_reason,
            },
        )

    for old in OldHelpTicketPanel.objects.all():
        NewHelpTicketPanel.objects.update_or_create(
            pk=old.pk,
            defaults={
                "channel_id": old.channel_id,
                "message_id": old.message_id,
                "content_hash": old.content_hash,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("help_tickets", "0001_initial"),
        ("tribes", "0024_help_tickets"),
    ]

    operations = [
        migrations.RunPython(migrate_from_tribes, migrations.RunPython.noop),
    ]
