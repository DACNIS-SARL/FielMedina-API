import datetime
import logging
import re
from typing import Annotated, Dict, List, Optional
from urllib.parse import urlencode

import strawberry
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, user_logged_in
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from shared.models import UserProfile, ensure_profile_exists

from .authentication import (
    clear_attempts,
    is_throttled,
    issue_token,
    record_attempt,
    resolve_token,
)
from .models import AuthToken

logger = logging.getLogger(__name__)
User = get_user_model()

WEB_LOCALES = ("en", "fr", "ar", "es")
SUBSCRIPTION_STATUSES = ("trial", "active", "grace", "expired")
TRIAL_LENGTH = datetime.timedelta(days=90)
PHONE_PATTERN = re.compile(r"^\+?[\d\s().-]{8,20}$")
PASSWORD_ERRORS = {
    "password_too_short": "passwordWeak",
    "password_entirely_numeric": "passwordWeak",
    "password_too_common": "passwordCommon",
    "password_too_similar": "passwordSimilar",
}
SIGN_IN_LIMIT = 5
SIGN_IN_WINDOW = 15 * 60
PASSWORD_CHECK_LIMIT = 5
RESET_LIMIT = 3
RESET_WINDOW = 60 * 60


@strawberry.type
class AccountSubscriptionType:
    plan: str
    status: str
    started_at: datetime.date
    renews_at: datetime.date
    days_left: int


@strawberry.type
class AccountType:
    id: strawberry.ID
    username: str
    email: str
    full_name: str
    role: str
    company: str
    phone: str
    city: str
    activity: str
    subscription: AccountSubscriptionType


@strawberry.type
class AccountSessionType:
    token: str
    expires_at: datetime.datetime
    persistent: bool


@strawberry.type
class AccountFieldErrorType:
    field: str
    code: str


@strawberry.type
class AccountPayload:
    ok: bool
    error: Optional[str] = None
    field_errors: List[AccountFieldErrorType] = strawberry.field(default_factory=list)
    account: Optional[AccountType] = None
    session: Optional[AccountSessionType] = None


@strawberry.input
class SignUpInput:
    full_name: str
    email: str
    password: str
    company: str
    activity: str
    city: str = ""
    phone: str = ""


@strawberry.input
class AccountUpdateInput:
    full_name: str
    email: str
    company: str = ""
    city: str = ""
    phone: str = ""


def failure(error: Optional[str] = None, **fields: str) -> AccountPayload:
    return AccountPayload(
        ok=False,
        error=error,
        field_errors=[AccountFieldErrorType(field=name, code=code) for name, code in fields.items()],
    )


def single_line(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit]


def split_name(full_name: str):
    first, _separator, last = full_name.partition(" ")
    return first[:150], last[:150]


def profile_for(user) -> UserProfile:
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        ensure_profile_exists(sender=User, instance=user, created=False)
        return UserProfile.objects.get(user=user)


def serialize_account(user) -> AccountType:
    profile = profile_for(user)
    today = timezone.localdate()
    started = profile.subscription_started_at or timezone.localdate(user.date_joined)
    renews = profile.subscription_renews_at or started + TRIAL_LENGTH
    status = (profile.subscription_status or "").lower()
    if status not in SUBSCRIPTION_STATUSES:
        status = "trial"
    if renews < today:
        status = "expired"

    return AccountType(
        id=strawberry.ID(str(user.pk)),
        username=user.get_username(),
        email=user.email or "",
        full_name=user.get_full_name() or user.get_username(),
        role="staff" if user.is_staff or user.is_superuser else "partner",
        company=profile.company_name,
        phone=profile.phone,
        city=profile.city,
        activity=profile.activity,
        subscription=AccountSubscriptionType(
            plan=profile.subscription_plan or "Trial",
            status=status,
            started_at=started,
            renews_at=renews,
            days_left=max((renews - today).days, 0),
        ),
    )


