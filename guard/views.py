# from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView,
    ListView,
    TemplateView,
    DetailView,
)
from django.urls import reverse_lazy

# from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import JsonResponse
from django.core.cache import cache


from .forms import (
    LocationForm,
    ImageLocationFormSet,
    EventForm,
    ImageEventFormSet,
    TipForm,
    HikingForm,
    HikingLocationFormSet,
    ImageHikingFormSet,
    AdForm,
    PublicTransportForm,
    PublicTransportFormSet,
    PartnerForm,
    SponsorForm,
    MerchantForm,
    MerchantCategoryForm,
    MerchantProductFormSet,
    MerchantImageFormSet,
    # ImageAdFormSet,
)

from .models import (
    LocationCategory,
    Location,
    Event,
    UserProfile,
    Tip,
    Hiking,
    Ad,
    PublicTransport,
    PublicTransportType,
    Partner,
    Sponsor,
    Merchant,
    MerchantCategory,
    MerchantImage,
    MerchantProduct,
    # ImageAd,
)

# from shared.translator import get_translator
from shared.short_io import ShortIOService


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "guard/views/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = ShortIOService()

        # Try to get stats from cache
        cache_key = "dashboard_analytics_stats"
        stats = cache.get(cache_key)

        if not stats:
            # Fetch active Ads and Events with short_id, filtered by user profile
            profile = self.request.user.profile
            ad_ids = list(
                Ad.objects.filter(
                    client=profile, is_active=True, short_id__isnull=False
                ).values_list("short_id", flat=True)
            )
            event_ids = list(
                Event.objects.filter(
                    client=profile, short_id__isnull=False
                ).values_list("short_id", flat=True)
            )

            # Aggregate stats for the last 7 days (week)
            period = "week"
            ads_stats = service.get_aggregated_link_statistics(ad_ids, period)
            events_stats = service.get_aggregated_link_statistics(event_ids, period)

            stats = {
                "ads": ads_stats,
                "events": events_stats,
            }
            # Cache for 15 minutes - include user ID in cache key for isolation
            cache.set(f"{cache_key}_{self.request.user.id}", stats, 60 * 15)

        context["stats"] = stats
        return context


class LocationsListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Location
    template_name = "guard/views/locations/list.html"
    context_object_name = "locations"
    # paginate_by = 10
    ordering = ["-created_at"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["location_categories"] = LocationCategory.objects.all()
        return context

    def test_func(self):
        return self.request.user.is_staff


class LocationCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Location
    template_name = "guard/views/locations/index.html"
    form_class = LocationForm
    success_url = reverse_lazy("guard:locationsList")
    success_message = _("Location created successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = ImageLocationFormSet(
                self.request.POST, self.request.FILES
            )
        else:
            context["image_formset"] = ImageLocationFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]

        if image_formset.is_valid():
            has_image = any(
                formset_form.cleaned_data.get("image")
                and not formset_form.cleaned_data.get("DELETE", False)
                for formset_form in image_formset
                if formset_form.cleaned_data
            )

            if not has_image:
                form.add_error(None, _("Please upload at least one image."))
                return self.form_invalid(form)

            self.object = form.save()
            image_formset.instance = self.object
            image_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class LocationUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Location
    template_name = "guard/views/locations/index.html"
    form_class = LocationForm
    success_url = reverse_lazy("guard:locationsList")
    success_message = _("Location updated successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = ImageLocationFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
        else:
            context["image_formset"] = ImageLocationFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]

        if image_formset.is_valid():
            existing_images = sum(
                1
                for formset_form in image_formset
                if formset_form.instance.pk
                and not formset_form.cleaned_data.get("DELETE", False)
            )
            new_images = sum(
                1
                for formset_form in image_formset
                if formset_form.cleaned_data.get("image")
                and not formset_form.instance.pk
            )

            if existing_images + new_images < 1:
                form.add_error(
                    None, _("Veuillez conserver ou télécharger au moins une image.")
                )
                return self.form_invalid(form)

            self.object = form.save()
            image_formset.instance = self.object
            image_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class LocationDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Location
    success_url = reverse_lazy("guard:locationsList")
    success_message = _("Unfortunately, this location has been deleted")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super(LocationDeleteView, self).delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


class SubscribersListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = UserProfile
    template_name = "guard/views/subscribers/list.html"
    context_object_name = "subscribers"
    # paginate_by = 10
    ordering = ["-created_at"]

    def test_func(self):
        return self.request.user.is_staff


class PublicTransportListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = PublicTransport
    template_name = "guard/views/publicTransports/list.html"
    context_object_name = "transports"
    # paginate_by = 10
    ordering = ["-created_at"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transport_types"] = PublicTransportType.objects.all()
        return context

    def test_func(self):
        return self.request.user.is_staff


class PublicTransportCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = PublicTransport
    template_name = "guard/views/publicTransports/index.html"
    form_class = PublicTransportForm
    success_url = reverse_lazy("guard:publicTransportsList")
    success_message = _("Public transport created successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["time_formset"] = PublicTransportFormSet(self.request.POST)
        else:
            context["time_formset"] = PublicTransportFormSet()
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Update queryset based on submitted city
        if self.request.POST and self.request.POST.get("city"):
            from cities_light.models import City, SubRegion

            try:
                city = City.objects.get(pk=self.request.POST.get("city"))
                form.fields["fromRegion"].queryset = SubRegion.objects.filter(
                    region=city.region
                )
                form.fields["toRegion"].queryset = SubRegion.objects.filter(
                    region=city.region
                )
            except City.DoesNotExist:
                pass
        return form

    def form_valid(self, form):
        context = self.get_context_data()
        time_formset = context["time_formset"]

        if time_formset.is_valid():
            has_time = any(
                formset_form.cleaned_data.get("time")
                and not formset_form.cleaned_data.get("DELETE", False)
                for formset_form in time_formset
                if formset_form.cleaned_data
            )

            if not has_time:
                form.add_error(None, _("Please add at least one departure time."))
                return self.form_invalid(form)

            self.object = form.save()
            time_formset.instance = self.object
            time_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class PublicTransportUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = PublicTransport
    template_name = "guard/views/publicTransports/index.html"
    form_class = PublicTransportForm
    success_url = reverse_lazy("guard:publicTransportsList")
    success_message = _("Public transport updated successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["time_formset"] = PublicTransportFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["time_formset"] = PublicTransportFormSet(instance=self.object)
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Update queryset based on submitted city or existing city
        city = None
        if self.request.POST and self.request.POST.get("city"):
            from cities_light.models import City, SubRegion

            try:
                city = City.objects.get(pk=self.request.POST.get("city"))
            except City.DoesNotExist:
                pass
        elif self.object and self.object.city:
            city = self.object.city

        if city:
            from cities_light.models import SubRegion

            form.fields["fromRegion"].queryset = SubRegion.objects.filter(
                region=city.region
            )
            form.fields["toRegion"].queryset = SubRegion.objects.filter(
                region=city.region
            )
        return form

    def form_valid(self, form):
        context = self.get_context_data()
        time_formset = context["time_formset"]

        if time_formset.is_valid():
            existing_times = sum(
                1
                for formset_form in time_formset
                if formset_form.instance.pk
                and not formset_form.cleaned_data.get("DELETE", False)
            )
            new_times = sum(
                1
                for formset_form in time_formset
                if formset_form.cleaned_data.get("time")
                and not formset_form.instance.pk
            )

            if existing_times + new_times < 1:
                form.add_error(
                    None, _("Please keep or add at least one departure time.")
                )
                return self.form_invalid(form)

            self.object = form.save()
            time_formset.instance = self.object
            time_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class PublicTransportDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = PublicTransport
    success_url = reverse_lazy("guard:publicTransportsList")
    success_message = _("Public transport has been deleted.")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = "guard/views/events/list.html"
    context_object_name = "events"
    # paginate_by = 10
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)


class EventCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Event
    template_name = "guard/views/events/index.html"
    form_class = EventForm
    success_url = reverse_lazy("guard:eventsList")
    success_message = _("Event created successfully.")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = ImageEventFormSet(
                self.request.POST, self.request.FILES
            )
        else:
            context["image_formset"] = ImageEventFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]

        if image_formset.is_valid():
            # Check if at least one image is uploaded
            has_image = any(
                formset_form.cleaned_data.get("image")
                and not formset_form.cleaned_data.get("DELETE", False)
                for formset_form in image_formset
                if formset_form.cleaned_data
            )

            if not has_image:
                form.add_error(None, _("Veuillez télécharger au moins une image."))
                return self.form_invalid(form)

            self.object = form.save(commit=False)
            self.object.client = self.request.user.profile

            # Shorten URL via Short.io
            try:
                service = ShortIOService()
                short_data = service.shorten_url(
                    self.object.link, title="Event Campaign"
                )
                if short_data:
                    self.object.short_link = short_data.get(
                        "secureShortURL"
                    ) or short_data.get("shortURL")
                    self.object.short_id = short_data.get("idString")
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(f"Short.io error: {e}")

            self.object.save()
            image_formset.instance = self.object
            image_formset.save()
            messages.success(self.request, self.success_message)
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)


class EventUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Event
    template_name = "guard/views/events/index.html"
    form_class = EventForm
    success_url = reverse_lazy("guard:eventsList")
    success_message = _("Event updated successfully.")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = ImageEventFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
        else:
            context["image_formset"] = ImageEventFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]

        if image_formset.is_valid():
            existing_images = sum(
                1
                for formset_form in image_formset
                if formset_form.instance.pk
                and not formset_form.cleaned_data.get("DELETE", False)
            )
            new_images = sum(
                1
                for formset_form in image_formset
                if formset_form.cleaned_data.get("image")
                and not formset_form.instance.pk
            )

            if existing_images + new_images < 1:
                form.add_error(
                    None, _("Veuillez conserver ou télécharger au moins une image.")
                )
                return self.form_invalid(form)

            self.object = form.save(commit=False)

            # Update URL via Short.io if changed
            if "link" in form.changed_data:
                try:
                    service = ShortIOService()
                    # Try to update existing link if we have a short_id
                    updated = False
                    if self.object.short_id:
                        result = service.update_link(
                            self.object.short_id,
                            self.object.link,
                            title="Event Campaign",
                        )
                        if result:
                            # Update fields just in case, though they likely remain same/similar
                            self.object.short_link = result.get(
                                "secureShortURL"
                            ) or result.get("shortURL")
                            updated = True

                    # Fallback to create new if update failed or no short_id
                    if not updated:
                        short_data = service.shorten_url(
                            self.object.link, title="Event Campaign"
                        )
                        if short_data:
                            self.object.short_link = short_data.get(
                                "secureShortURL"
                            ) or short_data.get("shortURL")
                            self.object.short_id = short_data.get("idString")

                except Exception as e:
                    import logging

                    logging.getLogger(__name__).error(f"Short.io error: {e}")

            self.object.save()
            image_formset.instance = self.object
            image_formset.save()
            messages.success(self.request, self.success_message)
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)


class EventTrackingView(LoginRequiredMixin, DetailView):
    model = Event
    template_name = "guard/views/events/partials/tracking.html"
    context_object_name = "object"

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = self.request.GET.get("period", "today")
        context["period"] = period
        context["page_title"] = self.object.name

        if self.object.short_id:
            service = ShortIOService()
            context["stats"] = service.get_link_statistics(self.object.short_id, period)

        return context


class EventDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Event
    success_url = reverse_lazy("guard:eventsList")
    success_message = _("Unfortunately, this event has been deleted")

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super(EventDeleteView, self).delete(request, *args, **kwargs)


class TipsListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Tip
    template_name = "guard/views/tips/list.html"
    context_object_name = "tips"
    # paginate_by = 10
    ordering = ["-created_at"]

    def test_func(self):
        return self.request.user.is_staff


class TipCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Tip
    form_class = TipForm
    template_name = "guard/views/tips/index.html"
    success_url = reverse_lazy("guard:tipsList")
    success_message = _("Tip created successfully")

    success_message = _("Tip created successfully")

    def form_invalid(self, form):
        messages.error(self.request, _("Error creating tip. Please check the form."))
        return super().form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class TipUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Tip
    form_class = TipForm
    template_name = "guard/views/tips/index.html"
    success_url = reverse_lazy("guard:tipsList")
    success_message = _("Tip updated successfully")

    success_message = _("Tip updated successfully")

    def form_invalid(self, form):
        messages.error(self.request, _("Error updating tip. Please check the form."))
        return super().form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class TipDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Tip
    success_url = reverse_lazy("guard:tipsList")
    success_message = _("Tip deleted successfully")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


class HikingListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Hiking
    template_name = "guard/views/hiking/list.html"
    context_object_name = "hikings"
    # paginate_by = 10
    ordering = ["-created_at"]

    def test_func(self):
        return self.request.user.is_staff


class HikingCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Hiking
    form_class = HikingForm
    template_name = "guard/views/hiking/index.html"
    success_url = reverse_lazy("guard:hikingsList")
    success_message = _("Hiking created successfully")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = ImageHikingFormSet(
                self.request.POST, self.request.FILES
            )
            context["location_formset"] = HikingLocationFormSet(self.request.POST)
        else:
            context["image_formset"] = ImageHikingFormSet()
            context["location_formset"] = HikingLocationFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]
        location_formset = context["location_formset"]

        if image_formset.is_valid() and location_formset.is_valid():
            has_image = any(
                formset_form.cleaned_data.get("image")
                and not formset_form.cleaned_data.get("DELETE", False)
                for formset_form in image_formset
                if formset_form.cleaned_data
            )

            if not has_image:
                form.add_error(None, _("Please upload at least one image."))
                return self.form_invalid(form)

            self.object = form.save()
            image_formset.instance = self.object
            image_formset.save()
            location_formset.instance = self.object
            location_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Error creating hiking. Please check the form."))
        return super().form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class HikingUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Hiking
    form_class = HikingForm
    template_name = "guard/views/hiking/index.html"
    success_url = reverse_lazy("guard:hikingsList")
    success_message = _("Hiking updated successfully")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = ImageHikingFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
            context["location_formset"] = HikingLocationFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["image_formset"] = ImageHikingFormSet(instance=self.object)
            context["location_formset"] = HikingLocationFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]
        location_formset = context["location_formset"]

        if image_formset.is_valid() and location_formset.is_valid():
            existing_images = sum(
                1
                for formset_form in image_formset
                if formset_form.instance.pk
                and not formset_form.cleaned_data.get("DELETE", False)
            )
            new_images = sum(
                1
                for formset_form in image_formset
                if formset_form.cleaned_data.get("image")
                and not formset_form.instance.pk
            )

            if existing_images + new_images < 1:
                form.add_error(
                    None, _("Veuillez conserver ou télécharger au moins une image.")
                )
                return self.form_invalid(form)

            self.object = form.save()
            image_formset.instance = self.object
            image_formset.save()
            location_formset.instance = self.object
            location_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Error updating hiking. Please check the form."))
        return super().form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class HikingDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Hiking
    success_url = reverse_lazy("guard:hikingsList")
    success_message = _("Hiking deleted successfully")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


class AdListView(LoginRequiredMixin, ListView):
    model = Ad
    template_name = "guard/views/ads/list.html"
    context_object_name = "ads"
    # paginate_by = 10
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = ShortIOService()
        for ad in context["ads"]:
            if ad.short_id:
                try:
                    clicks = service.get_clicks(ad.short_id)
                    if clicks != ad.clicks:
                        ad.clicks = clicks
                        ad.save(update_fields=["clicks"])
                except Exception:
                    pass  # Ignore errors during stats fetch
        return context


class AdCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Ad
    form_class = AdForm
    template_name = "guard/views/ads/index.html"
    success_url = reverse_lazy("guard:adsList")
    success_message = _("Ad created successfully")

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.client = self.request.user.profile

        try:
            service = ShortIOService()
            short_data = service.shorten_url(self.object.link, title="Ad Campaign")
            if short_data:
                self.object.short_link = short_data.get(
                    "secureShortURL"
                ) or short_data.get("shortURL")
                self.object.short_id = short_data.get("idString")
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Short.io error: {e}")

        self.object.save()

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, _("Error creating ad. Please check the form."))
        return super().form_invalid(form)


class AdUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Ad
    form_class = AdForm
    template_name = "guard/views/ads/index.html"
    success_url = reverse_lazy("guard:adsList")
    success_message = _("Ad updated successfully")

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def form_valid(self, form):
        self.object = form.save(commit=False)

        if "link" in form.changed_data:
            try:
                service = ShortIOService()
                updated = False
                if self.object.short_id:
                    result = service.update_link(
                        self.object.short_id, self.object.link, title="Ad Campaign"
                    )
                    if result:
                        self.object.short_link = result.get(
                            "secureShortURL"
                        ) or result.get("shortURL")
                        updated = True

                if not updated:
                    short_data = service.shorten_url(
                        self.object.link, title="Ad Campaign"
                    )
                    if short_data:
                        self.object.short_link = short_data.get(
                            "secureShortURL"
                        ) or short_data.get("shortURL")
                        self.object.short_id = short_data.get("idString")
                        self.object.clicks = 0  # Reset clicks for new link

            except Exception as e:
                import logging

                logging.getLogger(__name__).error(f"Short.io error: {e}")

        self.object.save()
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())


class AdTrackingView(LoginRequiredMixin, DetailView):
    model = Ad
    template_name = "guard/views/ads/partials/tracking.html"
    context_object_name = "object"

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = self.request.GET.get("period", "today")
        context["period"] = period
        context["page_title"] = self.object.link

        if self.object.short_id:
            service = ShortIOService()
            context["stats"] = service.get_link_statistics(self.object.short_id, period)

        return context


class AdDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Ad
    success_url = reverse_lazy("guard:adsList")
    success_message = _("Ad deleted successfully")

    def get_queryset(self):
        return super().get_queryset().filter(client=self.request.user.profile)

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


class PartnerListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Partner
    template_name = "guard/views/partners/list.html"
    context_object_name = "partners"
    # paginate_by = 10
    ordering = ["-id"]

    def test_func(self):
        return self.request.user.is_staff


class PartnerCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Partner
    form_class = PartnerForm
    template_name = "guard/views/partners/index.html"
    success_url = reverse_lazy("guard:partnersList")
    success_message = _("Partner created successfully.")

    def test_func(self):
        return self.request.user.is_staff


class PartnerUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Partner
    form_class = PartnerForm
    template_name = "guard/views/partners/index.html"
    success_url = reverse_lazy("guard:partnersList")
    success_message = _("Partner updated successfully.")

    def test_func(self):
        return self.request.user.is_staff


class PartnerDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Partner
    template_name = "guard/views/partners/delete.html"
    success_url = reverse_lazy("guard:partnersList")
    success_message = _("Partner deleted successfully.")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


class SponsorListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Sponsor
    template_name = "guard/views/sponsors/list.html"
    context_object_name = "sponsors"
    # paginate_by = 10
    ordering = ["-id"]

    def test_func(self):
        return self.request.user.is_staff


class SponsorCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Sponsor
    form_class = SponsorForm
    template_name = "guard/views/sponsors/index.html"
    success_url = reverse_lazy("guard:sponsorsList")
    success_message = _("Sponsor created successfully.")

    def test_func(self):
        return self.request.user.is_staff


class SponsorUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Sponsor
    form_class = SponsorForm
    template_name = "guard/views/sponsors/index.html"
    success_url = reverse_lazy("guard:sponsorsList")
    success_message = _("Sponsor updated successfully.")

    def test_func(self):
        return self.request.user.is_staff


class SponsorDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Sponsor
    template_name = "guard/views/sponsors/delete.html"
    success_url = reverse_lazy("guard:sponsorsList")
    success_message = _("Sponsor deleted successfully.")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


