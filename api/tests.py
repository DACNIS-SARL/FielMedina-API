import datetime
import json
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from shared.models import UserProfile

from .models import AuthToken

User = get_user_model()

ACCOUNT_FIELDS = """
  ok
  error
  fieldErrors { field code }
  session { token expiresAt persistent }
  account {
    id username email fullName role company phone city activity
    subscription { plan status startedAt renewsAt daysLeft }
  }
"""

SIGN_IN = (
    "mutation($identifier: String!, $password: String!, $remember: Boolean!) {"
    " signIn(identifier: $identifier, password: $password, remember: $remember) {"
    f"{ACCOUNT_FIELDS}"
    "} }"
)
SIGN_UP = f"mutation($input: SignUpInput!) {{ signUp(input: $input) {{ {ACCOUNT_FIELDS} }} }}"
SIGN_OUT = "mutation { signOut { ok } }"
ME = "{ me { id email role fullName subscription { status } } }"
CHANGE_PASSWORD = (
    "mutation($current: String!, $new: String!) {"
    " changePassword(currentPassword: $current, newPassword: $new) {"
    f"{ACCOUNT_FIELDS}"
    "} }"
)
REQUEST_RESET = (
    "mutation($email: String!, $locale: String!) {"
    " requestPasswordReset(email: $email, locale: $locale) { ok error fieldErrors { field code } } }"
)
RESET = (
    "mutation($token: String!, $password: String!) {"
    " resetPassword(token: $token, password: $password) { ok error fieldErrors { field code } } }"
)
UPDATE = f"mutation($input: AccountUpdateInput!) {{ updateAccount(input: $input) {{ {ACCOUNT_FIELDS} }} }}"

