import datetime
import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Annotated, Dict, List, Optional

import strawberry
import strawberry_django
from cities_light.models import City, Country
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Exists, OuterRef, Subquery
from django.utils import timezone
from django.utils.html import strip_tags
from PIL import Image as PilImage
from strawberry import auto
from strawberry.file_uploads import Upload

from guard.models import Ad, Event, EventCategory, ImageEvent, Location
from shared.models import UserProfile
from shared.short_io import ShortIOService
from subscribers.models import PaymentTransaction, TransactionStatus, TransactionType
from subscribers.views import (
    send_cancellation_email,
    send_transaction_emails,
    send_validation_email,
)

from .accounts import profile_for
from .authentication import resolve_token

if TYPE_CHECKING:
    from .schema import CityType, EventCategoryType, LocationType

logger = logging.getLogger(__name__)

SUBSCRIPTION_RATES = {1: Decimal("19"), 3: Decimal("55"), 6: Decimal("110"), 12: Decimal("150")}
EVENT_BOOST_HT = Decimal("15")
AD_DAY_HT = Decimal("3.9")
VAT_RATE = Decimal("0.19")
STAMP_DUTY = Decimal("1")
CENT = Decimal("0.01")
MAX_PRICE = Decimal("100000000")
BOOST_LEAD_DAYS = 3
MAX_AD_DAYS = 366
MAX_EVENT_IMAGES = 10
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_AD_COUNTRY = "TN"
LINK_MAX_LENGTH = 200
NAME_MAX_LENGTH = 255
URL_VALIDATOR = URLValidator(schemes=["http", "https"])


@dataclass
class Actor:
    user: object
    profile: UserProfile
    is_staff: bool


def current_actor(info: strawberry.Info) -> Optional[Actor]:
    token = resolve_token(info.context.request)
    if token is None:
        return None
    user = token.user
    return Actor(user=user, profile=profile_for(user), is_staff=user.is_staff or user.is_superuser)


def require_actor(info: strawberry.Info) -> Actor:
    actor = current_actor(info)
    if actor is None:
        raise PermissionError("unauthenticated")
    return actor


def media_url(field) -> Optional[str]:
    if not field:
        return None
    from .schema import absolute_media_url

    try:
        return absolute_media_url(field.url)
    except ValueError:
        return None


def owner_name(profile: Optional[UserProfile]) -> str:
    if profile is None:
        return ""
    user = profile.user
    return profile.company_name or user.get_full_name() or user.get_username()


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def invoice(amount_ht: Decimal) -> Dict[str, Decimal]:
    amount_ht = money(amount_ht)
    tax = money(amount_ht * VAT_RATE)
    return {
        "amount_ht": amount_ht,
        "tax_amount": tax,
        "timbre_fiscal": STAMP_DUTY,
        "total_ttc": amount_ht + tax + STAMP_DUTY,
    }


def boost_pending_query():
    return PaymentTransaction.objects.filter(
        event=OuterRef("pk"),
        transaction_type=TransactionType.EVENT_BOOST,
        status=TransactionStatus.PENDING,
    )


def event_queryset(actor: Actor):
    queryset = (
        Event.objects.select_related("city", "category", "location", "client__user")
        .prefetch_related("images")
        .annotate(boost_pending=Exists(boost_pending_query()))
        .order_by("-created_at", "-pk")
    )
    return queryset if actor.is_staff else queryset.filter(client=actor.profile)


def ad_queryset(actor: Actor):
    latest_payment = PaymentTransaction.objects.filter(
        ad=OuterRef("pk"), transaction_type=TransactionType.AD_BOOST
    ).order_by("-created_at", "-pk")
    queryset = (
        Ad.objects.select_related("city", "client__user")
        .annotate(payment_status=Subquery(latest_payment.values("status")[:1]))
        .order_by("-created_at", "-pk")
    )
    return queryset if actor.is_staff else queryset.filter(client=actor.profile)


