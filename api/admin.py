from django.contrib import admin

from .models import AuthToken


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "persistent", "created_at", "last_used_at", "expires_at")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "persistent", "created_at", "last_used_at", "expires_at")

    def has_add_permission(self, request):
        return False
