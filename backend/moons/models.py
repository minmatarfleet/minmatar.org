from django.db import models

ore_yield_map = {
    "Bitumens": {
        "Hydrocarbons": 65,
        "Pyerite": 6000,
        "Mexallon": 400,
    },
    "Coesite": {
        "Silicates": 65,
        "Pyerite": 2000,
        "Mexallon": 400,
    },
    "Sylvite": {
        "Evaporite Deposits": 65,
        "Pyerite": 4000,
        "Mexallon": 400,
    },
    "Zeolites": {
        "Atmospheric Gases": 65,
        "Pyerite": 8000,
        "Mexallon": 400,
    },
    "Cobaltite": {
        "Cobalt": 40,
    },
    "Euxenite": {
        "Scandium": 40,
    },
    "Scheelite": {
        "Tungsten": 40,
    },
    "Titanite": {
        "Titanium": 40,
    },
    "Chromite": {
        "Chromium": 40,
        "Hydrocarbons": 10,
    },
    "Otavite": {
        "Cadmium": 40,
        "Atmospheric Gases": 10,
    },
    "Sperrylite": {
        "Platinum": 40,
        "Evaporite Deposits": 10,
    },
    "Vanadinite": {
        "Vanadium": 40,
        "Silicates": 10,
    },
    "Carnotite": {
        "Technetium": 50,
        "Cobalt": 10,
        "Atmospheric Gases": 15,
    },
    "Cinnabar": {
        "Mercury": 50,
        "Tungsten": 10,
        "Evaporite Deposits": 15,
    },
    "Pollucite": {
        "Caesium": 50,
        "Scandium": 10,
        "Hydrocarbons": 15,
    },
    "Zircon": {
        "Hafnium": 50,
        "Titanium": 10,
        "Silicates": 15,
    },
    "Loparite": {
        "Promethium": 22,
        "Platinum": 10,
        "Scandium": 20,
        "Hydrocarbons": 20,
    },
    "Monazite": {
        "Neodymium": 22,
        "Chromium": 10,
        "Tungsten": 20,
        "Evaporite Deposits": 20,
    },
    "Xenotime": {
        "Dysprosium": 22,
        "Vanadium": 10,
        "Cobalt": 20,
        "Atmospheric Gases": 20,
    },
    "Ytterbite": {
        "Thulium": 22,
        "Cadmium": 10,
        "Titanium": 20,
        "Silicates": 20,
    },
}


# Create your models here.
class EveMoon(models.Model):
    system = models.CharField(max_length=100)
    planet = models.IntegerField()
    moon = models.IntegerField()
    reported_by = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    owned_by_ticker = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.system} - {self.planet} - {self.moon}"

    class Meta:
        unique_together = ("system", "planet", "moon")


class EveMoonDistribution(models.Model):
    ore_choices = (
        ("Bitumens", "Bitumens"),
        ("Coesite", "Coesite"),
        ("Sylvite", "Sylvite"),
        ("Zeolites", "Zeolites"),
        ("Cobaltite", "Cobaltite"),
        ("Euxenite", "Euxenite"),
        ("Scheelite", "Scheelite"),
        ("Titanite", "Titanite"),
        ("Chromite", "Chromite"),
        ("Otavite", "Otavite"),
        ("Sperrylite", "Sperrylite"),
        ("Vanadinite", "Vanadinite"),
        ("Carnotite", "Carnotite"),
        ("Cinnabar", "Cinnabar"),
        ("Pollucite", "Pollucite"),
        ("Zircon", "Zircon"),
        ("Loparite", "Loparite"),
        ("Monazite", "Monazite"),
        ("Xenotime", "Xenotime"),
        ("Ytterbite", "Ytterbite"),
    )

    moon = models.ForeignKey(EveMoon, on_delete=models.CASCADE)
    ore = models.CharField(max_length=100, choices=ore_choices)
    yield_percent = models.DecimalField(max_digits=11, decimal_places=10)
