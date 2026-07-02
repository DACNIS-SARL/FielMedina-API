from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

admin_url = f"{settings.DJANGO_ADMIN_URL.strip('/')}/"

urlpatterns = [
    path(admin_url, admin.site.urls),
    path("tinymce/", include("tinymce.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("api.urls")),
    path("", include("guard.urls")),
    path("", include("shared.urls")),
    path("subscribers/", include("subscribers.urls")),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Always serve media files (even in production) since Coolify doesn't run Nginx locally
urlpatterns += [
    re_path(rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$", serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]
