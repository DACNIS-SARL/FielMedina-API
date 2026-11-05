import datetime
import logging
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Annotated, Dict, List, Optional, Tuple

import strawberry
import strawberry_django
from cities_light.models import City, SubRegion
from django.db import transaction
from django.db.models import Q
from strawberry import auto
from strawberry.file_uploads import Upload

from guard.models import (
    Event,
    EventCategory,
    Hiking,
    HikingLocation,
    ImageHiking,
    ImageLocation,
    Location,
    LocationCategory,
    Merchant,
    MerchantCategory,
    MerchantImage,
    MerchantProduct,
    OfflineCity,
    PublicTransport,
    PublicTransportTime,
    PublicTransportType,
    Tip,
    Weekday,
)
from shared.models import Page

from .space import (
    NAME_MAX_LENGTH,
    SpaceImage,
    SpacePayload,
    current_actor,
    failure,
    find,
    image_error,
    link_error,
    media_url,
    parse_date,
    parse_price,
    parse_time,
    refresh_short_link,
    rich_text_empty,
    single_line,
)

if TYPE_CHECKING:
    from .schema import CityType, LocationCategoryType, MerchantCategoryType, PublicTransportTypeType

logger = logging.getLogger(__name__)

MAX_GALLERY_IMAGES = 10
MAX_PRODUCTS = 20
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_MODEL_BYTES = 25 * 1024 * 1024
AUDIO_EXTENSIONS = (".aac", ".m4a")
SLUG_MAX_LENGTH = 50
BUS_NUMBER_MAX_LENGTH = 255
REGION_ID_MAX_LENGTH = 100
ICON_MAX_LENGTH = 100
CATEGORY_KINDS = ("location", "event", "merchant", "transport")
CATEGORY_MODELS = {
    "location": LocationCategory,
    "event": EventCategory,
    "merchant": MerchantCategory,
    "transport": PublicTransportType,
}


def require_staff(info: strawberry.Info):
    actor = current_actor(info)
    if actor is None:
        raise PermissionError("unauthenticated")
    if not actor.is_staff:
        raise PermissionError("forbidden")
    return actor


def staff_or_failure(info: strawberry.Info) -> Tuple[Optional[object], Optional[SpacePayload]]:
    actor = current_actor(info)
    if actor is None:
        return None, failure("unauthenticated")
    if not actor.is_staff:
        return None, failure("forbidden")
    return actor, None


def as_float(value) -> Optional[float]:
    return None if value is None else float(value)


def time_text(value: Optional[datetime.time]) -> Optional[str]:
    return value.strftime("%H:%M") if value else None


def bilingual(errors: Dict[str, str], field: str, en: str, fr: str, rich: bool = False, limit: Optional[int] = None):
    english = (en or "").strip() if rich else single_line(en)
    french = (fr or "").strip() if rich else single_line(fr)
    empty = rich_text_empty if rich else (lambda value: not value)
    if empty(english) or empty(french):
        errors[field] = "required"
    elif limit and max(len(english), len(french)) > limit:
        errors[field] = "tooLong"
    return english, french


def optional_bilingual(errors: Dict[str, str], field: str, en: str, fr: str, limit: int):
    english, french = single_line(en), single_line(fr)
    if max(len(english), len(french)) > limit:
        errors[field] = "tooLong"
    return english or None, french or None


def pick(errors: Dict[str, str], field: str, model, value: str, required: bool = True, **filters):
    value = (value or "").strip()
    if not value:
        if required:
            errors[field] = "required"
        return None
    found = model.objects.filter(pk=int(value), **filters).first() if value.isdigit() else None
    if found is None:
        errors[field] = "invalidChoice"
    return found


