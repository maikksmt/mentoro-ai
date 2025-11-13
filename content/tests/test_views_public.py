from django.test import TestCase


class ContentPublicViewsTests(TestCase):
    def test_home_view_200_and_template(self):
        resp = self.client.get("/", follow=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("<h1", html)  # heading present
