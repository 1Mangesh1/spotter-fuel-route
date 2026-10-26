from django.contrib import admin

from planner.models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ["opis_id", "name", "city", "state", "price"]
    search_fields = ["name", "city", "state"]
