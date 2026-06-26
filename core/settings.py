from pathlib import Path
import base64
import json
import os
import environ
from firebase_admin import initialize_app, credentials


BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.is_file():
    env.read_env(env_file=str(_env_file))

SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)


INSTALLED_APPS = [
    "modeltranslation",
    "cities_light",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "strawberry.django",
    "strawberry_django",
    "tinymce",
    "fcm_django",
    "api",
    "guard",
    "shared",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("fr", "Français"),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# FIX: leading slash required for correct URL resolution in production
STATIC_URL = "/static/"
MEDIA_URL = "/upload/"
MEDIA_ROOT = BASE_DIR / "upload"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

TINYMCE_DEFAULT_CONFIG = {
    "height": 360,
    "width": "100%",
    "cleanup_on_startup": True,
    "custom_undo_redo_levels": 20,
    "selector": "textarea",
    "plugins": "link lists code",
    "toolbar": "undo redo | bold italic | bullist numlist | link code",
}


CITIES_LIGHT_TRANSLATION_LANGUAGES = ["en", "fr", "ar"]
CITIES_LIGHT_INCLUDE_COUNTRIES = ["TN", "MA", "DZ", "LY", "EG", "LB", "YE", "SY"]
CITIES_LIGHT_INCLUDE_CITY_TYPES = ["PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC"]

LOGIN_URL = "shared:login"
LOGIN_REDIRECT_URL = "guard:dashboard"
LOGOUT_REDIRECT_URL = "shared:login"

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
ADMIN_LIST_EMAILS = env.list("ADMIN_LIST_EMAILS")


if DEBUG:
    SITE_URL = "http://localhost:8000"
    CORS_ALLOW_ALL_ORIGINS = DEBUG
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]

else:
    SITE_URL = env("SITE_URL")
    CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
        "https://fielmedina.com",
        "https://www.fielmedina.com",
    ])
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["mystory.fielmedina.com"])
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT")
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS")
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL")
    DATABASES = {
        "default": env.db("DATABASE_URL")
    }

    # Redis cache — optional, gracefully skipped if REDIS_URL not set
    if env("REDIS_URL", default=None):
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": env("REDIS_URL"),
                "KEY_PREFIX": "fielmedina",
                "TIMEOUT": 300,
            }
        }
        SESSION_ENGINE = "django.contrib.sessions.backends.cache"
        SESSION_CACHE_ALIAS = "default"

    # SSL is handled by Coolify's Traefik reverse proxy
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Static files — WhiteNoise compressed storage for production
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    WHITENOISE_MANIFEST_STRICT = False
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]


PUBLIC_GROQ_API_KEI = env("PUBLIC_GROQ_API_KEI")
PUBLIC_SHORT_API = env("PUBLIC_SHORT_API")
SHORT_IO_DOMAIN = env("SHORT_IO_DOMAIN")
SHORT_IO_FOLDER_ID = env("SHORT_IO_FOLDER_ID")
DJANGO_ADMIN_URL = env("DJANGO_ADMIN_URL")


# Firebase — Base64 env var for Docker/Coolify, file fallback for local dev
_firebase_b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64")
if _firebase_b64:
    _creds_dict = json.loads(base64.b64decode(_firebase_b64))
    _cred = credentials.Certificate(_creds_dict)
else:
    _cred = credentials.Certificate(str(BASE_DIR / "firebase/firebase-adminsdk.json"))
FIREBASE_APP = initialize_app(_cred)

FCM_DJANGO_SETTINGS = {
    "APP_VERBOSE_NAME": "FielMedina",
    "ONE_DEVICE_PER_USER": False,
    "DELETE_INACTIVE_DEVICES": False,
    "UPDATE_ON_DUPLICATE_REG_ID": True,
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "django_error.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"] if DEBUG else ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "guard": {
            "handlers": ["console", "file"] if DEBUG else ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}