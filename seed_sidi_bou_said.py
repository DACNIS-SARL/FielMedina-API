import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from guard.models import OfflineCity
from cities_light.models import City

tunis_city = City.objects.filter(id=14).first()

if tunis_city:
    obj, created = OfflineCity.objects.update_or_create(
        region_id="sidi_boussaid",
        defaults={
            "name": "Sidi Bou Said",
            "latitude": 36.8706,
            "longitude": 10.3344,
            "radius": 2500,
            "city": tunis_city,
            "is_active": True
        }
    )
    print(f"Sidi Bou Said OfflineCity object: Region ID={obj.region_id}, Created={created}")
else:
    print("Tunis city not found!")
