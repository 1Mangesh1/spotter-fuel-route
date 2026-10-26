from django.db import models


class FuelStation(models.Model):
    """A truck stop from the Spotter price list.

    The price list has no coordinates. `lat` and `lon` are the Census centroid of the
    station's city, so they are approximate.
    """

    opis_id = models.PositiveIntegerField(unique=True, help_text="OPIS Truckstop ID")
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    price = models.DecimalField(
        max_digits=6, decimal_places=3, help_text="Retail price, USD per gallon"
    )
    lat = models.FloatField()
    lon = models.FloatField()

    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.state})"
