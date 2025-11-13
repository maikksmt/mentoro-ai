from django.test import TestCase


class ContentSitemapsTests(TestCase):
    def test_static_routes_present_in_content_sitemaps(self):
        resp = self.client.get("/sitemap.xml")
        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 302:
            resp = self.client.get(resp.url)
        self.assertEqual(resp.status_code, 200)

        xml = resp.content.decode()
        expected = [
            "/",
            "/en/legal/legal/",
            "/en/legal/privacy/",
            "/en/legal/cookies/",
            "/en/legal/terms/",
            "/en/legal/copyright/",
        ]
        for frag in expected:
            with self.subTest(fragment=frag):
                self.assertIn(frag, xml)
