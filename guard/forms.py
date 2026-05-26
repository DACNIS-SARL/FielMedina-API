from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from tinymce.widgets import TinyMCE

from .models import (
    Location,
    ImageLocation,
    Event,
    ImageEvent,
    Tip,
    Hiking,
    HikingLocation,
    ImageHiking,
    Ad,
    ImageAd,
    PublicTransport,
    PublicTransportTime,
    Partner,
    Sponsor,
    Merchant,
    MerchantCategory,
    MerchantImage,
    MerchantProduct,
)


class FlowbiteFormMixin:
    input_class = (
        "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg "
        "focus:ring-blue-600 focus:border-blue-600 block w-full p-2.5 "
        "dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 "
        "dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
    )

    file_input_class = (
        "block w-full text-sm text-gray-900 border border-gray-300 rounded-lg "
        "cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none "
        "dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"
    )

    checkbox_class = "w-5 h-5 border border-default-medium rounded bg-neutral-secondary-medium focus:ring-2 focus:ring-brand-soft"
    radio_class = "w-4 h-4 text-blue-600 focus:ring-2 focus:ring-blue-500"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            widget = field.widget
            classes = widget.attrs.get("class", "")

            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs["class"] = f"{classes} {self.checkbox_class}".strip()
            elif isinstance(widget, (forms.RadioSelect,)):
                widget.attrs["class"] = f"{classes} {self.radio_class}".strip()
            elif isinstance(widget, (forms.FileInput,)):
                widget.attrs["class"] = f"{classes} {self.file_input_class}".strip()
            else:
                widget.attrs["class"] = f"{classes} {self.input_class}".strip()

            widget.attrs.setdefault("id", f"id_{name}")


