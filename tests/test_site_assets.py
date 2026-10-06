"""Guard deployment assets and retired reviewer automation against regression."""
import re
import unittest
from pathlib import Path

from scripts import build_vercel

ROOT = Path(__file__).resolve().parents[1]


class SiteAssetTests(unittest.TestCase):
    def test_public_page_scripts_in_vercel_build(self):
        published = set(build_vercel.PUBLIC_FILES)
        for page in ("index.html", "about.html", "privacy.html",
                     "reviewer.html", "reviewer-admin.html",
                     "events.html", "djs.html"):
            text = (ROOT / page).read_text(encoding="utf-8")
            for ref in re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', text):
                local = ref.split("?", 1)[0]
                if local.startswith(("https:", "http:", "//")):
                    continue
                with self.subTest(page=page, script=local):
                    self.assertIn(local, published)
                    self.assertTrue((ROOT / local).is_file())

    def test_public_review_script_is_packaged(self):
        self.assertIn("community-reviews.js", build_vercel.PUBLIC_FILES)

    def test_retired_reviewer_issues_cannot_promote(self):
        workflow = (ROOT / ".github/workflows/promote-verified-submission.yml").read_text(encoding="utf-8")
        self.assertNotIn('title.startsWith("[Reviewer]")', workflow)
        self.assertNotIn('title.startsWith("[Review]")', workflow)


if __name__ == "__main__":
    unittest.main()
