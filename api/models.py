from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AuthTokenQuerySet(models.QuerySet):
    def active(self):
        return self.filter(expires_at__gt=timezone.now(), user__is_active=True)


class AuthToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_tokens",
        verbose_name=_("User"),
    )
    digest = models.CharField(max_length=64, unique=True, editable=False)
    persistent = models.BooleanField(_("Keep signed in"), default=False)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("Last used at"), null=True, blank=True)
    expires_at = models.DateTimeField(_("Expires at"), db_index=True)

    objects = AuthTokenQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("API session")
        verbose_name_plural = _("API sessions")

    def __str__(self) -> str:
        return f"{self.user.get_username()} · {self.created_at:%Y-%m-%d %H:%M}"