class LocationForm(FlowbiteFormMixin, forms.ModelForm):
    name_en = forms.CharField(
        label=_("Name (English)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter location name in English"),
            }
        ),
        error_messages={
            "required": _("Please enter the name in English."),
        },
    )
    name_fr = forms.CharField(
        label=_("Name (French)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter location name in French"),
            }
        ),
        error_messages={
            "required": _("Please enter the name in French."),
        },
    )

    story_en = forms.CharField(
        label=_("Story (English)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
        error_messages={
            "required": _("Please enter the story in English."),
        },
    )
    story_fr = forms.CharField(
        label=_("Story (French)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
        error_messages={
            "required": _("Please enter the story in French."),
        },
    )

    class Meta:
        model = Location
        fields = [
            "name_en",
            "name_fr",
            "category",
            "country",
            "city",
            "latitude",
            "longitude",
            "story_en",
            "story_fr",
            "openFrom",
            "openTo",
            "admissionFee",
            "is_active_ads",
            "closedDays",
            "voiceover_en",
            "voiceover_fr",
        ]
        widgets = {
            "category": forms.Select(
                attrs={
                    "placeholder": _("Select location category"),
                    "required": True,
                }
            ),
            "country": forms.Select(
                attrs={
                    "placeholder": _("Select location country"),
                    "required": True,
                }
            ),
            "city": forms.Select(
                attrs={
                    "placeholder": _("Select location city"),
                    "required": True,
                }
            ),
            "latitude": forms.NumberInput(
                attrs={
                    "placeholder": _("e.g., 36.8065"),
                    "step": "0.000001",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "placeholder": _("e.g., 10.1815"),
                    "step": "0.000001",
                }
            ),
            "openFrom": forms.TimeInput(
                attrs={
                    "type": "time",
                    "placeholder": _("Opening time"),
                }
            ),
            "openTo": forms.TimeInput(
                attrs={
                    "type": "time",
                    "placeholder": _("Closing time"),
                }
            ),
            "admissionFee": forms.NumberInput(
                attrs={
                    "placeholder": _("e.g., 5.00"),
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "is_active_ads": forms.CheckboxInput(),
            "closedDays": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "w-5 h-5 border border-default-medium rounded bg-neutral-secondary-medium focus:ring-2 focus:ring-brand-soft",
                }
            ),
            "voiceover_en": forms.FileInput(
                attrs={
                    "accept": ".aac,audio/aac,audio/x-aac",
                }
            ),
            "voiceover_fr": forms.FileInput(
                attrs={
                    "accept": ".aac,audio/aac,audio/x-aac",
                }
            ),
        }

        error_messages = {
            "category": {
                "required": _("Please select a category."),
            },
            "country": {
                "required": _("Please select a country."),
            },
            "city": {
                "required": _("Please select a city."),
            },
        }

        help_texts = {
            "latitude": _("Latitude in decimal degrees (e.g., 36.8065)"),
            "longitude": _("Longitude in decimal degrees (e.g., 10.1815)"),
            "openFrom": _("Leave empty if location is always open"),
            "openTo": _("Leave empty if location is always open"),
            "admissionFee": _("Leave empty if admission is free"),
            "is_active_ads": _("Enable advertisements for this location"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "category" in self.fields:
            self.fields["category"].required = True
        if "country" in self.fields:
            self.fields["country"].required = True
        if "city" in self.fields:
            self.fields["city"].required = True

        if "city" in self.fields:
            from cities_light.models import City

            if self.instance and self.instance.country:
                self.fields["city"].queryset = City.objects.filter(
                    country=self.instance.country
                )
            else:
                self.fields["city"].queryset = City.objects.all()

    def clean(self):
        cleaned_data = super().clean()

        # Check required multilingual fields and add non-field errors so they appear at top
        errors = []

        if not cleaned_data.get("name_en"):
            errors.append(_("Please enter the name in English."))
            # Remove field-specific error to avoid duplication
            if "name_en" in self.errors:
                del self.errors["name_en"]

        if not cleaned_data.get("name_fr"):
            errors.append(_("Please enter the name in French."))
            if "name_fr" in self.errors:
                del self.errors["name_fr"]

        if not cleaned_data.get("story_en"):
            errors.append(_("Please enter the story in English."))
            if "story_en" in self.errors:
                del self.errors["story_en"]

        if not cleaned_data.get("story_fr"):
            errors.append(_("Please enter the story in French."))
            if "story_fr" in self.errors:
                del self.errors["story_fr"]

        # Add all errors as non-field errors
        for error in errors:
            self.add_error(None, error)

        # Existing validation
        open_from = cleaned_data.get("openFrom")
        open_to = cleaned_data.get("openTo")

        if open_from and open_to and open_from >= open_to:
            self.add_error("openTo", _("Opening time must be before closing time."))

        return cleaned_data

    def _clean_voiceover(self, field_name):
        voiceover = self.cleaned_data.get(field_name)
        if voiceover:
            import os
            ext = os.path.splitext(voiceover.name)[1].lower()
            if ext != '.aac':
                raise forms.ValidationError(_("Only AAC audio format is allowed."))
        return voiceover

    def clean_voiceover_en(self):
        return self._clean_voiceover("voiceover_en")

    def clean_voiceover_fr(self):
        return self._clean_voiceover("voiceover_fr")


class ImageLocationForm(forms.ModelForm):
    class Meta:
        model = ImageLocation
        fields = ["image"]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400",
                    "accept": "image/*",
                }
            )
        }


ImageLocationFormSet = inlineformset_factory(
    Location,
    ImageLocation,
    form=ImageLocationForm,
    extra=1,
    can_delete=True,
    max_num=10,
)


class EventForm(FlowbiteFormMixin, forms.ModelForm):
    name_en = forms.CharField(
        label=_("Name (English)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter event name in English"),
            }
        ),
        error_messages={
            "required": _("Please enter the name in English."),
        },
    )
    name_fr = forms.CharField(
        label=_("Name (French)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter event name in French"),
            }
        ),
        error_messages={
            "required": _("Please enter the name in French."),
        },
    )

    description_en = forms.CharField(
        label=_("Description (English)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
        error_messages={
            "required": _("Please enter the description in English."),
        },
    )
    description_fr = forms.CharField(
        label=_("Description (French)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
        error_messages={
            "required": _("Please enter the description in French."),
        },
    )

    link = forms.URLField(
        label=_("Destination Link"),
        required=True,
        widget=forms.URLInput(
            attrs={
                "placeholder": "https://example.com",
            }
        ),
        help_text=_("The destination URL for this event."),
    )

    class Meta:
        model = Event
        fields = [
            "name_en",
            "name_fr",
            "description_en",
            "description_fr",
            "location",
            "city",
            "category",
            "startDate",
            "endDate",
            "time",
            "price",
            "link",
            "boost",
        ]
        widgets = {
            "location": forms.Select(
                attrs={
                    "placeholder": _("Select event location"),
                }
            ),
            "city": forms.Select(
                attrs={
                    "placeholder": _("Select city"),
                }
            ),
            "category": forms.Select(
                attrs={
                    "placeholder": _("Select event category"),
                }
            ),
            "startDate": forms.DateInput(
                attrs={
                    "type": "date",
                    "placeholder": _("Select event start date"),
                }
            ),
            "endDate": forms.DateInput(
                attrs={
                    "type": "date",
                    "placeholder": _("Select event end date"),
                }
            ),
            "time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "placeholder": _("Select event time"),
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "placeholder": _("Enter event price"),
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "link": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                }
            ),
            "boost": forms.CheckboxInput(),
        }

    def clean(self):
        cleaned_data = super().clean()

        # Check required multilingual fields and add non-field errors so they appear at top
        errors = []

        if not cleaned_data.get("name_en"):
            errors.append(_("Please enter the name in English."))
            # Remove field-specific error to avoid duplication
            if "name_en" in self.errors:
                del self.errors["name_en"]

        if not cleaned_data.get("name_fr"):
            errors.append(_("Please enter the name in French."))
            if "name_fr" in self.errors:
                del self.errors["name_fr"]

        if not cleaned_data.get("description_en"):
            errors.append(_("Please enter the description in English."))
            if "description_en" in self.errors:
                del self.errors["description_en"]

        if not cleaned_data.get("description_fr"):
            errors.append(_("Please enter the description in French."))
            if "description_fr" in self.errors:
                del self.errors["description_fr"]

        # Add all errors as non-field errors
        for error in errors:
            self.add_error(None, error)

        return cleaned_data

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if "city" in self.fields:
            self.fields["city"].required = True

        # Only staff can see/edit boost. If not staff, remove it so it's not reset to False.
        if user and not (user.is_staff or user.is_superuser):
            if "boost" in self.fields:
                del self.fields["boost"]

        if self.instance and self.instance.pk:
            pass


