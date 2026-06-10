import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from guard.models import OfflineCity
from cities_light.models import City

cities_to_add = [
    {"region_id": "sousse_medina", "name": "Sousse Medina", "lat": 35.825892, "lon": 10.637448, "radius": 2000, "city_id": 15},
    {"region_id": "monastir_medina", "name": "Monastir Medina", "lat": 35.7780, "lon": 10.8262, "radius": 2000, "city_id": 18},
    {"region_id": "tunis_medina", "name": "Tunis Medina", "lat": 36.7992, "lon": 10.1706, "radius": 2500, "city_id": 14},
    {"region_id": "zaghouan_south", "name": "Zaghouan South", "lat": 36.33297, "lon": 10.22389, "radius": 5000, "city_id": 142},
]

for data in cities_to_add:
    city_obj = City.objects.filter(id=data["city_id"]).first()
    obj, created = OfflineCity.objects.update_or_create(
        region_id=data["region_id"],
        defaults={
            "name": data["name"],
            "latitude": data["lat"],
            "longitude": data["lon"],
            "radius": data["radius"],
            "city": city_obj,
            "is_active": True
        }
    )
    if created:
        print(f"Created {data['name']}")
    else:
        print(f"Updated {data['name']}")
