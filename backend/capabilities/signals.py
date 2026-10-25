"""Recompute a fitting's requirements when anything they depend on changes."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from capabilities.tasks import queue_fitting_recompute
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingModuleSubstitution,
    EveFittingSkillOverride,
)


@receiver(post_save, sender=EveFitting)
def fitting_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        queue_fitting_recompute(instance.pk)


@receiver(post_save, sender=EveFittingSkillOverride)
@receiver(post_delete, sender=EveFittingSkillOverride)
@receiver(post_save, sender=EveFittingModuleSubstitution)
@receiver(post_delete, sender=EveFittingModuleSubstitution)
@receiver(post_save, sender=EveDoctrineFitting)
@receiver(post_delete, sender=EveDoctrineFitting)
def fitting_input_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        queue_fitting_recompute(instance.fitting_id)


@receiver(post_save, sender=EveDoctrine)
def doctrine_saved(sender, instance, raw=False, **kwargs):
    """A doctrine's type decides whether its fittings need the core tier."""
    if raw:
        return
    for fitting_id in EveDoctrineFitting.objects.filter(
        doctrine=instance
    ).values_list("fitting_id", flat=True):
        queue_fitting_recompute(fitting_id)
