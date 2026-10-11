import datetime
import io
import json
import os
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from cities_light.models import City, Country
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from api.authentication import issue_token
from guard.models import Ad, Event, EventCategory, ImageEvent
from shared.models import UserProfile
from subscribers.models import PaymentTransaction

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp(prefix="fielmedina-space-tests-")

PAYLOAD = "ok error fieldErrors { field code } id transaction { id reference type status months amountHt taxAmount timbreFiscal totalTtc subject partnerName }"
SAVE_EVENT = (
    "mutation($input: SpaceEventInput!, $id: ID, $images: [Upload!]) {"
    f" saveEvent(input: $input, id: $id, images: $images) {{ {PAYLOAD} }} }}"
)
DELETE_EVENT = f"mutation($id: ID!) {{ deleteEvent(id: $id) {{ {PAYLOAD} }} }}"
SAVE_AD = (
    "mutation($input: SpaceAdInput!, $id: ID, $imageMobile: Upload, $imageTablet: Upload) {"
    f" saveAd(input: $input, id: $id, imageMobile: $imageMobile, imageTablet: $imageTablet) {{ {PAYLOAD} }} }}"
)
REQUEST_SUBSCRIPTION = f"mutation($months: Int!) {{ requestSubscription(months: $months) {{ {PAYLOAD} }} }}"
REQUEST_BOOST = f"mutation($eventId: ID!) {{ requestEventBoost(eventId: $eventId) {{ {PAYLOAD} }} }}"
REVIEW = f"mutation($id: ID!, $decision: String!) {{ reviewTransaction(id: $id, decision: $decision) {{ {PAYLOAD} }} }}"
EVENTS = "{ spaceEvents { id nameEn nameFr boost boostPending owner shortLink images { id url } city { id } category { id } } }"
ADS = "{ spaceAds { id name isActive startDate endDate imageMobile imageTablet owner paymentStatus } }"
TRANSACTIONS = "{ spaceTransactions { id reference type status totalTtc partnerName subject } }"