def parse_decimal(value: str) -> Optional[Decimal]:
    try:
        number = Decimal((value or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def coordinates(errors: Dict[str, str], latitude: str, longitude: str, required: bool = True):
    lat_text, lng_text = (latitude or "").strip(), (longitude or "").strip()
    if not lat_text and not lng_text:
        if required:
            errors["coordinates"] = "required"
        return None, None
    lat, lng = parse_decimal(lat_text), parse_decimal(lng_text)
    if lat is None or lng is None or abs(lat) > 90 or abs(lng) > 180:
        errors["coordinates"] = "coordinates"
        return None, None
    step = Decimal("0.000001")
    return lat.quantize(step), lng.quantize(step)


def optional_time(errors: Dict[str, str], field: str, value: str) -> Optional[datetime.time]:
    if not (value or "").strip():
        return None
    parsed = parse_time(value)
    if parsed is None:
        errors[field] = "time"
    return parsed


def optional_number(errors: Dict[str, str], field: str, value: str, default: float, minimum=None, maximum=None) -> float:
    if not (value or "").strip():
        return default
    number = parse_decimal(value)
    if number is None or (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
        errors[field] = "number"
        return default
    return float(number)


def file_error(upload, extensions: Tuple[str, ...], limit: int, signature=None) -> Optional[str]:
    name = (getattr(upload, "name", "") or "").lower()
    if not name.endswith(extensions):
        return "fileType"
    if getattr(upload, "size", 0) > limit:
        return "fileTooLarge"
    if signature:
        try:
            upload.seek(0)
            head = upload.read(12)
        finally:
            upload.seek(0)
        if not signature(head):
            return "fileType"
    return None


def audio_signature(head: bytes) -> bool:
    return head[4:8] == b"ftyp" or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xF0) == 0xF0)


def model_signature(head: bytes) -> bool:
    return head[:4] == b"glTF"


def gallery_errors(errors: Dict[str, str], existing, keep: set, uploads: list, required: bool) -> list:
    kept = [image for image in existing if image.image and (image.image.url in keep or (media_url(image.image) or "") in keep)]
    problem = next((problem for problem in map(image_error, uploads) if problem), None)
    if problem:
        errors["images"] = problem
    elif required and len(kept) + len(uploads) < 1:
        errors["images"] = "required"
    elif len(kept) + len(uploads) > MAX_GALLERY_IMAGES:
        errors["images"] = "tooMany"
    return kept


def sync_gallery(queryset, kept: list, uploads: list, create) -> None:
    kept_ids = {image.pk for image in kept}
    for image in queryset.exclude(pk__in=kept_ids):
        image.delete()
    for upload in uploads:
        create(upload)


def replace_file(instance, field: str, upload, remove: bool) -> Optional[str]:
    current = getattr(instance, field)
    stale = current.name if current else None
    if upload is not None:
        setattr(instance, field, upload)
        return stale
    if remove and stale:
        setattr(instance, field, None)
        return stale
    return None


def delete_stored(field_file, name: Optional[str]) -> None:
    if not name:
        return
    try:
        field_file.storage.delete(name)
    except Exception as error:
        logger.warning("Could not delete %s: %s", name, error)


def saved(instance) -> SpacePayload:
    return SpacePayload(ok=True, id=strawberry.ID(str(instance.pk)))


@strawberry.type
class SpaceProduct:
    id: strawberry.ID
    name_en: str
    name_fr: str
    price: Optional[float]
    image: Optional[str]


@strawberry.type
class SpaceStop:
    id: strawberry.ID
    order: int
    name_en: str
    name_fr: str


@strawberry.type
class SpaceSubRegion:
    id: strawberry.ID
    name: str
    region_id: strawberry.ID
    region: str


@strawberry_django.type(Location)
class SpaceLocationType:
    id: auto
    name_en: Optional[str]
    name_fr: Optional[str]
    story_en: Optional[str]
    story_fr: Optional[str]
    admission_fee: Optional[Decimal] = strawberry_django.field(field_name="admissionFee")
    is_active_ads: auto
    model_scale: auto
    model_rotation: auto
    model_altitude: auto
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]
    category: Optional[Annotated["LocationCategoryType", strawberry.lazy("api.schema")]]

    @strawberry.field
    def latitude(self, root: Location) -> Optional[float]:
        return as_float(root.latitude)

    @strawberry.field
    def longitude(self, root: Location) -> Optional[float]:
        return as_float(root.longitude)

    @strawberry.field
    def open_from(self, root: Location) -> Optional[str]:
        return time_text(root.openFrom)

    @strawberry.field
    def open_to(self, root: Location) -> Optional[str]:
        return time_text(root.openTo)

    @strawberry.field
    def closed_days(self, root: Location) -> List[int]:
        return sorted(day.day for day in root.closedDays.all())

    @strawberry.field
    def images(self, root: Location) -> List[SpaceImage]:
        return [SpaceImage(id=strawberry.ID(str(image.pk)), url=media_url(image.image) or "") for image in root.images.all() if image.image]

    @strawberry.field
    def voiceover_en(self, root: Location) -> Optional[str]:
        return media_url(root.voiceover_en)

    @strawberry.field
    def voiceover_fr(self, root: Location) -> Optional[str]:
        return media_url(root.voiceover_fr)

    @strawberry.field
    def model3d(self, root: Location) -> Optional[str]:
        return media_url(root.model_3d)


@strawberry_django.type(Merchant)
class SpaceMerchantType:
    id: auto
    created_at: auto
    name_en: Optional[str]
    name_fr: Optional[str]
    description_en: Optional[str]
    description_fr: Optional[str]
    address_en: Optional[str]
    address_fr: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    short_link: Optional[str]
    price_range: auto
    is_active: auto
    is_featured: auto
    contract_status: auto
    contract_start: auto
    contract_end: auto
    contract_notes: Optional[str]
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]
    category: Optional[Annotated["MerchantCategoryType", strawberry.lazy("api.schema")]]

    @strawberry.field
    def latitude(self, root: Merchant) -> Optional[float]:
        return as_float(root.latitude)

    @strawberry.field
    def longitude(self, root: Merchant) -> Optional[float]:
        return as_float(root.longitude)

    @strawberry.field
    def open_from(self, root: Merchant) -> Optional[str]:
        return time_text(root.open_from)

    @strawberry.field
    def open_to(self, root: Merchant) -> Optional[str]:
        return time_text(root.open_to)

    @strawberry.field
    def cover(self, root: Merchant) -> Optional[str]:
        return media_url(root.cover)

    @strawberry.field
    def images(self, root: Merchant) -> List[SpaceImage]:
        return [
            SpaceImage(id=strawberry.ID(str(image.pk)), url=media_url(image.image) or "")
            for image in root.images.all()
            if image.image
        ]

    @strawberry.field
    def products(self, root: Merchant) -> List[SpaceProduct]:
        return [
            SpaceProduct(
                id=strawberry.ID(str(product.pk)),
                name_en=product.name_en or "",
                name_fr=product.name_fr or "",
                price=as_float(product.price),
                image=media_url(product.image),
            )
            for product in root.products.order_by("pk")
        ]

    @strawberry.field
    def ratings_count(self, root: Merchant) -> int:
        return root.ratings.filter(is_approved=True).count()

    @strawberry.field
    def average_rating(self, root: Merchant) -> Optional[float]:
        stars = list(root.ratings.filter(is_approved=True).values_list("stars", flat=True))
        return round(sum(stars) / len(stars), 1) if stars else None


