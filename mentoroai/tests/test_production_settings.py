import importlib
import os
import sys
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

REQUIRED_ENV = {
    "DJANGO_SECRET_KEY": "secret",
    "DJANGO_ALLOWED_HOSTS": "mentoro-ai.com",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://mentoro-ai.com",
    "DJANGO_ADMINS": "Admin:admin@example.com",
}


def load_production_settings(extra_env=None):
    env = REQUIRED_ENV.copy()
    if extra_env:
        env.update(extra_env)
    original_test_db = os.getenv("TEST_DB", "postgres")
    modules = [
        name for name in list(sys.modules) if name.startswith("mentoroai.settings")
    ]
    for name in modules:
        sys.modules.pop(name)

    with mock.patch.dict(os.environ, env, clear=False):
        base_module = importlib.import_module("mentoroai.settings.base")
        importlib.reload(base_module)
        prod_module = importlib.import_module("mentoroai.settings.production")
        prod_module = importlib.reload(prod_module)

    # Restore default development settings for the rest of the test suite
    with mock.patch.dict(
            os.environ,
            {"DJANGO_ENV": "development", "TEST_DB": original_test_db},
            clear=False,
    ):
        importlib.reload(importlib.import_module("mentoroai.settings.base"))
        importlib.reload(importlib.import_module("mentoroai.settings.development"))
        importlib.reload(importlib.import_module("mentoroai.settings"))

    return prod_module


class ProductionSettingsTests(SimpleTestCase):
    def test_security_flags_are_enabled(self):
        settings = load_production_settings()
        self.assertTrue(settings.SECURE_SSL_REDIRECT)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertGreaterEqual(settings.SECURE_HSTS_SECONDS, 31536000)

    def test_logging_uses_json_formatter(self):
        settings = load_production_settings()
        formatter = settings.LOGGING["formatters"]["json"]
        self.assertEqual(formatter["()"], "mentoroai.logging.JsonFormatter")
        self.assertIn("mail_admins", settings.LOGGING["handlers"])

    def test_missing_admins_raises_error(self):
        with self.assertRaises(ImproperlyConfigured):
            load_production_settings({"DJANGO_ADMINS": ""})
