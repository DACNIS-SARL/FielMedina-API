import os
import uuid
from io import BytesIO


from django.db import models
from django.db.models.signals import post_delete
from django.db.models import FileField
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from tinymce.models import HTMLField
from django.core.files.uploadedfile import UploadedFile
from django.core.files.base import ContentFile
from shared.models import OptimizedImageModel
from shared.utils import optimize_image
from shared.models import UserProfile
from PIL import Image as PilImage
from PIL import ImageOps


def location_image_path(instance, filename):
    name, ext = os.path.splitext(filename)
    return f"locations/{instance.location.id}/{name}.jpg"


def location_voiceover_path(instance, filename):
    name, ext = os.path.splitext(filename)
    return f"locations/voiceovers/{instance.id}/{name}{ext}"


def event_image_path(instance, filename):
    name, ext = os.path.splitext(filename)
    return f"events/{instance.event.id}/{name}.jpg"


def hiking_image_path(instance, filename):
    name, ext = os.path.splitext(filename)
    return f"hikings/{instance.hiking.id}/{name}.jpg"


def ad_image_path(instance, filename):
    name, ext = os.path.splitext(filename)
    return f"ads/{instance.ad.id}/{name}.jpg"


class ImageAd(OptimizedImageModel):
    ad = models.ForeignKey("guard.Ad", on_delete=models.CASCADE, related_name="images")

    class Meta:
        verbose_name = _("Ad Image")
        verbose_name_plural = _("Ad Images")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field("image").upload_to = ad_image_path
        self._meta.get_field("image_mobile").upload_to = ad_image_path


class ImageHiking(OptimizedImageModel):
    hiking = models.ForeignKey(
        "guard.Hiking", on_delete=models.CASCADE, related_name="images"
    )

    class Meta:
        verbose_name = _("Hiking Image")
        verbose_name_plural = _("Hiking Images")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field("image").upload_to = hiking_image_path
        self._meta.get_field("image_mobile").upload_to = hiking_image_path


class ImageLocation(OptimizedImageModel):
    location = models.ForeignKey(
        "guard.Location", on_delete=models.CASCADE, related_name="images"
    )

    class Meta:
        verbose_name = _("Location Image")
        verbose_name_plural = _("Location Images")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field("image").upload_to = location_image_path
        self._meta.get_field("image_mobile").upload_to = location_image_path


class ImageEvent(OptimizedImageModel):
    event = models.ForeignKey(
        "guard.Event", on_delete=models.CASCADE, related_name="images"
    )

    class Meta:
        verbose_name = _("Event Image")
        verbose_name_plural = _("Event Images")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field("image").upload_to = event_image_path
        self._meta.get_field("image_mobile").upload_to = event_image_path


