from django.db import models


class SystemSovereigntyConfig(models.Model):
    """One row per system we track for sovereignty (workforce/power computed from SDE + upgrades)."""

    system_id = models.BigIntegerField(unique=True)
    system_name = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "System sovereignty config"
        verbose_name_plural = "System sovereignty configs"

    def __str__(self):
        return f"{self.system_name or self.system_id} ({self.system_id})"


class SovereigntyUpgradeType(models.Model):
    """Catalog of sovereignty upgrade types (costs and optional conversion / mining level)."""

    name = models.CharField(max_length=255)
    eve_type_id = models.IntegerField(null=True, blank=True)

    power_cost = models.IntegerField(default=0)
    workforce_cost = models.IntegerField(default=0)

    # Resource generation: Power Monitoring Division (workforce -> power)
    produces_power = models.IntegerField(null=True, blank=True)
    consumes_workforce = models.IntegerField(null=True, blank=True)
    # Resource generation: Workforce Mecha-Tooling (power -> workforce)
    produces_workforce = models.IntegerField(null=True, blank=True)
    consumes_power = models.IntegerField(null=True, blank=True)

    # Mining arrays: 1 = small (1h), 2 = medium (4h20m), 3 = large (12h). Null/0 = not a mining array.
    mining_upgrade_level = models.IntegerField(
        null=True, blank=True, default=None
    )

    class Meta:
        verbose_name = "Sovereignty upgrade type"
        verbose_name_plural = "Sovereignty upgrade types"

    def __str__(self):
        return self.name


class SystemSovereigntyUpgrade(models.Model):
    """Which upgrade type is installed in which system."""

    system = models.ForeignKey(
        SystemSovereigntyConfig,
        on_delete=models.CASCADE,
        related_name="installed_upgrades",
    )
    upgrade_type = models.ForeignKey(
        SovereigntyUpgradeType,
        on_delete=models.CASCADE,
        related_name="system_installations",
    )

    class Meta:
        unique_together = ("system", "upgrade_type")
        verbose_name = "System sovereignty upgrade"
        verbose_name_plural = "System sovereignty upgrades"

    def __str__(self):
        return f"{self.system} — {self.upgrade_type.name}"


class SystemBaseResources(models.Model):
    """Cached base power/workforce per system from SDE (optional; populated by management command)."""

    system_id = models.BigIntegerField(unique=True)
    base_power = models.IntegerField(default=0)
    base_workforce = models.IntegerField(default=0)

    class Meta:
        verbose_name = "System base resources"
        verbose_name_plural = "System base resources"

    def __str__(self):
        return f"System {self.system_id} (P:{self.base_power} W:{self.base_workforce})"