def signed_in(user, persistent: bool) -> AccountPayload:
    raw, token = issue_token(user, persistent)
    return AccountPayload(
        ok=True,
        account=serialize_account(user),
        session=AccountSessionType(token=raw, expires_at=token.expires_at, persistent=persistent),
    )


def password_error(password: str, user) -> Optional[str]:
    try:
        validate_password(password, user)
    except ValidationError as error:
        codes = {item.code for item in error.error_list}
        return next((PASSWORD_ERRORS[code] for code in PASSWORD_ERRORS if code in codes), "passwordWeak")
    return None


def identity_errors(full_name: str, email: str, phone: str, user=None) -> Dict[str, str]:
    errors = {}
    if not full_name:
        errors["fullName"] = "required"
    elif len(full_name) < 2:
        errors["fullName"] = "tooShort"

    if not email:
        errors["email"] = "required"
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = "email"
        else:
            others = User.objects.filter(email__iexact=email)
            if user is not None:
                others = others.exclude(pk=user.pk)
            if others.exists():
                errors["email"] = "emailTaken"

    if phone and not PHONE_PATTERN.match(phone):
        errors["phone"] = "phone"
    return errors


def unique_username(email: str) -> str:
    base = re.sub(r"[^\w.@+-]", "", email)[:150] or "partner"
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        suffix += 1
        tail = f"-{suffix}"
        candidate = f"{base[: 150 - len(tail)]}{tail}"
    return candidate


def send_password_reset(user, locale: str) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"token": f"{uid}.{token}"})
    context = {
        "locale": locale,
        "name": user.get_short_name() or user.get_username(),
        "link": f"{settings.WEB_APP_URL.rstrip('/')}/{locale}/reset-password?{query}",
        "days": max(settings.PASSWORD_RESET_TIMEOUT // 86400, 1),
    }
    subject = " ".join(render_to_string("api/emails/password_reset_subject.txt", context).split())
    body = render_to_string("api/emails/password_reset.txt", context)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:
        logger.exception("Could not send the password reset email for user %s", user.pk)


def user_from_reset_token(value: str):
    uidb64, _separator, token = value.strip().partition(".")
    if not uidb64 or not token:
        return None
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)), is_active=True)
    except (TypeError, ValueError, OverflowError, ValidationError, User.DoesNotExist):
        return None
    return user if default_token_generator.check_token(user, token) else None


@strawberry.type
class AccountQuery:
    @strawberry.field
    def me(self, info: strawberry.Info) -> Optional[AccountType]:
        token = resolve_token(info.context.request)
        return serialize_account(token.user) if token else None