def transaction_queryset(actor: Actor):
    queryset = PaymentTransaction.objects.select_related("user__user", "event", "ad").order_by(
        "-created_at", "-pk"
    )
    return queryset if actor.is_staff else queryset.filter(user=actor.profile)


def find(queryset, record_id) -> Optional[object]:
    value = str(record_id or "").strip()
    return queryset.filter(pk=int(value)).first() if value.isdigit() else None


@strawberry.type
class SpaceImage:
    id: strawberry.ID
    url: str


@strawberry_django.type(Event)
class SpaceEventType:
    id: auto
    created_at: auto
    name_en: Optional[str]
    name_fr: Optional[str]
    description_en: Optional[str]
    description_fr: Optional[str]
    start_date: auto = strawberry_django.field(field_name="startDate")
    end_date: auto = strawberry_django.field(field_name="endDate")
    time: auto
    price: auto
    link: auto
    short_link: Optional[str]
    boost: auto
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]
    category: Optional[Annotated["EventCategoryType", strawberry.lazy("api.schema")]]
    location: Optional[Annotated["LocationType", strawberry.lazy("api.schema")]]

    @strawberry.field
    def images(self, root: Event) -> List[SpaceImage]:
        return [
            SpaceImage(id=strawberry.ID(str(image.pk)), url=media_url(image.image) or "")
            for image in root.images.all()
            if image.image
        ]

    @strawberry.field
    def owner(self, root: Event) -> str:
        return owner_name(root.client)

    @strawberry.field
    def boost_pending(self, root: Event) -> bool:
        return bool(getattr(root, "boost_pending", False))


@strawberry_django.type(Ad)
class SpaceAdType:
    id: auto
    created_at: auto
    name: Optional[str]
    link: auto
    short_link: Optional[str]
    clicks: auto
    is_active: auto
    start_date: Optional[datetime.date] = strawberry_django.field(field_name="startDate")
    end_date: Optional[datetime.date] = strawberry_django.field(field_name="endDate")
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]

    @strawberry.field
    def image_mobile(self, root: Ad) -> Optional[str]:
        return media_url(root.image_mobile)

    @strawberry.field
    def image_tablet(self, root: Ad) -> Optional[str]:
        return media_url(root.image_tablet)

    @strawberry.field
    def owner(self, root: Ad) -> str:
        return owner_name(root.client)

    @strawberry.field
    def client_id(self, root: Ad) -> Optional[strawberry.ID]:
        return strawberry.ID(str(root.client_id)) if root.client_id else None

    @strawberry.field
    def payment_status(self, root: Ad) -> Optional[str]:
        return getattr(root, "payment_status", None)


@strawberry_django.type(PaymentTransaction)
class SpaceTransactionType:
    id: auto
    status: auto
    months: auto
    amount_ht: auto
    tax_amount: auto
    timbre_fiscal: auto
    total_ttc: auto
    created_at: auto
    validated_at: auto

    @strawberry.field
    def reference(self, root: PaymentTransaction) -> str:
        return root.reference

    @strawberry.field(name="type")
    def transaction_type(self, root: PaymentTransaction) -> str:
        return root.transaction_type

    @strawberry.field
    def subject(self, root: PaymentTransaction) -> Optional[str]:
        if root.event_id and root.event:
            return root.event.name_fr or root.event.name_en or root.event.name
        if root.ad_id and root.ad:
            return root.ad.name or root.ad.link
        return None

    @strawberry.field
    def partner_id(self, root: PaymentTransaction) -> strawberry.ID:
        return strawberry.ID(str(root.user_id))

    @strawberry.field
    def partner_name(self, root: PaymentTransaction) -> str:
        return owner_name(root.user)

    @strawberry.field
    def is_stale(self, root: PaymentTransaction) -> bool:
        return root.is_stale


@strawberry.type
class SpaceClientType:
    id: strawberry.ID
    company: str
    name: str
    email: str


@strawberry.type
class SpaceFieldError:
    field: str
    code: str


