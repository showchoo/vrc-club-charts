import unittest
from scripts.build_vercel import normalize_vercel_directory_urls


class VercelDirectoryURLTests(unittest.TestCase):
    def test_exact_directory_url_only(self):
        base = "https://vrc-club-charts.vercel.app/"
        content = f'<loc>{base}worlds/</loc><link rel="canonical" href="{base}worlds/index.html"><loc>{base}worlds/wrld_test.html</loc>'
        result = normalize_vercel_directory_urls(content, base)
        self.assertIn(f"<loc>{base}worlds</loc>", result)
        self.assertIn(f'href="{base}worlds"', result)
        self.assertIn(f"<loc>{base}worlds/wrld_test.html</loc>", result)
