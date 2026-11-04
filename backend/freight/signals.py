import logging

from django.db.models import Q, signals
from django.dispatch import receiver

from eveonline.models import EveLocation
from freight.models import EveFreightRoute

logger = logging.getLogger(__name__)


def deactivate_routes_for_location(location) -> int:
    """Turn off every freight route that starts or ends at this location."""
    updated = EveFreightRoute.objects.filter(
        Q(origin_location_id=location.pk)
        | Q(destination_location_id=location.pk),
        active=True,
    ).update(active=False)
    if updated:
        logger.info(
            "Disabled %s freight route(s) touching %s",
            updated,
            location.pk,
        )
    return updated


@receiver(
    signals.pre_save,
    sender=EveLocation,
    dispatch_uid="freight_location_remember_active",
)
def remember_freight_location_active(sender, instance, **kwargs):
    """Record whether this location was a freight stop before the save."""
    previous = (
        EveLocation.all_objects.filter(pk=instance.pk)
        .values_list("freight_active", flat=True)
        .first()
    )
    instance.freight_was_active = bool(previous)


@receiver(
    signals.post_save,
    sender=EveLocation,
    dispatch_uid="freight_location_disable_routes",
)
def disable_routes_when_freight_location_turns_off(
    sender, instance, created, update_fields=None, **kwargs
):
    """Disabling a freight location also disables routes to and from it."""
    if created:
        return
    if update_fields is not None and "freight_active" not in update_fields:
        return
    if not getattr(instance, "freight_was_active", False):
        return
    if instance.freight_active:
        return
    deactivate_routes_for_location(instance)