@strawberry.type
class SpacePayload:
    ok: bool
    error: Optional[str] = None
    field_errors: List[SpaceFieldError] = strawberry.field(default_factory=list)
    id: Optional[strawberry.ID] = None
    transaction: Optional[SpaceTransactionType] = None


@strawberry.input
class SpaceEventInput:
    name_en: str = ""
    name_fr: str = ""
    description_en: str = ""
    description_fr: str = ""
    category: str = ""
    city: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    time: str = ""
    price: str = ""
    link: str = ""
    boost: Optional[bool] = None
    keep_images: List[str] = strawberry.field(default_factory=list)


@strawberry.input
class SpaceAdInput:
    name: str = ""
    link: str = ""
    start_date: str = ""
    end_date: str = ""
    client: str = ""
    is_active: Optional[bool] = None


def failure(error: Optional[str] = None, field_errors: Optional[Dict[str, str]] = None) -> SpacePayload:
    return SpacePayload(
        ok=False,
        error=error or ("fixErrors" if field_errors else None),
        field_errors=[SpaceFieldError(field=name, code=code) for name, code in (field_errors or {}).items()],
    )


def single_line(value: str) -> str:
    return " ".join((value or "").split())


def rich_text_empty(value: str) -> bool:
    return not strip_tags(value or "").replace("&nbsp;", " ").strip()


def parse_date(value: str) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def parse_time(value: str) -> Optional[datetime.time]:
    try:
        return datetime.time.fromisoformat((value or "").strip())
    except ValueError:
        return None