@login_required
def get_cities_by_country(request, country_id):
    from cities_light.models import City

    cities = City.objects.filter(country_id=country_id).values("id", "name")
    cities_list = list(cities)

    return JsonResponse({"success": True, "cities": cities_list})


@login_required
def get_subregions_by_city(request, city_id):
    from cities_light.models import City, SubRegion

    try:
        city = City.objects.get(id=city_id)
        # Filter subregions that belong to the same region as the city
        subregions = SubRegion.objects.filter(region=city.region).values("id", "name")
        subregions_list = list(subregions)
        return JsonResponse({"success": True, "subregions": subregions_list})
    except City.DoesNotExist:
        return JsonResponse({"success": False, "error": "City not found"}, status=404)


@login_required
def get_locations_by_city(request, city_id):
    try:
        locations = Location.objects.filter(city_id=city_id).values(
            "id", "name_en", "name_fr"
        )
        locations_list = list(locations)
        return JsonResponse({"success": True, "locations": locations_list})
    except Exception:
        return JsonResponse(
            {"success": False, "error": "Error fetching locations"}, status=500
        )


class MerchantsListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    model = Merchant
    template_name = "guard/views/merchants/list.html"
    context_object_name = "merchants"
    ordering = ["-is_featured", "-created_at"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["merchant_categories"] = MerchantCategory.objects.all()
        return context

    def test_func(self):
        return self.request.user.is_staff


class MerchantCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Merchant
    template_name = "guard/views/merchants/index.html"
    form_class = MerchantForm
    success_url = reverse_lazy("guard:merchantsList")
    success_message = _("Merchant created successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = MerchantImageFormSet(
                self.request.POST, self.request.FILES
            )
            context["product_formset"] = MerchantProductFormSet(
                self.request.POST, self.request.FILES
            )
        else:
            context["image_formset"] = MerchantImageFormSet()
            context["product_formset"] = MerchantProductFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]
        product_formset = context["product_formset"]

        if image_formset.is_valid() and product_formset.is_valid():
            self.object = form.save()
            image_formset.instance = self.object
            image_formset.save()
            product_formset.instance = self.object
            product_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class MerchantUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Merchant
    template_name = "guard/views/merchants/index.html"
    form_class = MerchantForm
    success_url = reverse_lazy("guard:merchantsList")
    success_message = _("Merchant updated successfully.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["image_formset"] = MerchantImageFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
            context["product_formset"] = MerchantProductFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
        else:
            context["image_formset"] = MerchantImageFormSet(instance=self.object)
            context["product_formset"] = MerchantProductFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context["image_formset"]
        product_formset = context["product_formset"]

        if image_formset.is_valid() and product_formset.is_valid():
            self.object = form.save()
            image_formset.instance = self.object
            image_formset.save()
            product_formset.instance = self.object
            product_formset.save()
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

    def test_func(self):
        return self.request.user.is_staff


class MerchantDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Merchant
    success_url = reverse_lazy("guard:merchantsList")
    success_message = _("Merchant has been deleted.")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff


class MerchantCategoryCreateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, CreateView
):
    model = MerchantCategory
    form_class = MerchantCategoryForm
    template_name = "guard/views/merchants/category_form.html"
    success_url = reverse_lazy("guard:merchantsList")
    success_message = _("Merchant category created successfully.")

    def test_func(self):
        return self.request.user.is_staff


class MerchantCategoryUpdateView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = MerchantCategory
    form_class = MerchantCategoryForm
    template_name = "guard/views/merchants/category_form.html"
    success_url = reverse_lazy("guard:merchantsList")
    success_message = _("Merchant category updated successfully.")

    def test_func(self):
        return self.request.user.is_staff


class MerchantCategoryDeleteView(
    UserPassesTestMixin, LoginRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = MerchantCategory
    success_url = reverse_lazy("guard:merchantsList")
    success_message = _("Merchant category has been deleted.")

    def delete(self, request, *args, **kwargs):
        messages.warning(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.is_staff