@strawberry.type
class AccountMutation:
    @strawberry.mutation
    def sign_in(
        self,
        info: strawberry.Info,
        identifier: str,
        password: str,
        remember: bool = False,
    ) -> AccountPayload:
        request = info.context.request
        identifier = identifier.strip()
        if not identifier or not password:
            return failure("invalidCredentials")
        if is_throttled("sign-in", identifier, SIGN_IN_LIMIT):
            return failure("tooManyAttempts")

        candidates = []
        if "@" in identifier:
            candidates = list(
                User.objects.filter(email__iexact=identifier).values_list("username", flat=True)[:5]
            )
        if identifier not in candidates:
            candidates.append(identifier)

        user = None
        for username in candidates:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                break

        if user is None:
            record_attempt("sign-in", identifier, SIGN_IN_WINDOW)
            return failure("invalidCredentials")

        clear_attempts("sign-in", identifier)
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        return signed_in(user, remember)

    @strawberry.mutation
    def sign_up(
        self,
        data: Annotated[SignUpInput, strawberry.argument(name="input")],
    ) -> AccountPayload:
        full_name = single_line(data.full_name, 300)
        email = data.email.strip().lower()
        company = single_line(data.company, 160)
        activity = data.activity.strip()
        city = single_line(data.city, 120)
        phone = data.phone.strip()[:32]

        errors = identity_errors(full_name, email, phone)
        if not company:
            errors["company"] = "required"
        if activity not in UserProfile.Activity.values:
            errors["activity"] = "invalidChoice"

        first_name, last_name = split_name(full_name)
        candidate = User(username=email[:150], email=email, first_name=first_name, last_name=last_name)
        code = password_error(data.password, candidate)
        if code:
            errors["password"] = code
        if errors:
            return failure(**errors)

        with transaction.atomic():
            user = User.objects.create_user(
                username=unique_username(email),
                email=email,
                password=data.password,
                first_name=first_name,
                last_name=last_name,
            )
            profile = profile_for(user)
            profile.user_type = UserProfile.UserType.CLIENT_PARTNER
            profile.company_name = company
            profile.activity = activity
            profile.city = city
            profile.phone = phone
            profile.save()

        return signed_in(user, True)

    @strawberry.mutation
    def sign_out(self, info: strawberry.Info) -> AccountPayload:
        token = resolve_token(info.context.request)
        if token is not None:
            token.delete()
        return AccountPayload(ok=True)

    @strawberry.mutation
    def request_password_reset(self, email: str, locale: str = "en") -> AccountPayload:
        email = email.strip()
        locale = locale if locale in WEB_LOCALES else "en"
        try:
            validate_email(email)
        except ValidationError:
            return failure(email="email")

        if is_throttled("password-reset", email, RESET_LIMIT):
            return AccountPayload(ok=True)
        record_attempt("password-reset", email, RESET_WINDOW)

        for user in User.objects.filter(email__iexact=email, is_active=True):
            if user.has_usable_password():
                send_password_reset(user, locale)
        return AccountPayload(ok=True)

    @strawberry.mutation
    def reset_password(self, token: str, password: str) -> AccountPayload:
        user = user_from_reset_token(token)
        if user is None:
            return failure("resetLinkInvalid")

        code = password_error(password, user)
        if code:
            return failure(password=code)

        user.set_password(password)
        user.save(update_fields=["password"])
        AuthToken.objects.filter(user=user).delete()
        return AccountPayload(ok=True)

    @strawberry.mutation
    def change_password(
        self,
        info: strawberry.Info,
        current_password: str,
        new_password: str,
    ) -> AccountPayload:
        token = resolve_token(info.context.request)
        if token is None:
            return failure("unauthenticated")

        user = token.user
        scope_key = str(user.pk)
        if is_throttled("password-check", scope_key, PASSWORD_CHECK_LIMIT):
            return failure("tooManyAttempts")
        if not user.check_password(current_password):
            record_attempt("password-check", scope_key, SIGN_IN_WINDOW)
            return failure(currentPassword="currentPasswordWrong")
        clear_attempts("password-check", scope_key)

        code = password_error(new_password, user)
        if code:
            return failure(newPassword=code)

        persistent = token.persistent
        user.set_password(new_password)
        user.save(update_fields=["password"])
        AuthToken.objects.filter(user=user).delete()
        return signed_in(user, persistent)

    @strawberry.mutation
    def update_account(
        self,
        info: strawberry.Info,
        data: Annotated[AccountUpdateInput, strawberry.argument(name="input")],
    ) -> AccountPayload:
        token = resolve_token(info.context.request)
        if token is None:
            return failure("unauthenticated")

        user = token.user
        full_name = single_line(data.full_name, 300)
        email = data.email.strip().lower()
        phone = data.phone.strip()[:32]

        errors = identity_errors(full_name, email, phone, user=user)
        if errors:
            return failure(**errors)

        user.first_name, user.last_name = split_name(full_name)
        user.email = email
        user.save(update_fields=["first_name", "last_name", "email"])

        profile = profile_for(user)
        profile.company_name = single_line(data.company, 160)
        profile.city = single_line(data.city, 120)
        profile.phone = phone
        profile.save(update_fields=["company_name", "city", "phone", "updated_at"])

        return AccountPayload(ok=True, account=serialize_account(user))