def parse_price(value: str) -> Optional[Decimal]:
    try:
        price = Decimal((value or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    if not price.is_finite() or price < 0 or price >= MAX_PRICE:
        return None
    return money(price)


def link_error(value: str) -> Optional[str]:
    if not value:
        return "required"
    if len(value) > LINK_MAX_LENGTH:
        return "tooLong"
    try:
        URL_VALIDATOR(value)
    except ValidationError:
        return "url"
    return None


def image_error(upload) -> Optional[str]:
    if getattr(upload, "size", 0) > MAX_UPLOAD_BYTES:
        return "imageTooLarge"
    try:
        upload.seek(0)
        with PilImage.open(upload) as image:
            image.verify()
    except Exception:
        return "imageInvalid"
    finally:
        upload.seek(0)
    return None


def refresh_short_link(instance, title: str) -> bool:
    try:
        service = ShortIOService()
        if instance.short_id:
            updated = service.update_link(instance.short_id, instance.link, title=title)
            if updated:
                instance.short_link = updated.get("secureShortURL") or updated.get("shortURL") or instance.short_link
                return False
        created = service.shorten_url(instance.link, title=title)
        if created:
            instance.short_link = created.get("secureShortURL") or created.get("shortURL")
            instance.short_id = created.get("idString")
            return True
    except Exception as error:
        logger.error("Short.io error: %s", error)
    return False


def record_payment(profile: UserProfile, transaction_type: str, amount_ht: Decimal, **context) -> PaymentTransaction:
    payment = PaymentTransaction.objects.create(
        user=profile,
        transaction_type=transaction_type,
        status=TransactionStatus.PENDING,
        **invoice(amount_ht),
        **context,
    )
    send_transaction_emails(payment)
    return payment


def extend_subscription(profile: UserProfile, months: int) -> None:
    today = timezone.localdate()
    days = months * 30
    if not profile.subscription_renews_at or profile.subscription_renews_at < today:
        profile.subscription_started_at = today
        profile.subscription_renews_at = today + datetime.timedelta(days=days)
    else:
        profile.subscription_renews_at += datetime.timedelta(days=days)
    profile.subscription_status = "active"
    profile.subscription_plan = f"{months} months" if months > 1 else "1 month"
    profile.save(
        update_fields=[
            "subscription_started_at",
            "subscription_renews_at",
            "subscription_status",
            "subscription_plan",
            "updated_at",
        ]
    )


def event_image_matches(image: ImageEvent, keep: set) -> bool:
    if not image.image:
        return False
    return image.image.url in keep or (media_url(image.image) or "") in keep


@strawberry.type
class SpaceQuery:
    @strawberry.field
    def space_events(self, info: strawberry.Info) -> List[SpaceEventType]:
        return list(event_queryset(require_actor(info)))

    @strawberry.field
    def space_event(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceEventType]:
        return find(event_queryset(require_actor(info)), id)

    @strawberry.field
    def space_ads(self, info: strawberry.Info) -> List[SpaceAdType]:
        return list(ad_queryset(require_actor(info)))

    @strawberry.field
    def space_ad(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceAdType]:
        return find(ad_queryset(require_actor(info)), id)

    @strawberry.field
    def space_transactions(self, info: strawberry.Info, status: Optional[str] = None) -> List[SpaceTransactionType]:
        queryset = transaction_queryset(require_actor(info))
        if status:
            queryset = queryset.filter(status=status)
        return list(queryset)

    @strawberry.field
    def space_clients(self, info: strawberry.Info) -> List[SpaceClientType]:
        actor = require_actor(info)
        if not actor.is_staff:
            raise PermissionError("forbidden")
        profiles = (
            UserProfile.objects.select_related("user")
            .filter(user__is_active=True, user__is_staff=False, user__is_superuser=False)
            .order_by("company_name", "user__first_name", "user__username")
        )
        return [
            SpaceClientType(
                id=strawberry.ID(str(profile.pk)),
                company=profile.company_name,
                name=profile.user.get_full_name() or profile.user.get_username(),
                email=profile.user.email or "",
            )
            for profile in profiles
        ]


@strawberry.type
class SpaceMutation:
    @strawberry.mutation
    def save_event(
        self,
        info: strawberry.Info,
        input: SpaceEventInput,
        id: Optional[strawberry.ID] = None,
        images: Optional[List[Upload]] = None,
    ) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")

        event = None
        if id is not None:
            event = find(event_queryset(actor), id)
            if event is None:
                return failure("notFound")

        errors: Dict[str, str] = {}
        name_en = single_line(input.name_en)
        name_fr = single_line(input.name_fr)
        if not name_en or not name_fr:
            errors["name"] = "required"
        elif max(len(name_en), len(name_fr)) > NAME_MAX_LENGTH:
            errors["name"] = "tooLong"

        description_en = (input.description_en or "").strip()
        description_fr = (input.description_fr or "").strip()
        if rich_text_empty(description_en) or rich_text_empty(description_fr):
            errors["description"] = "required"

        category = EventCategory.objects.filter(pk=input.category).first() if input.category.isdigit() else None
        if category is None:
            errors["category"] = "required" if not input.category else "invalidChoice"

        city = City.objects.filter(pk=input.city).first() if input.city.isdigit() else None
        if city is None:
            errors["city"] = "required" if not input.city else "invalidChoice"

        location = None
        if input.location:
            location = Location.objects.filter(pk=input.location).first() if input.location.isdigit() else None
            if location is None:
                errors["location"] = "invalidChoice"

        start_date = parse_date(input.start_date)
        end_date = parse_date(input.end_date)
        if start_date is None:
            errors["startDate"] = "required" if not input.start_date else "date"
        if end_date is None:
            errors["endDate"] = "required" if not input.end_date else "date"
        elif start_date is not None and end_date < start_date:
            errors["endDate"] = "dateOrder"

        time = parse_time(input.time)
        if time is None:
            errors["time"] = "required" if not input.time else "time"

        price = parse_price(input.price)
        if price is None:
            errors["price"] = "required" if not input.price else "number"

        link = (input.link or "").strip()
        problem = link_error(link)
        if problem:
            errors["link"] = problem

        uploads = list(images or [])
        keep = {value for value in input.keep_images if value}
        kept = [image for image in event.images.all() if event_image_matches(image, keep)] if event else []
        upload_problem = next((problem for problem in map(image_error, uploads) if problem), None)
        if upload_problem:
            errors["images"] = upload_problem
        elif len(kept) + len(uploads) < 1:
            errors["images"] = "required"
        elif len(kept) + len(uploads) > MAX_EVENT_IMAGES:
            errors["images"] = "tooMany"

        if errors:
            return failure(field_errors=errors)

        with transaction.atomic():
            created = event is None
            if created:
                event = Event(client=actor.profile, created_by=actor.user)
            link_changed = created or event.link != link

            event.name_en = name_en
            event.name_fr = name_fr
            event.description_en = description_en
            event.description_fr = description_fr
            event.category = category
            event.city = city
            event.location = location
            event.startDate = start_date
            event.endDate = end_date
            event.time = time
            event.price = price
            event.link = link
            event.updated_by = actor.user
            if actor.is_staff and input.boost is not None:
                event.boost = input.boost
            if link_changed:
                refresh_short_link(event, "Event Campaign")
            event.save()

            if not created:
                kept_ids = {image.pk for image in kept}
                for image in event.images.exclude(pk__in=kept_ids):
                    image.delete()
            for upload in uploads:
                ImageEvent.objects.create(event=event, image=upload)

        return SpacePayload(ok=True, id=strawberry.ID(str(event.pk)))

    @strawberry.mutation
    def delete_event(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")
        event = find(event_queryset(actor), id)
        if event is None:
            return failure("notFound")
        event.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_ad(
        self,
        info: strawberry.Info,
        input: SpaceAdInput,
        id: Optional[strawberry.ID] = None,
        image_mobile: Optional[Upload] = None,
        image_tablet: Optional[Upload] = None,
    ) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")

        ad = None
        if id is not None:
            ad = find(ad_queryset(actor), id)
            if ad is None:
                return failure("notFound")
        created = ad is None

        errors: Dict[str, str] = {}
        name = single_line(input.name)
        if len(name) > NAME_MAX_LENGTH:
            errors["name"] = "tooLong"

        link = (input.link or "").strip()
        problem = link_error(link)
        if problem:
            errors["link"] = problem

        start_date = end_date = None
        if created:
            start_date = parse_date(input.start_date)
            end_date = parse_date(input.end_date)
            if start_date is None:
                errors["startDate"] = "required" if not input.start_date else "date"
            elif not actor.is_staff and start_date < timezone.localdate():
                errors["startDate"] = "dateInPast"
            if end_date is None:
                errors["endDate"] = "required" if not input.end_date else "date"
            elif start_date is not None and end_date < start_date:
                errors["endDate"] = "dateOrder"
            elif start_date is not None and (end_date - start_date).days + 1 > MAX_AD_DAYS:
                errors["endDate"] = "dateRange"

        for field_name, upload in (("imageMobile", image_mobile), ("imageTablet", image_tablet)):
            if upload is None:
                if created:
                    errors[field_name] = "required"
            else:
                problem = image_error(upload)
                if problem:
                    errors[field_name] = problem

        client = None
        if actor.is_staff and input.client:
            client = (
                UserProfile.objects.filter(pk=input.client, user__is_staff=False).first()
                if input.client.isdigit()
                else None
            )
            if client is None:
                errors["client"] = "invalidChoice"

        if errors:
            return failure(field_errors=errors)

        payment = None
        with transaction.atomic():
            if created:
                ad = Ad(
                    created_by=actor.user,
                    client=client or actor.profile,
                    country=Country.objects.filter(code2=DEFAULT_AD_COUNTRY).first(),
                    startDate=start_date,
                    endDate=end_date,
                    is_active=bool(input.is_active if input.is_active is not None else True)
                    if actor.is_staff
                    else False,
                )
            else:
                if client is not None:
                    ad.client = client
                if actor.is_staff and input.is_active is not None:
                    ad.is_active = input.is_active
            link_changed = created or ad.link != link

            ad.name = name or (ad.name if not created else "")
            ad.link = link
            ad.updated_by = actor.user
            if image_mobile is not None:
                ad.image_mobile = image_mobile
            if image_tablet is not None:
                ad.image_tablet = image_tablet
            if link_changed and refresh_short_link(ad, "Ad Campaign") and not created:
                ad.clicks = 0
            ad.save()

            if created and not actor.is_staff:
                days = (ad.endDate - ad.startDate).days + 1
                payment = record_payment(
                    actor.profile,
                    TransactionType.AD_BOOST,
                    AD_DAY_HT * days,
                    ad=ad,
                    ad_start_date=ad.startDate,
                    ad_end_date=ad.endDate,
                )

        return SpacePayload(ok=True, id=strawberry.ID(str(ad.pk)), transaction=payment)

    @strawberry.mutation
    def delete_ad(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")
        ad = find(ad_queryset(actor), id)
        if ad is None:
            return failure("notFound")
        ad.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def request_subscription(self, info: strawberry.Info, months: int) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")
        if actor.is_staff:
            return failure("forbidden")
        if months not in SUBSCRIPTION_RATES:
            return failure("invalidChoice")
        if PaymentTransaction.objects.filter(
            user=actor.profile,
            transaction_type=TransactionType.SUBSCRIPTION,
            status=TransactionStatus.PENDING,
        ).exists():
            return failure("alreadyPending")
        payment = record_payment(
            actor.profile,
            TransactionType.SUBSCRIPTION,
            SUBSCRIPTION_RATES[months],
            months=months,
        )
        return SpacePayload(ok=True, id=strawberry.ID(str(payment.pk)), transaction=payment)

    @strawberry.mutation
    def request_event_boost(self, info: strawberry.Info, event_id: strawberry.ID) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")
        if actor.is_staff:
            return failure("forbidden")
        event = find(event_queryset(actor), event_id)
        if event is None:
            return failure("notFound")
        if event.boost:
            return failure("alreadyBoosted")
        if event.boost_pending:
            return failure("alreadyPending")
        if event.startDate <= timezone.localdate() + datetime.timedelta(days=BOOST_LEAD_DAYS):
            return failure("boostTooLate")
        payment = record_payment(actor.profile, TransactionType.EVENT_BOOST, EVENT_BOOST_HT, event=event)
        return SpacePayload(ok=True, id=strawberry.ID(str(payment.pk)), transaction=payment)

    @strawberry.mutation
    def review_transaction(self, info: strawberry.Info, id: strawberry.ID, decision: str) -> SpacePayload:
        actor = current_actor(info)
        if actor is None:
            return failure("unauthenticated")
        if not actor.is_staff:
            return failure("forbidden")
        if decision not in ("validate", "cancel"):
            return failure("invalidChoice")

        with transaction.atomic():
            payment = find(
                PaymentTransaction.objects.select_for_update().select_related("user__user", "event", "ad"),
                id,
            )
            if payment is None:
                return failure("notFound")
            if payment.status != TransactionStatus.PENDING:
                return failure("notPending")

            if decision == "cancel":
                payment.status = TransactionStatus.CANCELED
                payment.save(update_fields=["status"])
            else:
                payment.status = TransactionStatus.VALIDATED
                payment.validated_at = timezone.now()
                payment.save(update_fields=["status", "validated_at"])
                if payment.transaction_type == TransactionType.SUBSCRIPTION and payment.months:
                    extend_subscription(payment.user, payment.months)
                elif payment.transaction_type == TransactionType.EVENT_BOOST and payment.event:
                    payment.event.boost = True
                    payment.event.save(update_fields=["boost"])
                elif payment.transaction_type == TransactionType.AD_BOOST and payment.ad:
                    payment.ad.startDate = payment.ad_start_date
                    payment.ad.endDate = payment.ad_end_date
                    payment.ad.is_active = True
                    payment.ad.save(update_fields=["startDate", "endDate", "is_active", "updated_at"])

        if decision == "cancel":
            send_cancellation_email(payment)
        else:
            send_validation_email(payment)
        return SpacePayload(ok=True, id=id, transaction=payment)
