import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cities_light.models import Country, City

tunisia = Country.objects.filter(name__icontains="Tunisia").first()
if tunisia:
    city, created = City.objects.get_or_create(
        name="Zaghouan",
        country=tunisia,
        defaults={
            "display_name": "Zaghouan, Tunisia",
            "search_names": "Zaghouan",
            "latitude": 36.4011,
            "longitude": 10.1425,
        }
    )
    print(f"Zaghouan City object: ID={city.id}, Created={created}")
else:
    print("Tunisia not found!")
