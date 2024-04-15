from django.db import models


# Create your models here.


class EveFittingTag(models.Model):
    """
    Model for storing tags for fittings
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return str(self.name)


class EveFitting(models.Model):
    """
    Model for storing fittings
    """

    name = models.CharField(max_length=255, unique=True)
    ship_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()
    tags = models.ManyToManyField(EveFittingTag, blank=True)

    # fitting info
    eft_format = models.TextField()
    latest_version = models.CharField(max_length=255)

    def __str__(self):
        return str(self.name)


class EveDoctrine(models.Model):
    """
    Model for storing doctrines
    """

    type_choices = (
        ("armor", "Armor"),
        ("shield", "Shield"),
        ("kitchen_sink", "Kitchen Sink"),
    )
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255, choices=type_choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()

    def __str__(self):
        return str(self.name)


class EveDoctrineFitting(models.Model):
    """
    Model for storing fittings in a doctrine
    """

    role_choices = (
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("support", "Support"),
    )

    doctrine = models.ForeignKey(EveDoctrine, on_delete=models.CASCADE)
    fitting = models.ForeignKey(EveFitting, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, choices=role_choices)

    def __str__(self):
        return f"{self.doctrine.name} - {self.fitting.name}"