class ImageEventForm(forms.ModelForm):
    class Meta:
        model = ImageEvent
        fields = ["image"]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400",
                    "accept": "image/*",
                }
            )
        }


ImageEventFormSet = inlineformset_factory(
    Event,
    ImageEvent,
    form=ImageEventForm,
    extra=1,
    can_delete=True,
    max_num=10,
)


class TipForm(FlowbiteFormMixin, forms.ModelForm):
    description_en = forms.CharField(
        label=_("Description (English)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
    )
    description_fr = forms.CharField(
        label=_("Description (French)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
    )

    class Meta:
        model = Tip
        fields = ["city", "description_en", "description_fr"]
        widgets = {
            "city": forms.Select(
                attrs={
                    "placeholder": _("Select city"),
                    "required": True,
                }
            ),
        }
        error_messages = {
            "city": {
                "required": _("Please select a city."),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "city" in self.fields:
            self.fields["city"].required = True

    def clean(self):
        cleaned_data = super().clean()
        required_fields = {
            "description_en": _("Description (English) is required."),
            "description_fr": _("Description (French) is required."),
        }

        for field, error in required_fields.items():
            if not cleaned_data.get(field):
                self.add_error(None, error)
                if field in self._errors:
                    del self._errors[field]

        return cleaned_data


class HikingForm(FlowbiteFormMixin, forms.ModelForm):
    name_en = forms.CharField(
        label=_("Name (English)"),
        required=True,
        error_messages={
            "required": _("Please enter the name in English."),
        },
    )
    name_fr = forms.CharField(
        label=_("Name (French)"),
        required=True,
        error_messages={
            "required": _("Please enter the name in French."),
        },
    )
    description_en = forms.CharField(
        label=_("Description (English)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
        error_messages={
            "required": _("Please enter the description in English."),
        },
    )
    description_fr = forms.CharField(
        label=_("Description (French)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
        error_messages={
            "required": _("Please enter the description in French."),
        },
    )

    class Meta:
        model = Hiking
        fields = [
            "name_en",
            "name_fr",
            "description_en",
            "description_fr",
            "city",
            "latitude",
            "longitude",
        ]
        widgets = {
            "city": forms.Select(
                attrs={
                    "placeholder": _("Select city"),
                    "class": "block w-full px-3 py-2.5 bg-neutral-secondary-medium border border-default-medium text-heading text-sm rounded-base focus:ring-brand focus:border-brand shadow-xs placeholder:text-body",
                    "required": True,
                }
            ),
            "latitude": forms.NumberInput(
                attrs={
                    "placeholder": _("e.g., 36.8065"),
                    "step": "0.000001",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "placeholder": _("e.g., 10.1815"),
                    "step": "0.000001",
                }
            ),
        }
        error_messages = {
            "city": {
                "required": _("Please select a city."),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "city" in self.fields:
            self.fields["city"].required = True

    def clean(self):
        cleaned_data = super().clean()

        errors = []
        if not cleaned_data.get("name_en"):
            errors.append(_("Please enter the name in English."))
            if "name_en" in self.errors:
                del self.errors["name_en"]
        if not cleaned_data.get("name_fr"):
            errors.append(_("Please enter the name in French."))
            if "name_fr" in self.errors:
                del self.errors["name_fr"]
        if not cleaned_data.get("description_en"):
            errors.append(_("Please enter the description in English."))
            if "description_en" in self.errors:
                del self.errors["description_en"]
        if not cleaned_data.get("description_fr"):
            errors.append(_("Please enter the description in French."))
            if "description_fr" in self.errors:
                del self.errors["description_fr"]

        for error in errors:
            self.add_error(None, error)

        return cleaned_data


class HikingLocationForm(FlowbiteFormMixin, forms.ModelForm):
    class Meta:
        model = HikingLocation
        fields = ["location", "order"]
        widgets = {
            "location": forms.Select(
                attrs={
                    "class": "block w-full px-3 py-2.5 bg-neutral-secondary-medium border border-default-medium text-heading text-sm rounded-base focus:ring-brand focus:border-brand shadow-xs placeholder:text-body",
                    "placeholder": _("Select location"),
                }
            ),
            "order": forms.HiddenInput(),
        }


HikingLocationFormSet = inlineformset_factory(
    Hiking,
    HikingLocation,
    form=HikingLocationForm,
    extra=1,
    can_delete=True,
    fields=["location", "order"],
)


class ImageHikingForm(forms.ModelForm):
    class Meta:
        model = ImageHiking
        fields = ["image"]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400",
                    "accept": "image/*",
                }
            )
        }


ImageHikingFormSet = inlineformset_factory(
    Hiking,
    ImageHiking,
    form=ImageHikingForm,
    extra=1,
    can_delete=True,
    max_num=10,
)


class AdForm(FlowbiteFormMixin, forms.ModelForm):
    name = forms.CharField(
        label=_("Ad Name"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("e.g., Summer Campaign 2026"),
            }
        ),
        help_text=_("If empty, a name like 'ADS-XXXXXX' will be auto-generated."),
    )
    link = forms.URLField(
        label=_("Destination Link"),
        required=True,
        widget=forms.URLInput(
            attrs={
                "placeholder": "https://example.com",
            }
        ),
        help_text=_(
            "The destination URL for this ad. This will be tracked via Short.io."
        ),
    )

    class Meta:
        model = Ad
        fields = [
            "name",
            "country",
            "city",
            "image_mobile",
            "image_tablet",
            "link",
            "is_active",
        ]
        widgets = {
            "country": forms.Select(
                attrs={
                    "placeholder": _("Select country"),
                }
            ),
            "city": forms.Select(
                attrs={
                    "placeholder": _("Select city"),
                }
            ),
            "image_mobile": forms.FileInput(attrs={"accept": "image/*"}),
            "image_tablet": forms.FileInput(attrs={"accept": "image/*"}),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_active"].label = _("Active")

        if "country" in self.fields:
            self.fields["country"].required = True

        if "city" in self.fields:
            self.fields["city"].required = False  # Ads can be just country-level now

        # Enforce strict requirement for creation, overruling model's blank=True
        self.fields["image_mobile"].required = True
        self.fields["image_tablet"].required = True

        if self.instance and self.instance.pk:
            self.fields["image_mobile"].required = False
            self.fields["image_tablet"].required = False
            pass

    def clean_image_mobile(self):
        image = self.cleaned_data.get("image_mobile")
        if image:
            if hasattr(image, "image"):
                w, h = image.image.width, image.image.height
            else:
                from django.core.files.images import get_image_dimensions

                w, h = get_image_dimensions(image)

            if w != 320 or h != 50:
                raise forms.ValidationError(
                    _(
                        "Mobile image must be exactly 320x50 pixels. Uploaded: %(w)sx%(h)s"
                    )
                    % {"w": w, "h": h}
                )
        return image

    def clean_image_tablet(self):
        image = self.cleaned_data.get("image_tablet")
        if image:
            if hasattr(image, "image"):
                w, h = image.image.width, image.image.height
            else:
                from django.core.files.images import get_image_dimensions

                w, h = get_image_dimensions(image)

            if w != 728 or h != 90:
                raise forms.ValidationError(
                    _(
                        "Tablet image must be exactly 728x90 pixels. Uploaded: %(w)sx%(h)s"
                    )
                    % {"w": w, "h": h}
                )
        return image


ImageAdFormSet = inlineformset_factory(
    Ad,
    ImageAd,
    fields=["image"],
    extra=1,
    can_delete=True,
    max_num=5,
)


class PartnerForm(FlowbiteFormMixin, forms.ModelForm):
    class Meta:
        model = Partner
        fields = ["name", "image", "link"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("e.g., Partner name"),
                }
            ),
            "link": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "accept": "image/*",
                }
            ),
        }
        error_messages = {
            "name": {"required": _("Please enter a name.")},
            "image": {"required": _("Please upload an image (300x200).")},
            "link": {"required": _("Please provide a link.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "image" in self.fields:
            self.fields["image"].required = True
            if self.instance and self.instance.pk:
                self.fields["image"].required = False


class SponsorForm(FlowbiteFormMixin, forms.ModelForm):
    class Meta:
        model = Sponsor
        fields = ["name", "image", "link"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("e.g., Sponsor name"),
                }
            ),
            "link": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "accept": "image/*",
                }
            ),
        }
        error_messages = {
            "name": {"required": _("Please enter a name.")},
            "image": {"required": _("Please upload an image (300x200).")},
            "link": {"required": _("Please provide a link.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "image" in self.fields:
            self.fields["image"].required = True
            if self.instance and self.instance.pk:
                self.fields["image"].required = False


class PublicTransportForm(FlowbiteFormMixin, forms.ModelForm):
    class Meta:
        model = PublicTransport
        fields = ("publicTransportType", "city", "fromRegion", "toRegion", "busNumber")
        widgets = {
            "publicTransportType": forms.Select(
                attrs={
                    "placeholder": _("Select transport type"),
                    "required": True,
                }
            ),
            "city": forms.Select(
                attrs={
                    "placeholder": _("Select city"),
                    "required": True,
                }
            ),
            "fromRegion": forms.Select(
                attrs={
                    "placeholder": _("Select departure region"),
                }
            ),
            "toRegion": forms.Select(
                attrs={
                    "placeholder": _("Select arrival region"),
                }
            ),
            "busNumber": forms.TextInput(
                attrs={
                    "placeholder": _("e.g., Line 32 or Bus 105"),
                }
            ),
        }
        error_messages = {
            "publicTransportType": {
                "required": _("Please select a transport type."),
            },
            "city": {
                "required": _("Please select a city."),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "publicTransportType" in self.fields:
            self.fields["publicTransportType"].required = True
        if "city" in self.fields:
            self.fields["city"].required = True

        # Filter subregions based on city if editing
        if "fromRegion" in self.fields and "toRegion" in self.fields:
            from cities_light.models import SubRegion

            if self.instance and self.instance.pk and self.instance.city:
                region = self.instance.city.region
                self.fields["fromRegion"].queryset = SubRegion.objects.filter(
                    region=region
                )
                self.fields["toRegion"].queryset = SubRegion.objects.filter(
                    region=region
                )
            else:
                self.fields["fromRegion"].queryset = SubRegion.objects.none()
                self.fields["toRegion"].queryset = SubRegion.objects.none()


class PublicTransportTimeForm(FlowbiteFormMixin, forms.ModelForm):
    class Meta:
        model = PublicTransportTime
        fields = [
            "time",
        ]
        widgets = {
            "time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "placeholder": _("Select time"),
                }
            ),
        }


PublicTransportFormSet = inlineformset_factory(
    PublicTransport,
    PublicTransportTime,
    form=PublicTransportTimeForm,
    extra=1,
    can_delete=True,
    max_num=20,
)


class MerchantCategoryForm(FlowbiteFormMixin, forms.ModelForm):
    name_en = forms.CharField(
        label=_("Name (English)"),
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Category name in English")}),
    )
    name_fr = forms.CharField(
        label=_("Name (French)"),
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Category name in French")}),
    )
    icon = forms.CharField(
        label=_("Icon"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("SF Symbol (e.g. cart, bag)")}),
    )

    class Meta:
        model = MerchantCategory
        fields = ["name_en", "name_fr", "icon"]

    def clean(self):
        cleaned_data = super().clean()
        errors = []
        if not cleaned_data.get("name_en"):
            errors.append(_("Please enter the name in English."))
        if not cleaned_data.get("name_fr"):
            errors.append(_("Please enter the name in French."))
        for error in errors:
            self.add_error(None, error)
        return cleaned_data


class MerchantForm(FlowbiteFormMixin, forms.ModelForm):
    name_en = forms.CharField(
        label=_("Name (English)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Merchant name in English")}),
    )
    name_fr = forms.CharField(
        label=_("Name (French)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Merchant name in French")}),
    )

    description_en = forms.CharField(
        label=_("Description (English)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
    )
    description_fr = forms.CharField(
        label=_("Description (French)"),
        required=True,
        widget=TinyMCE(attrs={"cols": 80, "rows": 30}),
    )

    address_en = forms.CharField(
        label=_("Address (English)"),
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Address in English")}),
    )
    address_fr = forms.CharField(
        label=_("Address (French)"),
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Address in French")}),
    )

    class Meta:
        model = Merchant
        fields = [
            "name_en",
            "name_fr",
            "description_en",
            "description_fr",
            "category",
            "city",
            "latitude",
            "longitude",
            "address_en",
            "address_fr",
            "phone",
            "website",
            "price_range",
            "open_from",
            "open_to",
            "cover",
            "is_active",
            "is_featured",
            "contract_status",
            "contract_start",
            "contract_end",
            "contract_notes",
        ]
        widgets = {
            "category": forms.Select(attrs={"required": True}),
            "city": forms.Select(attrs={"required": True}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "placeholder": "36.8065"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "placeholder": "10.1815"}),
            "phone": forms.TextInput(attrs={"placeholder": "+1234567890"}),
            "website": forms.URLInput(attrs={"placeholder": "https://example.com"}),
            "price_range": forms.Select(),
            "open_from": forms.TimeInput(attrs={"type": "time"}),
            "open_to": forms.TimeInput(attrs={"type": "time"}),
            "cover": forms.FileInput(attrs={"accept": "image/*"}),
            "is_active": forms.CheckboxInput(),
            "is_featured": forms.CheckboxInput(),
            "contract_status": forms.Select(),
            "contract_start": forms.DateInput(attrs={"type": "date"}),
            "contract_end": forms.DateInput(attrs={"type": "date"}),
            "contract_notes": forms.Textarea(attrs={"rows": 4, "placeholder": _("Internal contract notes")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "category" in self.fields:
            self.fields["category"].required = True
        if "city" in self.fields:
            self.fields["city"].required = True

    def clean(self):
        cleaned_data = super().clean()
        errors = []
        if not cleaned_data.get("name_en"):
            errors.append(_("Please enter the name in English."))
            if "name_en" in self.errors:
                del self.errors["name_en"]

        if not cleaned_data.get("name_fr"):
            errors.append(_("Please enter the name in French."))
            if "name_fr" in self.errors:
                del self.errors["name_fr"]

        if not cleaned_data.get("description_en"):
            errors.append(_("Please enter the description in English."))
            if "description_en" in self.errors:
                del self.errors["description_en"]

        if not cleaned_data.get("description_fr"):
            errors.append(_("Please enter the description in French."))
            if "description_fr" in self.errors:
                del self.errors["description_fr"]

        for error in errors:
            self.add_error(None, error)

        # Time range validation
        open_from = cleaned_data.get("open_from")
        open_to = cleaned_data.get("open_to")
        if open_from and open_to and open_from >= open_to:
            self.add_error("open_to", _("Opening time must be before closing time."))

        # Contract date validation
        contract_start = cleaned_data.get("contract_start")
        contract_end = cleaned_data.get("contract_end")
        if contract_start and contract_end and contract_start >= contract_end:
            self.add_error("contract_end", _("Contract start date must be before end date."))

        return cleaned_data


class MerchantProductForm(FlowbiteFormMixin, forms.ModelForm):
    name_en = forms.CharField(
        label=_("Product Name (English)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Product name in English")}),
    )
    name_fr = forms.CharField(
        label=_("Product Name (French)"),
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Product name in French")}),
    )

    class Meta:
        model = MerchantProduct
        fields = ["name_en", "name_fr", "price", "image"]
        widgets = {
            "price": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "image": forms.FileInput(attrs={"accept": "image/*", "class": "block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        errors = []
        if not cleaned_data.get("name_en"):
            errors.append(_("Please enter product name in English."))
        if not cleaned_data.get("name_fr"):
            errors.append(_("Please enter product name in French."))
        for error in errors:
            self.add_error(None, error)
        return cleaned_data


MerchantProductFormSet = inlineformset_factory(
    Merchant,
    MerchantProduct,
    form=MerchantProductForm,
    extra=1,
    can_delete=True,
    max_num=20,
)


class MerchantImageForm(forms.ModelForm):
    class Meta:
        model = MerchantImage
        fields = ["image"]
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*", "class": "block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"}),
        }


MerchantImageFormSet = inlineformset_factory(
    Merchant,
    MerchantImage,
    form=MerchantImageForm,
    extra=1,
    can_delete=True,
    max_num=10,
)