@strawberry_django.type(Hiking)
class SpaceHikingType:
    id: auto
    name_en: Optional[str]
    name_fr: Optional[str]
    description_en: Optional[str]
    description_fr: Optional[str]
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]

    @strawberry.field
    def latitude(self, root: Hiking) -> Optional[float]:
        return as_float(root.latitude)

    @strawberry.field
    def longitude(self, root: Hiking) -> Optional[float]:
        return as_float(root.longitude)

    @strawberry.field
    def stops(self, root: Hiking) -> List[SpaceStop]:
        return [
            SpaceStop(
                id=strawberry.ID(str(stop.location_id)),
                order=stop.order,
                name_en=stop.location.name_en or "",
                name_fr=stop.location.name_fr or "",
            )
            for stop in root.hikinglocation_set.select_related("location").order_by("order", "pk")
        ]

    @strawberry.field
    def images(self, root: Hiking) -> List[SpaceImage]:
        return [SpaceImage(id=strawberry.ID(str(image.pk)), url=media_url(image.image) or "") for image in root.images.all() if image.image]


@strawberry_django.type(PublicTransport)
class SpaceTransportType:
    id: auto
    updated_at: auto
    bus_number: str = strawberry_django.field(field_name="busNumber")
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]
    type: Optional[Annotated["PublicTransportTypeType", strawberry.lazy("api.schema")]] = strawberry_django.field(
        field_name="publicTransportType"
    )

    @strawberry.field
    def from_region(self, root: PublicTransport) -> Optional[strawberry.ID]:
        return strawberry.ID(str(root.fromRegion_id)) if root.fromRegion_id else None

    @strawberry.field
    def to_region(self, root: PublicTransport) -> Optional[strawberry.ID]:
        return strawberry.ID(str(root.toRegion_id)) if root.toRegion_id else None

    @strawberry.field
    def times(self, root: PublicTransport) -> List[str]:
        return [time_text(entry.time) for entry in root.publicTransportTimes.order_by("time")]


@strawberry_django.type(Page)
class SpacePageType:
    id: auto
    updated_at: auto
    is_active: auto
    slug_en: Optional[str]
    slug_fr: Optional[str]
    title_en: Optional[str]
    title_fr: Optional[str]
    content_en: Optional[str]
    content_fr: Optional[str]


@strawberry_django.type(OfflineCity)
class SpaceOfflineCityType:
    id: auto
    updated_at: auto
    region_id: auto
    name_en: Optional[str]
    name_fr: Optional[str]
    radius: auto
    is_active: auto
    city: Optional[Annotated["CityType", strawberry.lazy("api.schema")]]

    @strawberry.field
    def latitude(self, root: OfflineCity) -> Optional[float]:
        return as_float(root.latitude)

    @strawberry.field
    def longitude(self, root: OfflineCity) -> Optional[float]:
        return as_float(root.longitude)


@strawberry.input
class SpaceLocationInput:
    name_en: str = ""
    name_fr: str = ""
    story_en: str = ""
    story_fr: str = ""
    category: str = ""
    city: str = ""
    latitude: str = ""
    longitude: str = ""
    open_from: str = ""
    open_to: str = ""
    admission_fee: str = ""
    closed_days: List[str] = strawberry.field(default_factory=list)
    is_active_ads: bool = False
    model_scale: str = ""
    model_rotation: str = ""
    model_altitude: str = ""
    keep_images: List[str] = strawberry.field(default_factory=list)
    remove_voiceover_en: bool = False
    remove_voiceover_fr: bool = False
    remove_model3d: bool = False


@strawberry.input
class SpaceProductInput:
    id: str = ""
    name_en: str = ""
    name_fr: str = ""
    price: str = ""
    keep_image: bool = True


@strawberry.input
class SpaceMerchantInput:
    name_en: str = ""
    name_fr: str = ""
    description_en: str = ""
    description_fr: str = ""
    address_en: str = ""
    address_fr: str = ""
    category: str = ""
    city: str = ""
    latitude: str = ""
    longitude: str = ""
    phone: str = ""
    website: str = ""
    price_range: str = ""
    open_from: str = ""
    open_to: str = ""
    is_active: bool = False
    is_featured: bool = False
    contract_status: str = ""
    contract_start: str = ""
    contract_end: str = ""
    contract_notes: str = ""
    products: List[SpaceProductInput] = strawberry.field(default_factory=list)
    keep_images: List[str] = strawberry.field(default_factory=list)


