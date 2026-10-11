import json
from decimal import Decimal

from django.test import TestCase

from guard.models import Hiking, Merchant, MerchantProduct

QUERY = """
{
  hikings { id latitude longitude }
  merchants(limit: 100) { id latitude longitude products { id price } }
}
"""


class DecimalFloatFieldsTests(TestCase):
    def setUp(self):
        Hiking.objects.create(
            name_en="Coastal walk",
            name_fr="Balade côtière",
            description_en="Walk",
            description_fr="Balade",
            latitude=Decimal("35.827500"),
            longitude=Decimal("10.640300"),
        )
        merchant = Merchant.objects.create(
            name_en="Dar Test",
            name_fr="Dar Test",
            description_en="Test",
            description_fr="Test",
            latitude=Decimal("35.825600"),
            longitude=Decimal("10.641100"),
            is_active=True,
            contract_status="active",
        )
        MerchantProduct.objects.create(merchant=merchant, name_en="Couscous", name_fr="Couscous", price=Decimal("18.500"))
        MerchantProduct.objects.create(merchant=merchant, name_en="Tea", name_fr="Thé")

    def test_decimal_columns_serialize_as_floats(self):
        response = self.client.post("/graphql", data=json.dumps({"query": QUERY}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("errors", body, body.get("errors"))

        hiking = body["data"]["hikings"][0]
        self.assertEqual((hiking["latitude"], hiking["longitude"]), (35.8275, 10.6403))

        merchant = body["data"]["merchants"][0]
        self.assertEqual((merchant["latitude"], merchant["longitude"]), (35.8256, 10.6411))
        self.assertEqual(sorted(product["price"] for product in merchant["products"] if product["price"] is not None), [18.5])
        self.assertIn(None, [product["price"] for product in merchant["products"]])
