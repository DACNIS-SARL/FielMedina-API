import datetime
import io
import json
import os
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from cities_light.models import City, Country, Region, SubRegion
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from api.authentication import issue_token
from guard.models import (
    Event,
    EventCategory,
    Hiking,
    Location,
    LocationCategory,
    Merchant,
    MerchantCategory,
    OfflineCity,
    PublicTransport,
    PublicTransportType,
    Tip,
)
from shared.models import Page

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp(prefix="fielmedina-content-tests-")
PAYLOAD = "ok error fieldErrors { field code } id"


def png(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (29, 53, 87)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def aac(name="story.aac"):
    return SimpleUploadedFile(name, b"\xff\xf1\x50\x80" + b"\x00" * 64, content_type="audio/aac")


def glb(name="mosque.glb"):
    return SimpleUploadedFile(name, b"glTF\x02\x00\x00\x00" + b"\x00" * 64, content_type="model/gltf-binary")


@override_settings(
    MEDIA_ROOT=MEDIA_ROOT,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class SpaceContentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        short_io = mock.patch("api.space.ShortIOService")
        self.short_io = short_io.start().return_value
        self.short_io.shorten_url.return_value = {"secureShortURL": "https://go.test/dar", "idString": "lnk_m"}
        self.short_io.update_link.return_value = {"secureShortURL": "https://go.test/dar"}
        self.addCleanup(short_io.stop)
        for method in ("send_new_location_notification", "send_new_hiking_notification", "send_new_tip_notification", "send_new_event_notification"):
            patcher = mock.patch(f"guard.notifications.NotificationService.{method}")
            patcher.start()
            self.addCleanup(patcher.stop)

        self.country = Country.objects.create(name="Tunisia", name_ascii="Tunisia", code2="TN", code3="TUN", continent="AF", tld="tn", phone="216")
        self.region = Region.objects.create(name="Sousse Governorate", name_ascii="Sousse Governorate", display_name="Sousse Governorate", country=self.country, geoname_code="23")
        self.other_region = Region.objects.create(name="Tunis Governorate", name_ascii="Tunis Governorate", display_name="Tunis Governorate", country=self.country, geoname_code="38")
        self.city = City.objects.create(name="Sousse", name_ascii="Sousse", display_name="Sousse", country=self.country, region=self.region)
        self.medina = SubRegion.objects.create(name="Sousse Medina", name_ascii="Sousse Medina", display_name="Sousse Medina", country=self.country, region=self.region, geoname_code="2464")
        self.kantaoui = SubRegion.objects.create(name="Hammam Sousse", name_ascii="Hammam Sousse", display_name="Hammam Sousse", country=self.country, region=self.region, geoname_code="2465")
        self.bab_bhar = SubRegion.objects.create(name="Bab El Bhar", name_ascii="Bab El Bhar", display_name="Bab El Bhar", country=self.country, region=self.other_region, geoname_code="3801")
        self.location_category = LocationCategory.objects.create(name_en="Mosque", name_fr="Mosquée")
        self.merchant_category = MerchantCategory.objects.create(name_en="Restaurant", name_fr="Restaurant")
        self.transport_type = PublicTransportType.objects.create(name_en="Bus", name_fr="Bus")

        self.staff = User.objects.create_user("equipe", "equipe@example.com", "Sidi-Bou-2026", is_staff=True)
        self.partner = User.objects.create_user("atelier", "atelier@example.com", "Sidi-Bou-2026")
        self.staff_token = issue_token(self.staff, False)[0]
        self.partner_token = issue_token(self.partner, False)[0]

    def graphql(self, query, variables=None, token=None, files=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token or self.staff_token}"}
        if files:
            data = {"operations": json.dumps({"query": query, "variables": variables or {}})}
            data["map"] = json.dumps({str(index): [f"variables.{path}"] for index, path in enumerate(files)})
            data.update({str(index): upload for index, upload in enumerate(files.values())})
            response = self.client.post("/graphql", data=data, **headers)
        else:
            response = self.client.post(
                "/graphql", data=json.dumps({"query": query, "variables": variables or {}}), content_type="application/json", **headers
            )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertNotIn("errors", body, body.get("errors"))
        return body["data"]

    def mutate(self, name, signature, arguments, variables, token=None, files=None):
        return self.graphql(
            f"mutation({signature}) {{ result: {name}({arguments}) {{ {PAYLOAD} }} }}", variables, token=token, files=files
        )["result"]

    def field_errors(self, payload):
        return {item["field"]: item["code"] for item in payload["fieldErrors"]}

    def location_input(self, **overrides):
        values = {
            "nameEn": "Great Mosque",
            "nameFr": "Grande Mosquée",
            "storyEn": "<p>Built in 851.</p>",
            "storyFr": "<p>Construite en 851.</p>",
            "category": str(self.location_category.pk),
            "city": str(self.city.pk),
            "latitude": "35.8275",
            "longitude": "10.6403",
            "openFrom": "08:00",
            "openTo": "13:30",
            "admissionFee": "5",
            "closedDays": ["6"],
            "isActiveAds": True,
            "modelScale": "1.5",
            "modelRotation": "90",
            "modelAltitude": "2",
        }
        values.update(overrides)
        return values

    def save_location(self, input, id=None, files=None):
        variables = {"input": input, "id": id}
        if files:
            variables.update({key.split(".")[0]: ([None] * 1 if key.startswith("images") else None) for key in files})
        return self.mutate(
            "saveLocation",
            "$input: SpaceLocationInput!, $id: ID, $images: [Upload!], $voiceoverEn: Upload, $voiceoverFr: Upload, $model3d: Upload",
            "input: $input, id: $id, images: $images, voiceoverEn: $voiceoverEn, voiceoverFr: $voiceoverFr, model3d: $model3d",
            variables,
            files=files,
        )

    def test_content_is_staff_only(self):
        payload = self.mutate("saveTip", "$input: SpaceTipInput!", "input: $input", {"input": {"city": str(self.city.pk)}}, token=self.partner_token)
        self.assertEqual(payload["error"], "forbidden")
        response = self.client.post(
            "/graphql",
            data=json.dumps({"query": "{ spaceMerchants { id } }"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.partner_token}",
        )
        self.assertIn("forbidden", response.json()["errors"][0]["message"])

    def test_location_with_audio_and_model(self):
        payload = self.save_location(
            self.location_input(),
            files={"images.0": png(), "voiceoverEn": aac(), "model3d": glb()},
        )
        self.assertTrue(payload["ok"], payload)
        location = Location.objects.get(pk=payload["id"])
        self.assertEqual(location.country, self.country)
        self.assertEqual(location.latitude, Decimal("35.827500"))
        self.assertEqual(list(location.closedDays.values_list("day", flat=True)), [6])
        self.assertEqual(location.model_scale, 1.5)
        self.assertTrue(location.voiceover_en.name.endswith(".aac"))
        self.assertTrue(location.model_3d.name.endswith(".glb"))
        old_audio = location.voiceover_en.path
        old_model = location.model_3d.path

        detail = self.graphql(
            "query($id: ID!) { spaceLocation(id: $id) { nameFr openFrom closedDays isActiveAds voiceoverEn model3d images { url } admissionFee } }",
            {"id": payload["id"]},
        )["spaceLocation"]
        self.assertEqual(detail["openFrom"], "08:00")
        self.assertEqual(detail["closedDays"], [6])
        self.assertTrue(detail["isActiveAds"])
        url = detail["images"][0]["url"]

        payload = self.save_location(
            self.location_input(keepImages=[url], removeVoiceoverEn=True, closedDays=[]),
            id=payload["id"],
            files={"model3d": glb("mosque-v2.glb")},
        )
        self.assertTrue(payload["ok"], payload)
        location.refresh_from_db()
        self.assertFalse(location.voiceover_en)
        self.assertFalse(os.path.exists(old_audio))
        self.assertFalse(os.path.exists(old_model))
        self.assertTrue(location.model_3d.name.endswith("mosque-v2.glb"))
        self.assertEqual(location.closedDays.count(), 0)
        self.assertEqual(location.images.count(), 1)

        model_path = location.model_3d.path
        deleted = self.mutate("deleteLocation", "$id: ID!", "id: $id", {"id": str(location.pk)})
        self.assertTrue(deleted["ok"])
        self.assertFalse(os.path.exists(model_path))

    def test_location_validation(self):
        fake_audio = SimpleUploadedFile("story.aac", b"<html></html>", content_type="audio/aac")
        payload = self.save_location(
            self.location_input(storyFr="<p></p>", latitude="95", category="", closedDays=["8"], modelRotation="400"),
            files={"voiceoverFr": fake_audio, "model3d": SimpleUploadedFile("m.gltf", b"{}")},
        )
        self.assertEqual(
            self.field_errors(payload),
            {
                "story": "required",
                "category": "required",
                "coordinates": "coordinates",
                "closedDays": "invalidChoice",
                "modelRotation": "number",
                "images": "required",
                "voiceoverFr": "fileType",
                "model3d": "fileType",
            },
        )

    def merchant_input(self, **overrides):
        values = {
            "nameEn": "Dar Test",
            "nameFr": "Dar Test",
            "descriptionEn": "<p>Couscous on Fridays.</p>",
            "descriptionFr": "<p>Couscous le vendredi.</p>",
            "category": str(self.merchant_category.pk),
            "city": str(self.city.pk),
            "latitude": "35.8256",
            "longitude": "10.6411",
            "website": "https://dar.example",
            "priceRange": "€€",
            "openFrom": "12:00",
            "openTo": "23:00",
            "isActive": False,
            "contractStatus": "pending",
            "contractStart": "2026-10-01",
            "contractEnd": "2027-10-01",
            "products": [{"nameEn": "Couscous", "nameFr": "Couscous", "price": "18.5"}, {"nameEn": "Tea", "nameFr": "Thé"}],
        }
        values.update(overrides)
        return values

    def save_merchant(self, input, id=None, files=None, product_slots=0):
        variables = {"input": input, "id": id, "cover": None, "images": None, "productImages": [None] * product_slots or None}
        for key in files or {}:
            if key.startswith("images"):
                variables["images"] = [None]
        return self.mutate(
            "saveMerchant",
            "$input: SpaceMerchantInput!, $id: ID, $cover: Upload, $images: [Upload!], $productImages: [Upload]",
            "input: $input, id: $id, cover: $cover, images: $images, productImages: $productImages",
            variables,
            files=files,
        )

    def test_merchant_products_contract_and_short_link(self):
        payload = self.save_merchant(self.merchant_input(), files={"cover": png("cover.png"), "productImages.0": png("couscous.png")}, product_slots=2)
        self.assertTrue(payload["ok"], payload)
        merchant = Merchant.objects.get(pk=payload["id"])
        self.assertEqual(merchant.short_link, "https://go.test/dar")
        self.assertFalse(merchant.is_active)
        products = list(merchant.products.order_by("pk"))
        self.assertEqual([(product.name_fr, product.price) for product in products], [("Couscous", Decimal("18.50")), ("Thé", None)])
        self.assertTrue(products[0].image)
        listed = self.graphql("{ spaceMerchants { id isActive contractStatus } }")["spaceMerchants"]
        self.assertEqual(listed, [{"id": payload["id"], "isActive": False, "contractStatus": "pending"}])

        tea_id = str(products[1].pk)
        payload = self.save_merchant(
            self.merchant_input(products=[{"id": tea_id, "nameEn": "Mint tea", "nameFr": "Thé à la menthe", "price": "3"}]),
            id=payload["id"],
        )
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(list(merchant.products.values_list("pk", "name_fr", "price")), [(int(tea_id), "Thé à la menthe", Decimal("3.00"))])
        self.assertFalse(os.path.exists(products[0].image.path))
        self.short_io.update_link.assert_not_called()

        payload = self.save_merchant(
            self.merchant_input(openFrom="23:00", openTo="12:00", contractEnd="2026-01-01", priceRange="$$", products=[{"nameEn": "Tea"}]),
            id=str(merchant.pk),
        )
        self.assertEqual(
            self.field_errors(payload),
            {"openTo": "timeOrder", "contractEnd": "dateOrder", "priceRange": "invalidChoice", "products": "productName"},
        )
        missing_cover = self.save_merchant(self.merchant_input())
        self.assertEqual(self.field_errors(missing_cover), {"cover": "required"})

    def test_hiking_stops_keep_their_order(self):
        first = Location.objects.create(name_en="Gate", name_fr="Porte", story_en="s", story_fr="s", latitude=1, longitude=1, city=self.city)
        second = Location.objects.create(name_en="Kasbah", name_fr="Kasbah", story_en="s", story_fr="s", latitude=1, longitude=1, city=self.city)
        signature = "$input: SpaceHikingInput!, $id: ID, $images: [Upload!]"
        arguments = "input: $input, id: $id, images: $images"
        base = {"nameEn": "Ramparts walk", "nameFr": "Balade des remparts", "descriptionEn": "<p>Walk</p>", "descriptionFr": "<p>Balade</p>", "city": str(self.city.pk)}
        payload = self.mutate("saveHiking", signature, arguments, {"input": {**base, "stops": [str(second.pk), str(first.pk)]}, "images": [None]}, files={"images.0": png()})
        self.assertTrue(payload["ok"], payload)
        hiking = Hiking.objects.get(pk=payload["id"])
        stops = self.graphql("query($id: ID!) { spaceHiking(id: $id) { stops { id order } } }", {"id": payload["id"]})["spaceHiking"]["stops"]
        self.assertEqual([stop["id"] for stop in stops], [str(second.pk), str(first.pk)])

        duplicate = self.mutate("saveHiking", signature, arguments, {"input": {**base, "stops": [str(first.pk), str(first.pk)]}, "id": str(hiking.pk)})
        self.assertEqual(self.field_errors(duplicate), {"stops": "duplicateStop", "images": "required"})

    def test_transport_times_and_sub_regions(self):
        signature = "$input: SpaceTransportInput!, $id: ID"
        arguments = "input: $input, id: $id"
        base = {"type": str(self.transport_type.pk), "city": str(self.city.pk), "busNumber": "52", "fromRegion": str(self.medina.pk), "toRegion": str(self.kantaoui.pk)}
        payload = self.mutate("saveTransport", signature, arguments, {"input": {**base, "times": ["18:30", "07:15", "07:15", ""]}})
        self.assertTrue(payload["ok"], payload)
        detail = self.graphql("query($id: ID!) { spaceTransport(id: $id) { times fromRegion toRegion busNumber } }", {"id": payload["id"]})["spaceTransport"]
        self.assertEqual(detail, {"times": ["07:15", "18:30"], "fromRegion": str(self.medina.pk), "toRegion": str(self.kantaoui.pk), "busNumber": "52"})

        wrong = self.mutate("saveTransport", signature, arguments, {"input": {**base, "toRegion": str(self.bab_bhar.pk), "times": []}, "id": payload["id"]})
        self.assertEqual(self.field_errors(wrong), {"toRegion": "invalidChoice", "times": "required"})
        regions = self.graphql("{ spaceSubRegions { id region } }")["spaceSubRegions"]
        self.assertEqual({region["id"] for region in regions}, {str(self.medina.pk), str(self.kantaoui.pk)})

    def test_tip_create_update_delete(self):
        signature = "$input: SpaceTipInput!, $id: ID"
        payload = self.mutate("saveTip", signature, "input: $input, id: $id", {"input": {"city": str(self.city.pk), "descriptionEn": "<p>Bargain</p>", "descriptionFr": "<p>Négociez</p>"}})
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(Tip.objects.get(pk=payload["id"]).description_fr, "<p>Négociez</p>")
        self.assertTrue(self.mutate("deleteTip", "$id: ID!", "id: $id", {"id": payload["id"]})["ok"])
        self.assertFalse(Tip.objects.exists())

    def test_pages_need_unique_slugs(self):
        signature = "$input: SpacePageInput!, $id: ID"
        base = {"slugEn": "privacy-policy", "slugFr": "politique-de-confidentialite", "titleEn": "Privacy", "titleFr": "Confidentialité", "contentEn": "<p>EN</p>", "contentFr": "<p>FR</p>", "isActive": False}
        payload = self.mutate("savePage", signature, "input: $input, id: $id", {"input": base})
        self.assertTrue(payload["ok"], payload)
        page = Page.objects.get(pk=payload["id"])
        self.assertEqual((page.slug_en, page.slug_fr), ("privacy-policy", "politique-de-confidentialite"))
        self.assertTrue(Page.objects.filter(pk=page.pk).exclude(title="").exists())
        self.assertEqual(self.graphql("{ spacePages { id isActive } }")["spacePages"], [{"id": payload["id"], "isActive": False}])

        taken = self.mutate("savePage", signature, "input: $input, id: $id", {"input": {**base, "slugFr": "privacy-policy", "slugEn": "other"}})
        self.assertEqual(self.field_errors(taken), {"slug": "slugTaken"})
        bad = self.mutate("savePage", signature, "input: $input, id: $id", {"input": {**base, "slugEn": "with space"}, "id": payload["id"]})
        self.assertEqual(self.field_errors(bad), {"slug": "slug"})

    def test_offline_region_id_is_fixed_once_created(self):
        signature = "$input: SpaceOfflineCityInput!, $id: ID"
        base = {"nameEn": "Sousse medina", "nameFr": "Médina de Sousse", "regionId": "sousse_medina", "city": str(self.city.pk), "latitude": "35.8256", "longitude": "10.6411", "radius": "2000", "isActive": False}
        payload = self.mutate("saveOfflineCity", signature, "input: $input, id: $id", {"input": base})
        self.assertTrue(payload["ok"], payload)
        again = self.mutate("saveOfflineCity", signature, "input: $input, id: $id", {"input": base})
        self.assertEqual(self.field_errors(again), {"regionId": "slugTaken"})
        renamed = self.mutate("saveOfflineCity", signature, "input: $input, id: $id", {"input": {**base, "regionId": "other", "radius": "2500"}, "id": payload["id"]})
        self.assertTrue(renamed["ok"], renamed)
        region = OfflineCity.objects.get(pk=payload["id"])
        self.assertEqual((region.region_id, region.radius, region.is_active), ("sousse_medina", 2500.0, False))
        invalid = self.mutate("saveOfflineCity", signature, "input: $input, id: $id", {"input": {**base, "regionId": "new region", "radius": "-1"}})
        self.assertEqual(self.field_errors(invalid), {"regionId": "slug", "radius": "number"})

    def test_categories_cannot_be_deleted_while_used(self):
        signature = "$kind: String!, $input: SpaceCategoryInput!, $id: ID"
        arguments = "kind: $kind, input: $input, id: $id"
        payload = self.mutate("saveCategory", signature, arguments, {"kind": "merchant", "input": {"nameEn": "Café", "nameFr": "Café", "icon": "cup"}})
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(payload["id"].startswith("merchant-"))
        self.assertEqual(MerchantCategory.objects.get(name_en="Café").icon, "cup")

        category = EventCategory.objects.create(name_en="Music", name_fr="Musique")
        Event.objects.create(name_en="Concert", name_fr="Concert", description_en="d", description_fr="d", category=category, startDate=datetime.date(2030, 1, 1), endDate=datetime.date(2030, 1, 1), time=datetime.time(20, 0), price=0, link="https://x.example")
        used = self.mutate("deleteCategory", "$kind: String!, $id: ID!", "kind: $kind, id: $id", {"kind": "event", "id": str(category.pk)})
        self.assertEqual(used["error"], "inUse")
        self.assertTrue(Event.objects.exists())
        unused = self.mutate("deleteCategory", "$kind: String!, $id: ID!", "kind: $kind, id: $id", {"kind": "transport", "id": str(self.transport_type.pk)})
        self.assertTrue(unused["ok"])
        self.assertFalse(PublicTransportType.objects.exists())
        wrong_kind = self.mutate("saveCategory", signature, arguments, {"kind": "planet", "input": {"nameEn": "X", "nameFr": "X"}})
        self.assertEqual(self.field_errors(wrong_kind), {"kind": "invalidChoice"})