@strawberry.input
class SpaceHikingInput:
    name_en: str = ""
    name_fr: str = ""
    description_en: str = ""
    description_fr: str = ""
    city: str = ""
    latitude: str = ""
    longitude: str = ""
    stops: List[str] = strawberry.field(default_factory=list)
    keep_images: List[str] = strawberry.field(default_factory=list)


@strawberry.input
class SpaceTipInput:
    city: str = ""
    description_en: str = ""
    description_fr: str = ""


@strawberry.input
class SpaceTransportInput:
    type: str = ""
    city: str = ""
    from_region: str = ""
    to_region: str = ""
    bus_number: str = ""
    times: List[str] = strawberry.field(default_factory=list)


@strawberry.input
class SpacePageInput:
    slug_en: str = ""
    slug_fr: str = ""
    title_en: str = ""
    title_fr: str = ""
    content_en: str = ""
    content_fr: str = ""
    is_active: bool = True


@strawberry.input
class SpaceOfflineCityInput:
    name_en: str = ""
    name_fr: str = ""
    region_id: str = ""
    city: str = ""
    latitude: str = ""
    longitude: str = ""
    radius: str = ""
    is_active: bool = True


@strawberry.input
class SpaceCategoryInput:
    name_en: str = ""
    name_fr: str = ""
    icon: str = ""


def slug_error(value: str) -> Optional[str]:
    if not value:
        return "required"
    if len(value) > SLUG_MAX_LENGTH:
        return "tooLong"
    if not all(character.isalnum() and character.isascii() or character in "-_" for character in value):
        return "slug"
    return None


def category_in_use(kind: str, category) -> bool:
    if kind == "location":
        return Location.objects.filter(category=category).exists()
    if kind == "event":
        return Event.objects.filter(category=category).exists()
    if kind == "merchant":
        return Merchant.objects.filter(category=category).exists()
    return PublicTransport.objects.filter(publicTransportType=category).exists()


@strawberry.type
class SpaceContentQuery:
    @strawberry.field
    def space_location(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceLocationType]:
        require_staff(info)
        return find(Location.objects.select_related("city", "category").prefetch_related("images", "closedDays"), id)

    @strawberry.field
    def space_merchants(self, info: strawberry.Info) -> List[SpaceMerchantType]:
        require_staff(info)
        return list(
            Merchant.objects.select_related("city", "category")
            .prefetch_related("images")
            .order_by("-is_featured", "-created_at")
        )

    @strawberry.field
    def space_merchant(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceMerchantType]:
        require_staff(info)
        return find(Merchant.objects.select_related("city", "category").prefetch_related("images"), id)

    @strawberry.field
    def space_hiking(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceHikingType]:
        require_staff(info)
        return find(Hiking.objects.select_related("city").prefetch_related("images"), id)

    @strawberry.field
    def space_transport(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceTransportType]:
        require_staff(info)
        return find(PublicTransport.objects.select_related("city", "publicTransportType"), id)

    @strawberry.field
    def space_pages(self, info: strawberry.Info) -> List[SpacePageType]:
        require_staff(info)
        return list(Page.objects.order_by("slug"))

    @strawberry.field
    def space_page(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpacePageType]:
        require_staff(info)
        return find(Page.objects.all(), id)

    @strawberry.field
    def space_offline_cities(self, info: strawberry.Info) -> List[SpaceOfflineCityType]:
        require_staff(info)
        return list(OfflineCity.objects.select_related("city").order_by("name"))

    @strawberry.field
    def space_offline_city(self, info: strawberry.Info, id: strawberry.ID) -> Optional[SpaceOfflineCityType]:
        require_staff(info)
        return find(OfflineCity.objects.select_related("city"), id)

    @strawberry.field
    def space_sub_regions(self, info: strawberry.Info) -> List[SpaceSubRegion]:
        require_staff(info)
        city_ids = (
            set(Location.objects.values_list("city_id", flat=True))
            | set(PublicTransport.objects.values_list("city_id", flat=True))
            | set(OfflineCity.objects.values_list("city_id", flat=True))
        )
        regions = (
            City.objects.filter(pk__in=[city for city in city_ids if city])
            .exclude(region__isnull=True)
            .values_list("region_id", flat=True)
            .distinct()
        )
        return [
            SpaceSubRegion(
                id=strawberry.ID(str(sub_region.pk)),
                name=sub_region.name,
                region_id=strawberry.ID(str(sub_region.region_id)),
                region=sub_region.region.name if sub_region.region else "",
            )
            for sub_region in SubRegion.objects.filter(region_id__in=list(regions)).select_related("region").order_by("name")
        ]


