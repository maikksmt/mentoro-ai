from django.test import TestCase


class CompareServiceSmokeTests(TestCase):
    def test_parse_ids_contract_if_exposed(self):
        try:
            from compare.views import parse_ids  # falls vorhanden
        except Exception:
            self.skipTest("No parse_ids service-like function exposed – skipping.")
        out = parse_ids("beta,alpha,alpha,,gamma")
        self.assertEqual(out, ["beta", "alpha", "alpha", "gamma"])
