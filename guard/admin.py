from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    Location,
    ImageLocation,
    ImageEvent,
    LocationCategory,
    Event,
    EventCategory,
    Tip,
    Hiking,
    ImageHiking,
    Ad,
    HikingLocation,
    PublicTransport,
    PublicTransportTime,
    PublicTransportType,
    Partner,
    Sponsor,
)
from modeltranslation.admin import TranslationAdmin


class ImageInline(admin.TabularInline):
    model = ImageLocation
    extra = 1


@admin.register(Location)
class LocationAdmin(TranslationAdmin):
    list_display = ["name", "country", "city", "category", "created_at"]
    list_filter = ["country", "is_active_ads", "category"]
    search_fields = ["name", "story", "city__name", "country__name", "category__name"]
    inlines = [ImageInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("country", "city", "is_active_ads", "category")},
        ),
        (
            _("Location Details"),
            {
                "fields": (
                    "name",
                    "latitude",
                    "longitude",
                    "openFrom",
                    "openTo",
                    "closedDays",
                    "admissionFee",
                    "story",
                )
            },
        ),
        (
            _("Voiceover Audio"),
            {
                "fields": ("voiceover_en", "voiceover_fr"),
                "description": _("Optional audio voiceovers for this location (AAC format only)"),
            },
        ),
    )


@admin.register(LocationCategory)
class LocationCategoryAdmin(TranslationAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


class ImageEventInline(admin.TabularInline):
    model = ImageEvent
    extra = 1


@admin.register(Event)
class EventAdmin(TranslationAdmin):
    list_display = [
        "name",
        "location",
        "client",
        "startDate",
        "endDate",
        "price",
        "boost",
        "created_at",
    ]
    list_filter = ["startDate", "endDate", "location", "boost"]
    search_fields = ["name", "description", "location__name", "client__user__username"]
    inlines = [ImageEventInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "client", "location", "category")},
        ),
        (
            _("Event Schedule"),
            {
                "fields": (
                    "startDate",
                    "endDate",
                    "time",
                    "link",
                    "short_link",
                    "short_id",
                )
            },
        ),
        (_("Details"), {"fields": ("price", "description", "boost")}),
    )


@admin.register(EventCategory)
class EventCategoryAdmin(TranslationAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Tip)
class TipAdmin(TranslationAdmin):
    list_display = ["city", "created_at"]
    list_filter = ["city"]
    search_fields = ["city__name"]


class HikingLocationInline(admin.TabularInline):
    model = HikingLocation
    extra = 1


class ImageHikingInline(admin.TabularInline):
    model = ImageHiking
    extra = 1


@admin.register(Hiking)
class HikingAdmin(TranslationAdmin):
    list_display = [
        "city",
        "name",
    ]
    list_filter = ["city", "name", "locations"]
    search_fields = [
        "name",
        "description",
    ]
    inlines = [HikingLocationInline, ImageHikingInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "city", "description")},
        ),
        (
            _("Geolocation"),
            {"fields": ("latitude", "longitude")},
        ),
    )


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "client",
        "clicks",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "client"]
    search_fields = ["name", "link", "client__user__username"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "client", "is_active")},
        ),
        (
            _("Ad Images"),
            {"fields": ("image_mobile", "image_tablet")},
        ),
        (
            _("Link Information"),
            {
                "fields": (
                    "link",
                    "short_link",
                    "short_id",
                )
            },
        ),
        (_("Statistics"), {"fields": ("clicks",)}),
    )


@admin.register(PublicTransportType)
class PublicTransportTypeAdmin(TranslationAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class PublicTransportTimeInline(admin.TabularInline):
    model = PublicTransportTime
    extra = 1


@admin.register(PublicTransport)
class PublicTransportAdmin(admin.ModelAdmin):
    list_display = [
        "city",
        "publicTransportType",
        "fromRegion",
        "toRegion",
    ]
    list_filter = [
        "city",
        "publicTransportType",
    ]
    search_fields = [
        "city__name",
    ]
    inlines = [PublicTransportTimeInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("publicTransportType", "city", "fromRegion", "toRegion")},
        ),
    )

    class Media:
        js = ("admin/js/public_transport_admin.js",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ["fromRegion", "toRegion"]:
            # If we are editing an existing object, filter subregions by city
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                try:
                    obj = self.get_object(request, obj_id)
                    if obj and obj.city:
                        from cities_light.models import SubRegion

                        kwargs["queryset"] = SubRegion.objects.filter(
                            region=obj.city.region
                        )
                except Exception:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "image", "link"]
    search_fields = ["name"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "image", "link")},
        ),
    )


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ["name", "image", "link"]
    search_fields = ["name"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "image", "link")},
        ),
    )
