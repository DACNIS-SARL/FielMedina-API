import logging
import threading

import requests
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5
DEBOUNCE_SECONDS = 3

_lock = threading.Lock()
_timer = None


def _send():
    try:
        response = requests.post(
            settings.WEB_REVALIDATE_URL,
            headers={"x-revalidate-secret": settings.WEB_REVALIDATE_SECRET},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        logger.warning("Website revalidation failed: %s", error)
        return

    if response.status_code != 200:
        logger.warning(
            "Website revalidation returned %s: %s",
            response.status_code,
            response.text[:200],
        )


def _schedule():
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(DEBOUNCE_SECONDS, _send)
        _timer.daemon = True
        _timer.start()


def notify_website(sender, **kwargs):
    if not settings.WEB_REVALIDATE_SECRET or not settings.WEB_REVALIDATE_URL:
        return
    transaction.on_commit(_schedule)


def connect(models):
    for model in models:
        label = model._meta.label
        post_save.connect(notify_website, sender=model, dispatch_uid=f"revalidate-save-{label}")
        post_delete.connect(notify_website, sender=model, dispatch_uid=f"revalidate-delete-{label}")
