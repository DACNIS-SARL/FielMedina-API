from modeltranslation.translator import register, TranslationOptions
from .models import (
    Location,
    LocationCategory,
    Event,
    EventCategory,
    Tip,
    Hiking,
    PublicTransportType,
    MerchantCategory, Merchant, MerchantProduct,
    OfflineCity
)


@register(Location)
class LocationTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "story",
    )


@register(LocationCategory)
class LocationCategoryTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Event)
class EventTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
    )


@register(EventCategory)
class EventCategoryTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Tip)
class TipTranslationOptions(TranslationOptions):
    fields = ("description",)


@register(Hiking)
class HikingTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
    )


@register(PublicTransportType)
class PublicTransportTypeTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(MerchantCategory)
class MerchantCategoryTranslationOptions(TranslationOptions):
    fields = ("name",)

@register(Merchant)
class MerchantTranslationOptions(TranslationOptions):
    fields = ("name", "description", "address")

@register(MerchantProduct)
class MerchantProductTranslationOptions(TranslationOptions):
    fields = ("name",)

@register(OfflineCity)
class OfflineCityTranslationOptions(TranslationOptions):
    fields = ("name",)