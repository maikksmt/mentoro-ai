from django.test import SimpleTestCase
from django.urls import reverse, NoReverseMatch


class ContentURLTests(SimpleTestCase):
    def test_home_url_resolves(self):
        try:
            url = reverse("home")
        except NoReverseMatch:
            url = "/"
        resp = self.client.get(url)
        self.assertIn(
            resp.status_code,
            (200, 302),
            msg=f"Unexpected status {resp.status_code} for {url}",
        )

    def test_legal_urls_resolve(self):
        paths = [
            "/en/legal/legal-notice/",
            "/en/legal/privacy/",
            "/en/legal/cookies/",
            "/en/legal/terms/",
            "/en/legal/copyright/",
        ]
        for path in paths:
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertEqual(resp.status_code, 200)

    def test_404_handler_renders(self):
        resp = self.client.get("/this-route-does-not-exist-xyz/")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("text/html", resp.headers.get("Content-Type", ""))
