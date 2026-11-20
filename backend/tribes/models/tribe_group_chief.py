from django.db import models


class TribeGroupChief(models.Model):
    """
    One of a tribe group's chief seats: one per timezone region.

    A group has up to three chiefs (US, EU, AU), each covering their own
    evening. Every seated chief can manage the group and is pinged when it
    needs a chief. A group with no seat filled is led by its tribe chief as
    interim chief (docs/tribes/interim-chiefs.md).
    """

    REGION_US = "US"
    REGION_EU = "EU"
    REGION_AU = "AU"
    # Seat order on pages and in "the first chief" fallbacks.
    REGIONS = (REGION_US, REGION_EU, REGION_AU)
    REGION_CHOICES = [
        (REGION_US, "USTZ"),
        (REGION_EU, "EUTZ"),
        (REGION_AU, "AUTZ"),
    ]

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="chief_seats",
    )
    region = models.CharField(max_length=2, choices=REGION_CHOICES)
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="tribe_group_chief_seats",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tribe_group} {self.region}: {self.user}"

    class Meta:
        ordering = ["tribe_group_id", "region"]
        constraints = [
            models.UniqueConstraint(
                fields=["tribe_group", "region"],
                name="tribes_group_chief_one_per_region",
            ),
            models.UniqueConstraint(
                fields=["tribe_group", "user"],
                name="tribes_group_chief_one_seat_per_pilot",
            ),
        ]
