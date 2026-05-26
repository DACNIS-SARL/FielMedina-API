from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, time
from decimal import Decimal

from cities_light.models import City, Country
from guard.models import Merchant, MerchantCategory
from guard.forms import MerchantCategoryForm, MerchantForm

User = get_user_model()

class MerchantModuleTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create Country and City
        self.country = Country.objects.create(name="France", code2="FR")
        self.city = City.objects.create(name="Paris", country=self.country)

        # Create a non-staff user
        self.user = User.objects.create_user(
            username="regularuser",
            email="regular@example.com",
            password="Password123"
        )
        # Create a staff user
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="Password123",
            is_staff=True
        )
        # Create a category
        self.category = MerchantCategory.objects.create(
            name_en="Food & Drink",
            name_fr="Nourriture & Boisson",
            icon="cart"
        )
        # Create a merchant
        self.merchant = Merchant.objects.create(
            name_en="Gourmet Bistro",
            name_fr="Bistrot Gourmet",
            description_en="Fine dining experience",
            description_fr="Une expérience gastronomique raffinée",
            category=self.category,
            city=self.city,
            latitude=Decimal("48.8566"),
            longitude=Decimal("2.3522"),
            address_en="123 Rue de Paris",
            address_fr="123 Rue de Paris",
            price_range="€€",
            is_active=True,
            contract_status="active",
            contract_start=date(2026, 1, 1),
            contract_end=date(2026, 12, 31)
        )

    def test_merchant_category_str(self):
        self.assertEqual(str(self.category), "Food & Drink")

    def test_merchant_str(self):
        self.assertEqual(str(self.merchant), "Gourmet Bistro")

    def test_merchant_contract_expiry_on_save(self):
        # Create a merchant with an expired contract end date
        merchant_expired = Merchant(
            name_en="Old Shop",
            name_fr="Vieux Magasin",
            description_en="Old description",
            description_fr="Ancienne description",
            category=self.category,
            city=self.city,
            latitude=Decimal("0.0"),
            longitude=Decimal("0.0"),
            contract_status="active",
            contract_start=date(2025, 1, 1),
            contract_end=date(2025, 5, 25), # Before current date 2026-05-26
            is_active=True
        )
        merchant_expired.save()
        # Should auto-update contract status to expired and is_active to False
        self.assertEqual(merchant_expired.contract_status, "expired")
        self.assertFalse(merchant_expired.is_active)

    def test_merchant_category_form_valid(self):
        form_data = {
            "name_en": "Shopping",
            "name_fr": "Shopping FR",
            "icon": "bag"
        }
        form = MerchantCategoryForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_merchant_category_form_invalid(self):
        form_data = {
            "icon": "bag"
        }
        form = MerchantCategoryForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_merchant_form_valid(self):
        form_data = {
            "name_en": "Coffee Place",
            "name_fr": "Café",
            "description_en": "Nice coffee",
            "description_fr": "Bon café",
            "category": self.category.id,
            "city": self.city.id,
            "latitude": Decimal("48.8"),
            "longitude": Decimal("2.3"),
            "address_en": "456 Avenue",
            "address_fr": "456 Avenue",
            "price_range": "€",
            "open_from": "08:00",
            "open_to": "18:00",
            "is_active": True,
            "contract_status": "active",
            "contract_start": "2026-01-01",
            "contract_end": "2026-12-31"
        }
        form = MerchantForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_merchant_form_invalid_dates(self):
        form_data = {
            "name_en": "Coffee Place",
            "name_fr": "Café",
            "description_en": "Nice coffee",
            "description_fr": "Bon café",
            "category": self.category.id,
            "city": self.city.id,
            "latitude": Decimal("48.8"),
            "longitude": Decimal("2.3"),
            "contract_start": "2026-12-31",
            "contract_end": "2026-01-01" # End before start
        }
        form = MerchantForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("contract_end", form.errors)

    def test_views_anonymous_redirect(self):
        # Anonymous users should be redirected to login
        url_list = [
            reverse("guard:merchantsList"),
            reverse("guard:merchant_create"),
            reverse("guard:merchant_update", args=[self.merchant.id]),
            reverse("guard:merchant_delete", args=[self.merchant.id]),
            reverse("guard:merchant_category_create"),
            reverse("guard:merchant_category_update", args=[self.category.id]),
            reverse("guard:merchant_category_delete", args=[self.category.id]),
        ]
        for url in url_list:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)

    def test_views_regular_user_forbidden(self):
        self.client.login(username="regularuser", password="Password123")
        url_list = [
            reverse("guard:merchantsList"),
            reverse("guard:merchant_create"),
            reverse("guard:merchant_update", args=[self.merchant.id]),
            reverse("guard:merchant_delete", args=[self.merchant.id]),
            reverse("guard:merchant_category_create"),
            reverse("guard:merchant_category_update", args=[self.category.id]),
            reverse("guard:merchant_category_delete", args=[self.category.id]),
        ]
        for url in url_list:
            response = self.client.get(url)
            self.assertIn(response.status_code, [302, 403])

    def test_views_staff_user_success(self):
        self.client.login(username="staffuser", password="Password123")
        
        # Get List View
        response = self.client.get(reverse("guard:merchantsList"))
        self.assertEqual(response.status_code, 200)

        # Get Create View
        response = self.client.get(reverse("guard:merchant_create"))
        self.assertEqual(response.status_code, 200)

        # Get Update View
        response = self.client.get(reverse("guard:merchant_update", args=[self.merchant.id]))
        self.assertEqual(response.status_code, 200)

        # Get Category Create View
        response = self.client.get(reverse("guard:merchant_category_create"))
        self.assertEqual(response.status_code, 200)

        # Get Category Update View
        response = self.client.get(reverse("guard:merchant_category_update", args=[self.category.id]))
        self.assertEqual(response.status_code, 200)
