"""Keep the Google Search Console ownership proof in public build outputs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "google19b2b044fc820283.html"


class GoogleSearchVerificationTest(unittest.TestCase):
    def test_expected_verification_file(self):
        self.assertEqual(
            (ROOT / NAME).read_text(encoding="utf-8").strip(),
            "google-site-verification: google19b2b044fc820283.html",
        )

    def test_vercel_build_copies_file(self):
        from scripts.build_vercel import PUBLIC_FILES

        self.assertIn(NAME, PUBLIC_FILES)

    def test_github_pages_build_copies_file(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn(f'      - "{NAME}"', workflow)
        self.assertIn(f"robots.txt {NAME} _site/", workflow)


if __name__ == "__main__":
    unittest.main()
