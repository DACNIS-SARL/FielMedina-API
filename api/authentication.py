import datetime
import hashlib
import secrets
from typing import Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

from .models import AuthToken

PERSISTENT_LIFETIME = datetime.timedelta(days=30)
SESSION_LIFETIME = datetime.timedelta(hours=12)
TOUCH_INTERVAL = datetime.timedelta(minutes=5)


def token_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(user, persistent: bool) -> Tuple[str, AuthToken]:
    raw = secrets.token_urlsafe(32)
    lifetime = PERSISTENT_LIFETIME if persistent else SESSION_LIFETIME
    token = AuthToken.objects.create(
        user=user,
        digest=token_digest(raw),
        persistent=persistent,
        expires_at=timezone.now() + lifetime,
    )
    return raw, token


def bearer_token(request) -> Optional[str]:
    scheme, _separator, value = request.META.get("HTTP_AUTHORIZATION", "").partition(" ")
    value = value.strip()
    return value if scheme.lower() == "bearer" and value else None


def resolve_token(request) -> Optional[AuthToken]:
    if hasattr(request, "_api_auth_token"):
        return request._api_auth_token

    token = None
    raw = bearer_token(request)
    if raw:
        token = (
            AuthToken.objects.active()
            .select_related("user")
            .filter(digest=token_digest(raw))
            .first()
        )

    if token is not None:
        now = timezone.now()
        if token.last_used_at is None or now - token.last_used_at > TOUCH_INTERVAL:
            AuthToken.objects.filter(pk=token.pk).update(last_used_at=now)
            token.last_used_at = now

    request._api_auth_token = token
    return token


def throttle_key(scope: str, value: str) -> str:
    return f"api-auth:{scope}:{token_digest(value.strip().lower())}"


def is_throttled(scope: str, value: str, limit: int) -> bool:
    return (cache.get(throttle_key(scope, value)) or 0) >= limit


def record_attempt(scope: str, value: str, window: int) -> None:
    key = throttle_key(scope, value)
    if cache.add(key, 1, window):
        return
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)


def clear_attempts(scope: str, value: str) -> None:
    cache.delete(throttle_key(scope, value))
