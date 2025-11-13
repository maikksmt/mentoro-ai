from .base import *  # noqa: F403,F401
from .base import INSTALLED_APPS, DATABASES  # noqa: F403,F401

DEBUG = True

SECRET_KEY = "dev-unsafe-change-me"

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS += [
    "rosetta",
]

# E-Mail
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Rosetta
ROSETTA_MESSAGES_PER_PAGE = 20

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# mentoroai/settings/development.py  (nur für TESTS)
DATABASES["default"]["TEST"] = {"NAME": "test_mentoroai"}
DATABASES['default']['CONN_MAX_AGE'] = 0