PASSWORD = "Sidi-Bou-2026"


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    WEB_APP_URL="https://web.example",
)
class AccountApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.partner = User.objects.create_user(
            "atelier",
            "Atelier@Example.com",
            PASSWORD,
            first_name="Amina",
            last_name="Ben Salah",
        )

    def graphql(self, query, variables=None, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        response = self.client.post(
            "/graphql",
            data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("errors", body, body.get("errors"))
        return body["data"]

    def sign_in(self, identifier, password=PASSWORD, remember=False):
        variables = {"identifier": identifier, "password": password, "remember": remember}
        return self.graphql(SIGN_IN, variables)["signIn"]

    def field_errors(self, payload):
        return {item["field"]: item["code"] for item in payload["fieldErrors"]}

    def test_sign_in_with_email_or_username(self):
        by_email = self.sign_in("atelier@example.com", remember=True)
        self.assertTrue(by_email["ok"], by_email)
        self.assertTrue(by_email["session"]["persistent"])
        self.assertEqual(by_email["account"]["role"], "partner")
        self.assertEqual(by_email["account"]["fullName"], "Amina Ben Salah")

        by_username = self.sign_in("atelier")
        self.assertTrue(by_username["ok"], by_username)
        self.assertFalse(by_username["session"]["persistent"])

        digests = list(AuthToken.objects.filter(user=self.partner).values_list("digest", flat=True))
        self.assertEqual(len(digests), 2)
        self.assertNotIn(by_email["session"]["token"], digests)

    def test_wrong_password_is_rejected_then_throttled(self):
        for _ in range(5):
            payload = self.sign_in("atelier@example.com", "wrong-password")
            self.assertEqual(payload["error"], "invalidCredentials")
            self.assertIsNone(payload["session"])
        self.assertEqual(self.sign_in("atelier@example.com")["error"], "tooManyAttempts")

    def test_inactive_user_cannot_sign_in(self):
        self.partner.is_active = False
        self.partner.save()
        self.assertEqual(self.sign_in("atelier")["error"], "invalidCredentials")

    def test_me_requires_a_valid_token(self):
        self.assertIsNone(self.graphql(ME)["me"])
        self.assertIsNone(self.graphql(ME, token="not-a-token")["me"])

        token = self.sign_in("atelier")["session"]["token"]
        self.assertEqual(self.graphql(ME, token=token)["me"]["email"], "Atelier@example.com")

        AuthToken.objects.update(expires_at=timezone.now() - datetime.timedelta(minutes=1))
        self.assertIsNone(self.graphql(ME, token=token)["me"])

    def test_staff_role(self):
        User.objects.create_user("team", "team@fielmedina.com", PASSWORD, is_staff=True)
        self.assertEqual(self.sign_in("team")["account"]["role"], "staff")

    def test_subscription_expires_with_renewal_date(self):
        UserProfile.objects.filter(user=self.partner).update(
            subscription_status="active",
            subscription_renews_at=timezone.localdate() - datetime.timedelta(days=1),
        )
        token = self.sign_in("atelier")["session"]["token"]
        self.assertEqual(self.graphql(ME, token=token)["me"]["subscription"]["status"], "expired")

    def test_sign_up_creates_a_partner_session(self):
        payload = self.graphql(
            SIGN_UP,
            {
                "input": {
                    "fullName": "  Youssef   Trabelsi ",
                    "email": "Dar.Yasmine@Example.com",
                    "password": PASSWORD,
                    "company": "Dar Yasmine",
                    "activity": "guesthouse",
                    "city": "Sousse",
                    "phone": "+216 73 000 000",
                }
            },
        )["signUp"]
        self.assertTrue(payload["ok"], payload)
        account = payload["account"]
        self.assertEqual(account["email"], "dar.yasmine@example.com")
        self.assertEqual(account["fullName"], "Youssef Trabelsi")
        self.assertEqual(account["role"], "partner")
        self.assertEqual(account["company"], "Dar Yasmine")
        self.assertEqual(account["subscription"]["status"], "trial")
        self.assertTrue(payload["session"]["persistent"])

        profile = UserProfile.objects.get(user__email="dar.yasmine@example.com")
        self.assertEqual(profile.user_type, UserProfile.UserType.CLIENT_PARTNER)
        self.assertEqual(profile.activity, "guesthouse")
        self.assertEqual(profile.city, "Sousse")

        me = self.graphql(ME, token=payload["session"]["token"])["me"]
        self.assertEqual(me["fullName"], "Youssef Trabelsi")

    def test_sign_up_validation(self):
        payload = self.graphql(
            SIGN_UP,
            {
                "input": {
                    "fullName": "A",
                    "email": "atelier@example.com",
                    "password": "password123",
                    "company": "",
                    "activity": "casino",
                    "phone": "call me",
                }
            },
        )["signUp"]
        self.assertFalse(payload["ok"])
        self.assertEqual(
            self.field_errors(payload),
            {
                "fullName": "tooShort",
                "email": "emailTaken",
                "password": "passwordCommon",
                "company": "required",
                "activity": "invalidChoice",
                "phone": "phone",
            },
        )
        self.assertEqual(User.objects.count(), 1)

    def test_sign_out_revokes_the_token(self):
        token = self.sign_in("atelier")["session"]["token"]
        self.assertTrue(self.graphql(SIGN_OUT, token=token)["signOut"]["ok"])
        self.assertIsNone(self.graphql(ME, token=token)["me"])

    def test_change_password_rotates_sessions(self):
        first = self.sign_in("atelier", remember=True)["session"]["token"]
        other = self.sign_in("atelier")["session"]["token"]

        wrong = self.graphql(CHANGE_PASSWORD, {"current": "nope", "new": "Kairouan-2027"}, token=first)
        self.assertEqual(self.field_errors(wrong["changePassword"]), {"currentPassword": "currentPasswordWrong"})

        changed = self.graphql(CHANGE_PASSWORD, {"current": PASSWORD, "new": "Kairouan-2027"}, token=first)
        changed = changed["changePassword"]
        self.assertTrue(changed["ok"], changed)
        self.assertTrue(changed["session"]["persistent"])
        self.assertIsNone(self.graphql(ME, token=first)["me"])
        self.assertIsNone(self.graphql(ME, token=other)["me"])
        self.assertIsNotNone(self.graphql(ME, token=changed["session"]["token"])["me"])
        self.assertTrue(self.sign_in("atelier", "Kairouan-2027")["ok"])

    def test_change_password_requires_a_session(self):
        payload = self.graphql(CHANGE_PASSWORD, {"current": PASSWORD, "new": "Kairouan-2027"})
        self.assertEqual(payload["changePassword"]["error"], "unauthenticated")

    def test_password_reset_flow(self):
        session = self.sign_in("atelier")["session"]["token"]
        requested = self.graphql(REQUEST_RESET, {"email": "atelier@example.com", "locale": "fr"})
        self.assertTrue(requested["requestPasswordReset"]["ok"])
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["Atelier@example.com"])
        self.assertIn("Bonjour Amina", message.body)
        match = re.search(r"https://web\.example/fr/reset-password\?token=([\w.-]+)", message.body)
        self.assertIsNotNone(match, message.body)
        token = match.group(1)

        weak = self.graphql(RESET, {"token": token, "password": "12345678"})["resetPassword"]
        self.assertEqual(self.field_errors(weak), {"password": "passwordWeak"})

        done = self.graphql(RESET, {"token": token, "password": "Kairouan-2027"})["resetPassword"]
        self.assertTrue(done["ok"], done)
        self.assertIsNone(self.graphql(ME, token=session)["me"])

        reused = self.graphql(RESET, {"token": token, "password": "Mahdia-2028!"})["resetPassword"]
        self.assertEqual(reused["error"], "resetLinkInvalid")
        self.assertTrue(self.sign_in("atelier", "Kairouan-2027")["ok"])

    def test_password_reset_does_not_reveal_accounts(self):
        payload = self.graphql(REQUEST_RESET, {"email": "nobody@example.com", "locale": "en"})
        self.assertTrue(payload["requestPasswordReset"]["ok"])
        self.assertEqual(len(mail.outbox), 0)

        invalid = self.graphql(RESET, {"token": "bad.token", "password": "Kairouan-2027"})
        self.assertEqual(invalid["resetPassword"]["error"], "resetLinkInvalid")

    def test_update_account(self):
        User.objects.create_user("other", "taken@example.com", PASSWORD)
        token = self.sign_in("atelier")["session"]["token"]

        taken = self.graphql(
            UPDATE,
            {"input": {"fullName": "Amina Ben Salah", "email": "TAKEN@example.com"}},
            token=token,
        )["updateAccount"]
        self.assertEqual(self.field_errors(taken), {"email": "emailTaken"})

        saved = self.graphql(
            UPDATE,
            {
                "input": {
                    "fullName": "Amina B. Salah",
                    "email": "Amina@Example.com",
                    "company": "Atelier Amina",
                    "city": "Mahdia",
                    "phone": "+216 70 000 000",
                }
            },
            token=token,
        )["updateAccount"]
        self.assertTrue(saved["ok"], saved)
        self.assertEqual(saved["account"]["company"], "Atelier Amina")
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.email, "amina@example.com")
        self.assertEqual(self.partner.last_name, "B. Salah")
        self.assertEqual(self.partner.profile.city, "Mahdia")

    def test_update_account_requires_a_session(self):
        payload = self.graphql(UPDATE, {"input": {"fullName": "Amina", "email": "amina@example.com"}})
        self.assertEqual(payload["updateAccount"]["error"], "unauthenticated")