@strawberry.type
class SpaceContentMutation:
    @strawberry.mutation
    def save_location(
        self,
        info: strawberry.Info,
        input: SpaceLocationInput,
        id: Optional[strawberry.ID] = None,
        images: Optional[List[Upload]] = None,
        voiceover_en: Optional[Upload] = None,
        voiceover_fr: Optional[Upload] = None,
        model3d: Optional[Upload] = None,
    ) -> SpacePayload:
        actor, denied = staff_or_failure(info)
        if denied:
            return denied
        location = None
        if id is not None:
            location = find(Location.objects.prefetch_related("images"), id)
            if location is None:
                return failure("notFound")

        errors: Dict[str, str] = {}
        name_en, name_fr = bilingual(errors, "name", input.name_en, input.name_fr, limit=NAME_MAX_LENGTH)
        story_en, story_fr = bilingual(errors, "story", input.story_en, input.story_fr, rich=True)
        category = pick(errors, "category", LocationCategory, input.category)
        city = pick(errors, "city", City, input.city)
        latitude, longitude = coordinates(errors, input.latitude, input.longitude)
        open_from = optional_time(errors, "openFrom", input.open_from)
        open_to = optional_time(errors, "openTo", input.open_to)
        admission_fee = None
        if (input.admission_fee or "").strip():
            admission_fee = parse_price(input.admission_fee)
            if admission_fee is None:
                errors["admissionFee"] = "number"
        days = sorted({int(day) for day in input.closed_days if str(day).isdigit()})
        if any(day < 1 or day > 7 for day in days) or len(days) != len(set(input.closed_days)):
            errors["closedDays"] = "invalidChoice"
        model_scale = optional_number(errors, "modelScale", input.model_scale, 1.0, minimum=Decimal("0.001"))
        model_rotation = optional_number(errors, "modelRotation", input.model_rotation, 0.0, minimum=0, maximum=360)
        model_altitude = optional_number(errors, "modelAltitude", input.model_altitude, 0.0)
        uploads = list(images or [])
        existing = list(location.images.all()) if location else []
        kept = gallery_errors(errors, existing, set(input.keep_images), uploads, required=True)
        for field, upload in (("voiceoverEn", voiceover_en), ("voiceoverFr", voiceover_fr)):
            if upload is not None:
                problem = file_error(upload, AUDIO_EXTENSIONS, MAX_AUDIO_BYTES, audio_signature)
                if problem:
                    errors[field] = problem
        if model3d is not None:
            problem = file_error(model3d, (".glb",), MAX_MODEL_BYTES, model_signature)
            if problem:
                errors["model3d"] = problem
        if errors:
            return failure(field_errors=errors)

        stale = []
        with transaction.atomic():
            created = location is None
            if created:
                location = Location(created_by=actor.user)
            location.name_en, location.name_fr = name_en, name_fr
            location.story_en, location.story_fr = story_en, story_fr
            location.category = category
            location.city = city
            location.country = city.country
            location.latitude, location.longitude = latitude, longitude
            location.openFrom, location.openTo = open_from, open_to
            location.admissionFee = admission_fee
            location.is_active_ads = input.is_active_ads
            location.model_scale, location.model_rotation, location.model_altitude = model_scale, model_rotation, model_altitude
            location.updated_by = actor.user
            if created:
                location.save()
            for field, upload, remove in (
                ("voiceover_en", voiceover_en, input.remove_voiceover_en),
                ("voiceover_fr", voiceover_fr, input.remove_voiceover_fr),
                ("model_3d", model3d, input.remove_model3d),
            ):
                previous = replace_file(location, field, upload, remove)
                if previous:
                    stale.append((field, previous))
            location.save()
            location.closedDays.set([Weekday.objects.get_or_create(day=day)[0] for day in days])
            sync_gallery(location.images.all(), kept, uploads, lambda upload: ImageLocation.objects.create(location=location, image=upload))
        for field, name in stale:
            if getattr(location, field).name != name:
                delete_stored(getattr(location, field), name)
        return saved(location)

    @strawberry.mutation
    def delete_location(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        location = find(Location.objects.all(), id)
        if location is None:
            return failure("notFound")
        model_file = location.model_3d
        model_name = model_file.name if model_file else None
        location.delete()
        delete_stored(model_file, model_name)
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_merchant(
        self,
        info: strawberry.Info,
        input: SpaceMerchantInput,
        id: Optional[strawberry.ID] = None,
        cover: Optional[Upload] = None,
        images: Optional[List[Upload]] = None,
        product_images: Optional[List[Optional[Upload]]] = None,
    ) -> SpacePayload:
        actor, denied = staff_or_failure(info)
        if denied:
            return denied
        merchant = None
        if id is not None:
            merchant = find(Merchant.objects.prefetch_related("images", "products"), id)
            if merchant is None:
                return failure("notFound")

        errors: Dict[str, str] = {}
        name_en, name_fr = bilingual(errors, "name", input.name_en, input.name_fr, limit=NAME_MAX_LENGTH)
        description_en, description_fr = bilingual(errors, "description", input.description_en, input.description_fr, rich=True)
        address_en, address_fr = optional_bilingual(errors, "address", input.address_en, input.address_fr, 500)
        category = pick(errors, "category", MerchantCategory, input.category)
        city = pick(errors, "city", City, input.city)
        latitude, longitude = coordinates(errors, input.latitude, input.longitude)
        phone = single_line(input.phone)
        if len(phone) > 30 or (phone and not any(character.isdigit() for character in phone)):
            errors["phone"] = "phone"
        website = (input.website or "").strip()
        if website:
            problem = link_error(website)
            if problem:
                errors["website"] = problem
        price_range = input.price_range or Merchant.PriceRange.MODERATE
        if price_range not in Merchant.PriceRange.values:
            errors["priceRange"] = "invalidChoice"
        open_from = optional_time(errors, "openFrom", input.open_from)
        open_to = optional_time(errors, "openTo", input.open_to)
        if open_from and open_to and open_from >= open_to:
            errors["openTo"] = "timeOrder"
        contract_status = input.contract_status or Merchant.ContractStatus.PENDING
        if contract_status not in Merchant.ContractStatus.values:
            errors["contractStatus"] = "invalidChoice"
        contract_start = parse_date(input.contract_start) if input.contract_start else None
        contract_end = parse_date(input.contract_end) if input.contract_end else None
        if input.contract_start and contract_start is None:
            errors["contractStart"] = "date"
        if input.contract_end and contract_end is None:
            errors["contractEnd"] = "date"
        elif contract_start and contract_end and contract_start >= contract_end:
            errors["contractEnd"] = "dateOrder"
        if cover is None and not (merchant and merchant.cover):
            errors["cover"] = "required"
        elif cover is not None:
            problem = image_error(cover)
            if problem:
                errors["cover"] = problem

        existing_products = {str(product.pk): product for product in (merchant.products.all() if merchant else [])}
        product_uploads = list(product_images or [])
        products = []
        if len(input.products) > MAX_PRODUCTS:
            errors["products"] = "tooMany"
        for index, row in enumerate(input.products):
            product_en, product_fr = single_line(row.name_en), single_line(row.name_fr)
            price_text = (row.price or "").strip()
            if not product_en and not product_fr and not price_text and not row.id:
                continue
            upload = product_uploads[index] if index < len(product_uploads) else None
            if not product_en or not product_fr:
                errors["products"] = "productName"
            elif max(len(product_en), len(product_fr)) > NAME_MAX_LENGTH:
                errors["products"] = "tooLong"
            price = None
            if price_text:
                price = parse_price(price_text)
                if price is None:
                    errors["products"] = "number"
            if upload is not None:
                problem = image_error(upload)
                if problem:
                    errors["products"] = problem
            if row.id and row.id not in existing_products:
                errors["products"] = "invalidChoice"
            products.append((existing_products.get(row.id), product_en, product_fr, price, upload, row.keep_image))

        uploads = list(images or [])
        existing = list(merchant.images.all()) if merchant else []
        kept = gallery_errors(errors, existing, set(input.keep_images), uploads, required=False)
        if errors:
            return failure(field_errors=errors)

        stale = []
        discarded = []
        with transaction.atomic():
            created = merchant is None
            if created:
                merchant = Merchant(created_by=actor.user)
            website_changed = (merchant.website or "") != website
            merchant.name_en, merchant.name_fr = name_en, name_fr
            merchant.description_en, merchant.description_fr = description_en, description_fr
            merchant.address_en, merchant.address_fr = address_en, address_fr
            merchant.category = category
            merchant.city = city
            merchant.latitude, merchant.longitude = latitude, longitude
            merchant.phone = phone or None
            merchant.website = website or None
            merchant.price_range = price_range
            merchant.open_from, merchant.open_to = open_from, open_to
            merchant.is_active = input.is_active
            merchant.is_featured = input.is_featured
            merchant.contract_status = contract_status
            merchant.contract_start, merchant.contract_end = contract_start, contract_end
            merchant.contract_notes = (input.contract_notes or "").strip() or None
            merchant.updated_by = actor.user
            previous_cover = replace_file(merchant, "cover", cover, False)
            if previous_cover:
                stale.append((merchant.cover, previous_cover))
            if website_changed:
                if website:
                    refresh_short_link(merchant, "Merchant Website", website)
                else:
                    merchant.short_link = None
                    merchant.short_id = None
            merchant.save()

            keep_ids = {product.pk for product, *_rest in products if product is not None}
            for product in merchant.products.exclude(pk__in=keep_ids):
                if product.image:
                    discarded.append((product.image, product.image.name))
                product.delete()
            for product, product_en, product_fr, price, upload, keep_image in products:
                product = product or MerchantProduct(merchant=merchant)
                product.name_en, product.name_fr, product.price = product_en, product_fr, price
                previous_image = replace_file(product, "image", upload, not keep_image)
                if previous_image:
                    stale.append((product.image, previous_image))
                product.save()

            sync_gallery(
                MerchantImage.objects.filter(merchant=merchant),
                kept,
                uploads,
                lambda upload: MerchantImage.objects.create(merchant=merchant, image=upload),
            )
        for field_file, name in stale:
            if not field_file or field_file.name != name:
                delete_stored(field_file, name)
        for field_file, name in discarded:
            delete_stored(field_file, name)
        return saved(merchant)

    @strawberry.mutation
    def delete_merchant(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        merchant = find(Merchant.objects.all(), id)
        if merchant is None:
            return failure("notFound")
        files = [(merchant.cover, merchant.cover.name)] if merchant.cover else []
        files += [(product.image, product.image.name) for product in merchant.products.all() if product.image]
        merchant.delete()
        for field_file, name in files:
            delete_stored(field_file, name)
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_hiking(
        self,
        info: strawberry.Info,
        input: SpaceHikingInput,
        id: Optional[strawberry.ID] = None,
        images: Optional[List[Upload]] = None,
    ) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        hiking = None
        if id is not None:
            hiking = find(Hiking.objects.prefetch_related("images"), id)
            if hiking is None:
                return failure("notFound")

        errors: Dict[str, str] = {}
        name_en, name_fr = bilingual(errors, "name", input.name_en, input.name_fr, limit=NAME_MAX_LENGTH)
        description_en, description_fr = bilingual(errors, "description", input.description_en, input.description_fr, rich=True)
        city = pick(errors, "city", City, input.city)
        latitude, longitude = coordinates(errors, input.latitude, input.longitude, required=False)
        stop_ids = [stop for stop in (value.strip() for value in input.stops) if stop]
        if not all(stop.isdigit() for stop in stop_ids):
            errors["stops"] = "invalidChoice"
        elif len(stop_ids) != len(set(stop_ids)):
            errors["stops"] = "duplicateStop"
        stops = {str(location.pk): location for location in Location.objects.filter(pk__in=[int(stop) for stop in stop_ids if stop.isdigit()])}
        if "stops" not in errors and len(stops) != len(stop_ids):
            errors["stops"] = "invalidChoice"
        uploads = list(images or [])
        existing = list(hiking.images.all()) if hiking else []
        kept = gallery_errors(errors, existing, set(input.keep_images), uploads, required=True)
        if errors:
            return failure(field_errors=errors)

        with transaction.atomic():
            hiking = hiking or Hiking()
            hiking.name_en, hiking.name_fr = name_en, name_fr
            hiking.description_en, hiking.description_fr = description_en, description_fr
            hiking.city = city
            hiking.latitude, hiking.longitude = latitude, longitude
            hiking.save()
            HikingLocation.objects.filter(hiking=hiking).delete()
            HikingLocation.objects.bulk_create(
                [HikingLocation(hiking=hiking, location=stops[stop], order=index) for index, stop in enumerate(stop_ids)]
            )
            sync_gallery(hiking.images.all(), kept, uploads, lambda upload: ImageHiking.objects.create(hiking=hiking, image=upload))
        return saved(hiking)

    @strawberry.mutation
    def delete_hiking(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        hiking = find(Hiking.objects.all(), id)
        if hiking is None:
            return failure("notFound")
        hiking.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_tip(self, info: strawberry.Info, input: SpaceTipInput, id: Optional[strawberry.ID] = None) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        tip = None
        if id is not None:
            tip = find(Tip.objects.all(), id)
            if tip is None:
                return failure("notFound")
        errors: Dict[str, str] = {}
        city = pick(errors, "city", City, input.city)
        description_en, description_fr = bilingual(errors, "description", input.description_en, input.description_fr, rich=True)
        if errors:
            return failure(field_errors=errors)
        tip = tip or Tip()
        tip.city = city
        tip.description_en, tip.description_fr = description_en, description_fr
        tip.save()
        return saved(tip)

    @strawberry.mutation
    def delete_tip(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        tip = find(Tip.objects.all(), id)
        if tip is None:
            return failure("notFound")
        tip.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_transport(
        self, info: strawberry.Info, input: SpaceTransportInput, id: Optional[strawberry.ID] = None
    ) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        transport = None
        if id is not None:
            transport = find(PublicTransport.objects.all(), id)
            if transport is None:
                return failure("notFound")
        errors: Dict[str, str] = {}
        transport_type = pick(errors, "type", PublicTransportType, input.type)
        city = pick(errors, "city", City, input.city)
        region_filter = {"region_id": city.region_id} if city and city.region_id else {}
        from_region = pick(errors, "fromRegion", SubRegion, input.from_region, required=False, **region_filter)
        to_region = pick(errors, "toRegion", SubRegion, input.to_region, required=False, **region_filter)
        bus_number = single_line(input.bus_number)
        if not bus_number:
            errors["busNumber"] = "required"
        elif len(bus_number) > BUS_NUMBER_MAX_LENGTH:
            errors["busNumber"] = "tooLong"
        times = []
        for value in input.times:
            if not (value or "").strip():
                continue
            parsed = parse_time(value)
            if parsed is None:
                errors["times"] = "time"
                break
            times.append(parsed.replace(second=0, microsecond=0))
        times = sorted(set(times))
        if "times" not in errors and not times:
            errors["times"] = "required"
        if errors:
            return failure(field_errors=errors)
        with transaction.atomic():
            transport = transport or PublicTransport()
            transport.publicTransportType = transport_type
            transport.city = city
            transport.fromRegion, transport.toRegion = from_region, to_region
            transport.busNumber = bus_number
            transport.save()
            PublicTransportTime.objects.filter(publicTransport=transport).delete()
            PublicTransportTime.objects.bulk_create([PublicTransportTime(publicTransport=transport, time=time) for time in times])
        return saved(transport)

    @strawberry.mutation
    def delete_transport(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        transport = find(PublicTransport.objects.all(), id)
        if transport is None:
            return failure("notFound")
        transport.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_page(self, info: strawberry.Info, input: SpacePageInput, id: Optional[strawberry.ID] = None) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        page = None
        if id is not None:
            page = find(Page.objects.all(), id)
            if page is None:
                return failure("notFound")
        errors: Dict[str, str] = {}
        slug_en, slug_fr = (input.slug_en or "").strip().lower(), (input.slug_fr or "").strip().lower()
        problem = slug_error(slug_en) or slug_error(slug_fr)
        if problem:
            errors["slug"] = problem
        else:
            others = Page.objects.exclude(pk=page.pk) if page else Page.objects.all()
            if others.filter(
                Q(slug__in=[slug_en, slug_fr]) | Q(slug_en__in=[slug_en, slug_fr]) | Q(slug_fr__in=[slug_en, slug_fr])
            ).exists():
                errors["slug"] = "slugTaken"
        title_en, title_fr = bilingual(errors, "title", input.title_en, input.title_fr, limit=NAME_MAX_LENGTH)
        content_en, content_fr = bilingual(errors, "content", input.content_en, input.content_fr, rich=True)
        if errors:
            return failure(field_errors=errors)
        page = page or Page()
        page.slug = slug_en
        page.slug_en, page.slug_fr = slug_en, slug_fr
        page.title_en, page.title_fr = title_en, title_fr
        page.content_en, page.content_fr = content_en, content_fr
        page.is_active = input.is_active
        page.save()
        return saved(page)

    @strawberry.mutation
    def delete_page(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        page = find(Page.objects.all(), id)
        if page is None:
            return failure("notFound")
        page.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_offline_city(
        self, info: strawberry.Info, input: SpaceOfflineCityInput, id: Optional[strawberry.ID] = None
    ) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        region = None
        if id is not None:
            region = find(OfflineCity.objects.all(), id)
            if region is None:
                return failure("notFound")
        errors: Dict[str, str] = {}
        name_en, name_fr = bilingual(errors, "name", input.name_en, input.name_fr, limit=NAME_MAX_LENGTH)
        region_id = region.region_id if region else (input.region_id or "").strip()
        if region is None:
            if not region_id:
                errors["regionId"] = "required"
            elif len(region_id) > REGION_ID_MAX_LENGTH:
                errors["regionId"] = "tooLong"
            elif not all(character.isascii() and (character.isalnum() or character in "-_") for character in region_id):
                errors["regionId"] = "slug"
            elif OfflineCity.objects.filter(region_id=region_id).exists():
                errors["regionId"] = "slugTaken"
        city = pick(errors, "city", City, input.city, required=False)
        latitude, longitude = coordinates(errors, input.latitude, input.longitude)
        radius = parse_decimal(input.radius)
        if not (input.radius or "").strip():
            errors["radius"] = "required"
        elif radius is None or radius <= 0 or radius > 100000:
            errors["radius"] = "number"
        if errors:
            return failure(field_errors=errors)
        region = region or OfflineCity(region_id=region_id)
        region.name_en, region.name_fr = name_en, name_fr
        region.city = city
        region.latitude, region.longitude = latitude, longitude
        region.radius = float(radius)
        region.is_active = input.is_active
        region.save()
        return saved(region)

    @strawberry.mutation
    def delete_offline_city(self, info: strawberry.Info, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        region = find(OfflineCity.objects.all(), id)
        if region is None:
            return failure("notFound")
        region.delete()
        return SpacePayload(ok=True, id=id)

    @strawberry.mutation
    def save_category(
        self, info: strawberry.Info, kind: str, input: SpaceCategoryInput, id: Optional[strawberry.ID] = None
    ) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        if kind not in CATEGORY_KINDS:
            return failure(field_errors={"kind": "invalidChoice"})
        model = CATEGORY_MODELS[kind]
        category = None
        if id is not None:
            category = find(model.objects.all(), id)
            if category is None:
                return failure("notFound")
        errors: Dict[str, str] = {}
        limit = 100 if kind == "merchant" else NAME_MAX_LENGTH
        name_en, name_fr = bilingual(errors, "name", input.name_en, input.name_fr, limit=limit)
        icon = single_line(input.icon)
        if kind == "merchant" and len(icon) > ICON_MAX_LENGTH:
            errors["icon"] = "tooLong"
        if errors:
            return failure(field_errors=errors)
        category = category or model()
        category.name_en, category.name_fr = name_en, name_fr
        if kind == "merchant":
            category.icon = icon or None
        category.save()
        return SpacePayload(ok=True, id=strawberry.ID(f"{kind}-{category.pk}"))

    @strawberry.mutation
    def delete_category(self, info: strawberry.Info, kind: str, id: strawberry.ID) -> SpacePayload:
        _actor, denied = staff_or_failure(info)
        if denied:
            return denied
        if kind not in CATEGORY_KINDS:
            return failure("notFound")
        category = find(CATEGORY_MODELS[kind].objects.all(), id)
        if category is None:
            return failure("notFound")
        if category_in_use(kind, category):
            return failure("inUse")
        category.delete()
        return SpacePayload(ok=True, id=strawberry.ID(f"{kind}-{id}"))
