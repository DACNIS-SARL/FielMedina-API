from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch, MagicMock
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

    @patch('guard.views.ShortIOService')
    def test_merchant_creation_shortens_url(self, mock_service_class):
        mock_service = MagicMock()
        mock_service.shorten_url.return_value = {
            "secureShortURL": "https://short.fielmedina.com/abcd",
            "idString": "link_12345"
        }
        mock_service_class.return_value = mock_service

        self.client.login(username="staffuser", password="Password123")
        
        form_data = {
            "name_en": "Mock Coffee Place",
            "name_fr": "Mock Café",
            "description_en": "Mock Nice coffee",
            "description_fr": "Mock Bon café",
            "category": self.category.id,
            "city": self.city.id,
            "latitude": Decimal("48.8"),
            "longitude": Decimal("2.3"),
            "address_en": "456 Avenue",
            "address_fr": "456 Avenue",
            "price_range": "€",
            "website": "https://example.com/bistro",
            "is_active": True,
            "contract_status": "active",
            
            # Formset management fields
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            
            "products-TOTAL_FORMS": "0",
            "products-INITIAL_FORMS": "0",
            "products-MIN_NUM_FORMS": "0",
            "products-MAX_NUM_FORMS": "1000",
        }
        
        response = self.client.post(reverse("guard:merchant_create"), data=form_data)
        self.assertEqual(response.status_code, 302)
        
        # Verify the merchant was created and has short fields populated
        merchant = Merchant.objects.get(name_en="Mock Coffee Place")
        self.assertEqual(merchant.short_link, "https://short.fielmedina.com/abcd")
        self.assertEqual(merchant.short_id, "link_12345")
        mock_service.shorten_url.assert_called_once_with("https://example.com/bistro", title="Merchant Website")

    @patch('guard.views.ShortIOService')
    def test_merchant_update_website_changes(self, mock_service_class):
        mock_service = MagicMock()
        mock_service.update_link.return_value = {
            "secureShortURL": "https://short.fielmedina.com/abcd-updated",
            "idString": "link_12345"
        }
        mock_service_class.return_value = mock_service

        self.client.login(username="staffuser", password="Password123")
        
        # Set initial short link fields on the merchant we're updating
        self.merchant.website = "https://example.com/bistro"
        self.merchant.short_link = "https://short.fielmedina.com/abcd"
        self.merchant.short_id = "link_12345"
        self.merchant.save()

        form_data = {
            "name_en": "Gourmet Bistro",
            "name_fr": "Bistrot Gourmet",
            "description_en": "Fine dining experience",
            "description_fr": "Une expérience gastronomique raffinée",
            "category": self.category.id,
            "city": self.city.id,
            "latitude": Decimal("48.8566"),
            "longitude": Decimal("2.3522"),
            "address_en": "123 Rue de Paris",
            "address_fr": "123 Rue de Paris",
            "price_range": "€€",
            "website": "https://example.com/bistro-new", # Changed
            "is_active": True,
            "contract_status": "active",
            
            # Formset management fields
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            
            "products-TOTAL_FORMS": "0",
            "products-INITIAL_FORMS": "0",
            "products-MIN_NUM_FORMS": "0",
            "products-MAX_NUM_FORMS": "1000",
        }
        
        response = self.client.post(reverse("guard:merchant_update", args=[self.merchant.id]), data=form_data)
        self.assertEqual(response.status_code, 302)
        
        # Verify the merchant website and short fields were updated
        merchant = Merchant.objects.get(pk=self.merchant.id)
        self.assertEqual(merchant.website, "https://example.com/bistro-new")
        self.assertEqual(merchant.short_link, "https://short.fielmedina.com/abcd-updated")
        mock_service.update_link.assert_called_once_with("link_12345", "https://example.com/bistro-new", title="Merchant Website")

    @patch('guard.views.ShortIOService')
    def test_dashboard_aggregates_merchant_stats(self, mock_service_class):
        mock_service = MagicMock()
        mock_service.get_aggregated_link_statistics.side_effect = [
            {"totalClicks": 100, "humanClicks": 80, "clickStatistics": {"timeline": []}}, # ads
            {"totalClicks": 200, "humanClicks": 160, "clickStatistics": {"timeline": []}}, # events
            {"totalClicks": 300, "humanClicks": 240, "clickStatistics": {"timeline": []}}, # merchants
        ]
        mock_service_class.return_value = mock_service

        # Ensure merchant has a short_id and is active so it's included
        self.merchant.short_id = "merchant_short_123"
        self.merchant.is_active = True
        self.merchant.save()

        self.client.login(username="staffuser", password="Password123")
        
        response = self.client.get(reverse("guard:dashboard"))
        self.assertEqual(response.status_code, 200)
        
        # Check context
        stats = response.context["stats"]
        self.assertEqual(stats["merchants"]["totalClicks"], 300)
        
        mock_service.get_aggregated_link_statistics.assert_any_call(["merchant_short_123"], "week")