class LocationCategory(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Location Category")
        verbose_name_plural = _("Location Categories")

    def __str__(self):
        return self.name


class WeekdayChoices(models.IntegerChoices):
    SUNDAY = 1, _("Sunday")
    MONDAY = 2, _("Monday")
    TUESDAY = 3, _("Tuesday")
    WEDNESDAY = 4, _("Wednesday")
    THURSDAY = 5, _("Thursday")
    FRIDAY = 6, _("Friday")
    SATURDAY = 7, _("Saturday")


class Weekday(models.Model):
    day = models.IntegerField(
        choices=WeekdayChoices.choices, unique=True, verbose_name=_("Day")
    )

    class Meta:
        verbose_name = _("Weekday")
        verbose_name_plural = _("Weekdays")
        ordering = ["day"]

    def __str__(self):
        return self.get_day_display()


class Location(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(
        LocationCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locations",
        verbose_name=_("Category"),
    )
    name = models.CharField(max_length=255)
    country = models.ForeignKey(
        "cities_light.Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locations",
        verbose_name=_("Country"),
    )
    city = models.ForeignKey(
        "cities_light.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locations",
        verbose_name=_("City"),
    )
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active_ads = models.BooleanField(default=False, verbose_name=_("Active Ads"))
    story = HTMLField(verbose_name=_("Story"))
    openFrom = models.TimeField(
        verbose_name=_("Open From"),
        blank=True,
        null=True,
        help_text=_("Add opening hours if the location is open from a specific time"),
    )
    openTo = models.TimeField(
        verbose_name=_("Open To"),
        blank=True,
        null=True,
        help_text=_("Add opening hours if the location is open to a specific time"),
    )
    admissionFee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Admission Fee"),
        blank=True,
        null=True,
        help_text=_("Add admission fee if the location has a specific admission fee"),
    )
    closedDays = models.ManyToManyField(
        "Weekday",
        verbose_name=_("Closed Days"),
        blank=True,
        related_name="locations",
    )
    voiceover_en = models.FileField(
        upload_to=location_voiceover_path,
        verbose_name=_("Voiceover (English)"),
        blank=True,
        null=True,
        help_text=_("Upload an audio voiceover in English (AAC format only)"),
    )
    voiceover_fr = models.FileField(
        upload_to=location_voiceover_path,
        verbose_name=_("Voiceover (French)"),
        blank=True,
        null=True,
        help_text=_("Upload an audio voiceover in French (AAC format only)"),
    )

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")

    def __str__(self):
        return self.name


class HikingLocation(models.Model):
    hiking = models.ForeignKey("Hiking", on_delete=models.CASCADE)
    location = models.ForeignKey("Location", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        unique_together = ["hiking", "location"]

    def __str__(self):
        return f"{self.hiking.name} - {self.location.name}"


class Hiking(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    city = models.ForeignKey(
        "cities_light.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hikings",
        verbose_name=_("Cities"),
    )
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"))

    locations = models.ManyToManyField(
        "Location", through="HikingLocation", verbose_name=_("Location")
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        verbose_name = _("Hiking")
        verbose_name_plural = _("Hikings")

    def __str__(self):
        return self.name


class EventCategory(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Event Category")
        verbose_name_plural = _("Event Categories")

    def __str__(self):
        return self.name


class Event(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    client = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        verbose_name=_("Client"),
    )
    city = models.ForeignKey(
        "cities_light.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        verbose_name=_("City"),
    )
    category = models.ForeignKey(
        EventCategory,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Category"),
    )
    name = models.CharField(max_length=255)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        verbose_name=_("Location"),
    )
    startDate = models.DateField(verbose_name=_("Start Date"))
    endDate = models.DateField(verbose_name=_("End Date"))
    time = models.TimeField(verbose_name=_("Time"))
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Price")
    )
    link = models.URLField(verbose_name=_("The link to subscribe"))
    short_link = models.URLField(blank=True, null=True)
    short_id = models.CharField(max_length=50, blank=True, null=True)
    description = HTMLField(verbose_name=_("Description"))
    boost = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")

    def __str__(self):
        return self.name


class Tip(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    city = models.ForeignKey(
        "cities_light.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tips",
        verbose_name=_("Cities"),
    )
    description = HTMLField()

    class Meta:
        verbose_name = _("Tip")
        verbose_name_plural = _("Tips")

    def __str__(self):
        return self.city.name


class Ad(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(
        max_length=255, verbose_name=_("Add a name"), blank=True, null=True
    )
    country = models.ForeignKey(
        "cities_light.Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ads",
        verbose_name=_("Country"),
    )
    city = models.ForeignKey(
        "cities_light.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ads",
        verbose_name=_("City"),
    )
    client = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ads",
        verbose_name=_("Client"),
    )
    image_mobile = models.ImageField(
        upload_to="ads/mobile/",
        help_text=_("Size: 320x50 pixels"),
        verbose_name=_("Mobile Image (320x50)"),
        null=True,
        blank=True,
    )
    image_tablet = models.ImageField(
        upload_to="ads/tablet/",
        help_text=_("Size: 728x90 pixels"),
        verbose_name=_("Tablet Image (728x90)"),
        null=True,
        blank=True,
    )
    link = models.URLField()
    short_link = models.URLField(blank=True, null=True)
    short_id = models.CharField(max_length=50, blank=True, null=True)
    clicks = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Ad")
        verbose_name_plural = _("Ads")

    def save(self, *args, **kwargs):
        if not self.name:
            ref = uuid.uuid4().hex[:6].upper()
            self.name = f"ADS-{ref}"

        for field_name in ["image_mobile", "image_tablet"]:
            field = getattr(self, field_name)
            if field and isinstance(field.file, UploadedFile):
                optimized = optimize_image(field)
                if optimized:
                    _, content = optimized
                    ext = ".jpg"
                    unique_filename = f"{uuid.uuid4()}{ext}"
                    content.name = unique_filename
                    setattr(self, field_name, content)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.link


@receiver(post_delete, sender=Ad)
def cleanup_ad_images(sender, instance, **kwargs):
    """
    Delete image files from filesystem when Ad object is deleted.
    """
    for field_name in ["image_mobile", "image_tablet"]:
        field = getattr(instance, field_name)
        if field and field.name:
            try:
                if os.path.isfile(field.path):
                    os.remove(field.path)
            except Exception:
                pass


@receiver(post_delete, sender=Location)
def cleanup_location_voiceovers(sender, instance, **kwargs):
    """
    Delete voiceover files from filesystem when Location is deleted.
    """
    for field_name in ["voiceover_en", "voiceover_fr"]:
        field = getattr(instance, field_name, None)
        if field and field.name:
            try:
                if os.path.isfile(field.path):
                    os.remove(field.path)
            except Exception:
                pass


class PublicTransportType(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = _("Public Transport Type")
        verbose_name_plural = _("Public Transport Types")

    def __str__(self):
        return self.name


class PublicTransport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    publicTransportType = models.ForeignKey(
        PublicTransportType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="public_transports",
        verbose_name=_("Public Transport Type"),
    )

    city = models.ForeignKey(
        "cities_light.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publicTransports",
        verbose_name=_("City"),
    )

    fromRegion = models.ForeignKey(
        "cities_light.SubRegion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publicTransportsFromRegion",
        verbose_name=_("From region"),
    )
    toRegion = models.ForeignKey(
        "cities_light.SubRegion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publicTransportsToRegion",
        verbose_name=_("To region"),
    )
    busNumber = models.CharField(max_length=255, verbose_name=_("Bus number"))

    class Meta:
        verbose_name = _("Public Transport")
        verbose_name_plural = _("Public Transports")

    def __str__(self):
        return self.city.name


class PublicTransportTime(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    publicTransport = models.ForeignKey(
        PublicTransport,
        on_delete=models.CASCADE,
        related_name="publicTransportTimes",
        verbose_name=_("Public Transport"),
    )
    time = models.TimeField(verbose_name=_("Time"))

    class Meta:
        verbose_name = _("Public Transport Time")
        verbose_name_plural = _("Public Transport Times")

    def __str__(self):
        return self.publicTransport.city.name


def resize_to_fixed(image_field, size=(300, 200)):
    """
    Resize and center-crop an uploaded image to a fixed size, returning a JPEG ContentFile.
    """
    if not image_field:
        return None

    try:
        img = PilImage.open(image_field)
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Fit and center-crop to target size
        img = ImageOps.fit(img, size, PilImage.Resampling.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=80, optimize=True)
        buffer.seek(0)

        base, _ = os.path.splitext(os.path.basename(image_field.name))
        new_name = f"{base}.jpg"
        return new_name, ContentFile(buffer.read())
    except Exception:
        return None


class Partner(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    image = models.ImageField(upload_to="partners/", verbose_name=_("Image"))
    link = models.URLField(verbose_name=_("Link"))

    class Meta:
        verbose_name = _("Partner")
        verbose_name_plural = _("Partners")

    def save(self, *args, **kwargs):
        # Resize image to 300x200 when a new upload is provided
        if self.image and isinstance(self.image.file, UploadedFile):
            processed = resize_to_fixed(self.image, size=(300, 200))
            if processed:
                name, content = processed
                content.name = name
                self.image = content
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Sponsor(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    image = models.ImageField(upload_to="sponsors/", verbose_name=_("Image"))
    link = models.URLField(verbose_name=_("Link"))

    class Meta:
        verbose_name = _("sponsor")
        verbose_name_plural = _("sponsors")

    def save(self, *args, **kwargs):
        if self.image and isinstance(self.image.file, UploadedFile):
            processed = resize_to_fixed(self.image, size=(300, 200))
            if processed:
                name, content = processed
                content.name = name
                self.image = content
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


@receiver(post_delete, sender=Partner)
@receiver(post_delete, sender=Sponsor)
def cleanup_all_files(sender, instance, **kwargs):
    for field in instance._meta.fields:
        if isinstance(field, FileField):
            file_field = getattr(instance, field.name)

            if file_field and file_field.name:
                # print(f"Attempting to delete file: {file_field.name}") # Debug line
                try:
                    file_field.storage.delete(file_field.name)
                    # print("Delete successful!")
                except Exception as e:
                    print(f"Error deleting file: {e}")