def png(name="photo.png", size=(64, 48)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (182, 98, 57)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(
    MEDIA_ROOT=MEDIA_ROOT,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    ADMIN_LIST_EMAILS=["admin@fielmedina.test"],
)
class SpaceApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        short_io = mock.patch("api.space.ShortIOService")
        self.short_io = short_io.start().return_value
        self.short_io.shorten_url.return_value = {"secureShortURL": "https://go.test/abc", "idString": "lnk_1"}
        self.short_io.update_link.return_value = {"secureShortURL": "https://go.test/abc"}
        self.addCleanup(short_io.stop)
        push = mock.patch("guard.notifications.NotificationService.send_new_event_notification")
        push.start()
        self.addCleanup(push.stop)

        self.country = Country.objects.create(name="Tunisia", name_ascii="Tunisia", code2="TN", code3="TUN", continent="AF", tld="tn", phone="216")
        self.city = City.objects.create(name="Sousse", name_ascii="Sousse", display_name="Sousse", country=self.country)
        self.category = EventCategory.objects.create(name_en="Music", name_fr="Musique")

        self.partner = User.objects.create_user("atelier", "atelier@example.com", "Sidi-Bou-2026", first_name="Amina")
        self.other = User.objects.create_user("voisin", "voisin@example.com", "Sidi-Bou-2026")
        self.staff = User.objects.create_user("equipe", "equipe@example.com", "Sidi-Bou-2026", is_staff=True)
        for user, company in ((self.partner, "Atelier Amina"), (self.other, "Dar Voisin")):
            profile = UserProfile.objects.get(user=user)
            profile.company_name = company
            profile.save()
        self.partner_token = issue_token(self.partner, False)[0]
        self.other_token = issue_token(self.other, False)[0]
        self.staff_token = issue_token(self.staff, False)[0]

    def graphql(self, query, variables=None, token=None, files=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        if files:
            operations = {"query": query, "variables": variables or {}}
            mapping = {}
            data = {}
            for index, (path, upload) in enumerate(files.items()):
                mapping[str(index)] = [f"variables.{path}"]
                data[str(index)] = upload
            data["operations"] = json.dumps(operations)
            data["map"] = json.dumps(mapping)
            response = self.client.post("/graphql", data=data, **headers)
        else:
            response = self.client.post(
                "/graphql",
                data=json.dumps({"query": query, "variables": variables or {}}),
                content_type="application/json",
                **headers,
            )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def data(self, *args, **kwargs):
        body = self.graphql(*args, **kwargs)
        self.assertNotIn("errors", body, body.get("errors"))
        return body["data"]

    def event_input(self, **overrides):
        start = timezone.localdate() + datetime.timedelta(days=10)
        values = {
            "nameEn": "Malouf night",
            "nameFr": "Soirée malouf",
            "descriptionEn": "<p>Live malouf in the patio.</p>",
            "descriptionFr": "<p>Malouf en direct dans le patio.</p>",
            "category": str(self.category.pk),
            "city": str(self.city.pk),
            "startDate": start.isoformat(),
            "endDate": start.isoformat(),
            "time": "20:30",
            "price": "25",
            "link": "https://tickets.example/malouf",
        }
        values.update(overrides)
        return values

    def create_event(self, token=None, **overrides):
        payload = self.data(
            SAVE_EVENT,
            {"input": self.event_input(**overrides), "images": [None]},
            token=token or self.partner_token,
            files={"images.0": png()},
        )["saveEvent"]
        self.assertTrue(payload["ok"], payload)
        return Event.objects.get(pk=payload["id"])

    def field_errors(self, payload):
        return {item["field"]: item["code"] for item in payload["fieldErrors"]}

    def test_space_queries_require_a_session(self):
        body = self.graphql(EVENTS)
        self.assertIn("errors", body)
        self.assertIn("unauthenticated", body["errors"][0]["message"])

    def test_partner_creates_event_with_image_and_short_link(self):
        event = self.create_event()
        self.assertEqual(event.client.user, self.partner)
        self.assertEqual(event.created_by, self.partner)
        self.assertEqual(event.name_en, "Malouf night")
        self.assertEqual(event.name_fr, "Soirée malouf")
        self.assertTrue(Event.objects.filter(pk=event.pk).exclude(name="").exists())
        self.assertEqual(event.short_link, "https://go.test/abc")
        self.assertEqual(event.short_id, "lnk_1")
        self.assertFalse(event.boost)
        self.assertEqual(event.images.count(), 1)
        self.assertTrue(event.images.first().image.name.endswith(".jpg"))

    def test_event_validation_matches_the_old_dashboard(self):
        payload = self.data(
            SAVE_EVENT,
            {
                "input": self.event_input(
                    nameFr=" ",
                    descriptionFr="<p>&nbsp;</p>",
                    endDate="2020-01-01",
                    price="-3",
                    link="not a link",
                    category="",
                ),
            },
            token=self.partner_token,
        )["saveEvent"]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "fixErrors")
        self.assertEqual(
            self.field_errors(payload),
            {
                "name": "required",
                "description": "required",
                "category": "required",
                "endDate": "dateOrder",
                "price": "number",
                "link": "url",
                "images": "required",
            },
        )
        self.assertFalse(Event.objects.exists())

    def test_fake_image_upload_is_rejected(self):
        fake = SimpleUploadedFile("photo.png", b"<html>not an image</html>", content_type="image/png")
        payload = self.data(
            SAVE_EVENT,
            {"input": self.event_input(), "images": [None]},
            token=self.partner_token,
            files={"images.0": fake},
        )["saveEvent"]
        self.assertEqual(self.field_errors(payload), {"images": "imageInvalid"})
        self.assertFalse(Event.objects.exists())

    def test_partners_only_see_and_edit_their_own_events(self):
        mine = self.create_event()
        theirs = self.create_event(token=self.other_token, nameEn="Pottery", nameFr="Poterie")

        listed = self.data(EVENTS, token=self.partner_token)["spaceEvents"]
        self.assertEqual([item["id"] for item in listed], [str(mine.pk)])
        self.assertEqual(listed[0]["owner"], "Atelier Amina")
        everything = self.data(EVENTS, token=self.staff_token)["spaceEvents"]
        self.assertEqual({item["id"] for item in everything}, {str(mine.pk), str(theirs.pk)})

        payload = self.data(
            SAVE_EVENT, {"id": str(theirs.pk), "input": self.event_input()}, token=self.partner_token
        )["saveEvent"]
        self.assertEqual(payload["error"], "notFound")
        payload = self.data(DELETE_EVENT, {"id": str(theirs.pk)}, token=self.partner_token)["deleteEvent"]
        self.assertEqual(payload["error"], "notFound")
        self.assertTrue(Event.objects.filter(pk=theirs.pk).exists())

    def test_update_keeps_and_removes_images_and_ignores_partner_boost(self):
        event = self.create_event()
        first = event.images.get()
        url = self.data(EVENTS, token=self.partner_token)["spaceEvents"][0]["images"][0]["url"]

        payload = self.data(
            SAVE_EVENT,
            {"id": str(event.pk), "input": self.event_input(keepImages=[url], boost=True), "images": [None]},
            token=self.partner_token,
            files={"images.0": png("second.png")},
        )["saveEvent"]
        self.assertTrue(payload["ok"], payload)
        event.refresh_from_db()
        self.assertEqual(event.images.count(), 2)
        self.assertTrue(event.images.filter(pk=first.pk).exists())
        self.assertFalse(event.boost)
        self.short_io.update_link.assert_not_called()

        payload = self.data(
            SAVE_EVENT,
            {"id": str(event.pk), "input": self.event_input(keepImages=[], link="https://tickets.example/new")},
            token=self.partner_token,
        )["saveEvent"]
        self.assertEqual(self.field_errors(payload), {"images": "required"})

        payload = self.data(
            SAVE_EVENT,
            {"id": str(event.pk), "input": self.event_input(keepImages=[url], link="https://tickets.example/new", boost=True)},
            token=self.staff_token,
        )["saveEvent"]
        self.assertTrue(payload["ok"], payload)
        event.refresh_from_db()
        self.assertEqual(list(event.images.values_list("pk", flat=True)), [first.pk])
        self.assertTrue(event.boost)
        self.assertEqual(event.client.user, self.partner)
        self.short_io.update_link.assert_called_once()

    def test_partner_ad_waits_for_payment(self):
        start = timezone.localdate() + datetime.timedelta(days=2)
        payload = self.data(
            SAVE_AD,
            {
                "input": {
                    "link": "https://dar.example/offer",
                    "startDate": start.isoformat(),
                    "endDate": (start + datetime.timedelta(days=2)).isoformat(),
                    "isActive": True,
                },
                "imageMobile": None,
                "imageTablet": None,
            },
            token=self.partner_token,
            files={"imageMobile": png("mobile.png", (320, 50)), "imageTablet": png("tablet.png", (728, 90))},
        )["saveAd"]
        self.assertTrue(payload["ok"], payload)
        ad = Ad.objects.get(pk=payload["id"])
        self.assertFalse(ad.is_active)
        self.assertEqual(ad.client.user, self.partner)
        self.assertEqual(ad.country, self.country)
        self.assertTrue(ad.name.startswith("ADS-"))
        self.assertTrue(ad.image_mobile.name.endswith(".jpg"))

        payment = payload["transaction"]
        self.assertEqual(payment["type"], "ad_boost")
        self.assertEqual(payment["status"], "pending")
        self.assertEqual(Decimal(payment["amountHt"]), Decimal("11.70"))
        self.assertEqual(Decimal(payment["taxAmount"]), Decimal("2.22"))
        self.assertEqual(Decimal(payment["totalTtc"]), Decimal("14.92"))
        self.assertEqual(payment["reference"], f"ORDER-ADS-{payment['id']}")
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(payment["reference"], mail.outbox[0].body)

        listed = self.data(ADS, token=self.partner_token)["spaceAds"]
        self.assertEqual(listed[0]["paymentStatus"], "pending")
        self.assertEqual(self.data(ADS, token=self.other_token)["spaceAds"], [])

    def test_ad_rules(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        payload = self.data(
            SAVE_AD,
            {"input": {"link": "ftp://nope", "startDate": yesterday.isoformat(), "endDate": "2099-01-01"}},
            token=self.partner_token,
        )["saveAd"]
        self.assertEqual(
            self.field_errors(payload),
            {
                "link": "url",
                "startDate": "dateInPast",
                "endDate": "dateRange",
                "imageMobile": "required",
                "imageTablet": "required",
            },
        )
        payload = self.data(
            SAVE_AD,
            {"input": {"link": "https://dar.example", "startDate": "2030-01-01", "endDate": "2032-01-01"}},
            token=self.staff_token,
        )["saveAd"]
        self.assertEqual(self.field_errors(payload)["endDate"], "dateRange")

    def test_subscription_request_and_validation(self):
        payload = self.data(REQUEST_SUBSCRIPTION, {"months": 3}, token=self.partner_token)["requestSubscription"]
        self.assertTrue(payload["ok"], payload)
        payment = payload["transaction"]
        self.assertEqual(Decimal(payment["amountHt"]), Decimal("55.00"))
        self.assertEqual(Decimal(payment["taxAmount"]), Decimal("10.45"))
        self.assertEqual(Decimal(payment["totalTtc"]), Decimal("66.45"))
        self.assertEqual(payment["reference"], f"ORDER-SUB-{payment['id']}")

        again = self.data(REQUEST_SUBSCRIPTION, {"months": 1}, token=self.partner_token)["requestSubscription"]
        self.assertEqual(again["error"], "alreadyPending")
        invalid = self.data(REQUEST_SUBSCRIPTION, {"months": 2}, token=self.other_token)["requestSubscription"]
        self.assertEqual(invalid["error"], "invalidChoice")
        staff = self.data(REQUEST_SUBSCRIPTION, {"months": 1}, token=self.staff_token)["requestSubscription"]
        self.assertEqual(staff["error"], "forbidden")

        denied = self.data(REVIEW, {"id": payment["id"], "decision": "validate"}, token=self.partner_token)
        self.assertEqual(denied["reviewTransaction"]["error"], "forbidden")

        trial_ends = UserProfile.objects.get(user=self.partner).subscription_renews_at or timezone.localdate()
        mail.outbox.clear()
        validated = self.data(REVIEW, {"id": payment["id"], "decision": "validate"}, token=self.staff_token)
        self.assertTrue(validated["reviewTransaction"]["ok"])
        profile = UserProfile.objects.get(user=self.partner)
        self.assertEqual(profile.subscription_status, "active")
        self.assertEqual(profile.subscription_plan, "3 months")
        self.assertEqual(profile.subscription_renews_at, max(trial_ends, timezone.localdate()) + datetime.timedelta(days=90))
        self.assertEqual(len(mail.outbox), 1)

        twice = self.data(REVIEW, {"id": payment["id"], "decision": "cancel"}, token=self.staff_token)
        self.assertEqual(twice["reviewTransaction"]["error"], "notPending")

        listed = self.data(TRANSACTIONS, token=self.partner_token)["spaceTransactions"]
        self.assertEqual([(item["type"], item["status"]) for item in listed], [("subscription", "validated")])
        self.assertEqual(self.data(TRANSACTIONS, token=self.other_token)["spaceTransactions"], [])

    def test_event_boost_rules_and_validation(self):
        soon = self.create_event(startDate=(timezone.localdate() + datetime.timedelta(days=2)).isoformat(), endDate=(timezone.localdate() + datetime.timedelta(days=2)).isoformat())
        late = self.data(REQUEST_BOOST, {"eventId": str(soon.pk)}, token=self.partner_token)["requestEventBoost"]
        self.assertEqual(late["error"], "boostTooLate")

        event = self.create_event()
        payload = self.data(REQUEST_BOOST, {"eventId": str(event.pk)}, token=self.partner_token)["requestEventBoost"]
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(Decimal(payload["transaction"]["totalTtc"]), Decimal("18.85"))
        self.assertEqual(payload["transaction"]["subject"], "Soirée malouf")
        listed = self.data(EVENTS, token=self.partner_token)["spaceEvents"]
        self.assertTrue(next(item for item in listed if item["id"] == str(event.pk))["boostPending"])

        again = self.data(REQUEST_BOOST, {"eventId": str(event.pk)}, token=self.partner_token)["requestEventBoost"]
        self.assertEqual(again["error"], "alreadyPending")
        other = self.data(REQUEST_BOOST, {"eventId": str(event.pk)}, token=self.other_token)["requestEventBoost"]
        self.assertEqual(other["error"], "notFound")

        self.data(REVIEW, {"id": payload["transaction"]["id"], "decision": "validate"}, token=self.staff_token)
        event.refresh_from_db()
        self.assertTrue(event.boost)

    def test_ad_validation_activates_the_ad_and_cancel_emails_the_partner(self):
        start = timezone.localdate() + datetime.timedelta(days=1)
        ad_payload = self.data(
            SAVE_AD,
            {
                "input": {"link": "https://dar.example", "startDate": start.isoformat(), "endDate": start.isoformat()},
                "imageMobile": None,
                "imageTablet": None,
            },
            token=self.partner_token,
            files={"imageMobile": png("m.png"), "imageTablet": png("t.png")},
        )["saveAd"]
        self.data(REVIEW, {"id": ad_payload["transaction"]["id"], "decision": "validate"}, token=self.staff_token)
        ad = Ad.objects.get(pk=ad_payload["id"])
        self.assertTrue(ad.is_active)
        self.assertEqual(ad.startDate, start)

        subscription = self.data(REQUEST_SUBSCRIPTION, {"months": 1}, token=self.partner_token)["requestSubscription"]
        mail.outbox.clear()
        canceled = self.data(REVIEW, {"id": subscription["transaction"]["id"], "decision": "cancel"}, token=self.staff_token)
        self.assertTrue(canceled["reviewTransaction"]["ok"])
        self.assertEqual(PaymentTransaction.objects.get(pk=subscription["transaction"]["id"]).status, "canceled")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["atelier@example.com"])

    def test_deleting_an_event_removes_its_images(self):
        event = self.create_event()
        image_path = event.images.get().image.path
        payload = self.data(DELETE_EVENT, {"id": str(event.pk)}, token=self.partner_token)["deleteEvent"]
        self.assertTrue(payload["ok"])
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
        self.assertFalse(ImageEvent.objects.exists())
        self.assertFalse(os.path.exists(image_path))
