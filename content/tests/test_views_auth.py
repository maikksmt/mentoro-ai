from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from mentoroai.tests.utils import silence_django_request_warnings

User = get_user_model()

EDITORIAL_CANDIDATE_PATHS = [
    "/en/editorial/me/drafts/",
    "/en/editorial/me/submit/",
    "/en/editorial/review/",
    "/en/editorial/review/update/",
    "/en/editorial/register-author/",
]


@override_settings(DEBUG=False)
class ContentEditorialAuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="editor",
            email="editor@example.com",
            password="pass",
            is_staff=True,
        )
        cls.user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="pass",
            is_staff=False,
        )

    def _first_existing_editorial_path(self):
        for p in EDITORIAL_CANDIDATE_PATHS:
            with silence_django_request_warnings():
                resp = self.client.get(p)
            if resp.status_code not in (404, 301, 302):  # anything “real”
                return p
        return None

    def test_editorial_requires_auth(self):
        path = self._first_existing_editorial_path()
        with silence_django_request_warnings():
            resp = self.client.get(path)
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn("/accounts/login", resp.headers.get("Location", ""))

    def test_editorial_staff_access_ok(self):
        path = self._first_existing_editorial_path()
        self.client.login(username="editor", password="pass")
        with silence_django_request_warnings():
            resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200)

    def test_editorial_nonstaff_forbidden(self):
        path = self._first_existing_editorial_path()
        self.client.login(username="regular", password="pass")
        # Fängt das WARNING-Logging ab, das Django bei PermissionDenied ausgibt
        with silence_django_request_warnings():
            resp = self.client.get(path)
        self.assertIn(resp.status_code, (302, 403))
