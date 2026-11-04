"""Sitewide Midnight Deco design regression and static asset checks."""
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import build_static_pages, build_vercel

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PAGES = (
    "index.html", "about.html", "privacy.html", "reviewer.html",
    "reviewer-admin.html", "events.html", "djs.html",
)


class MidnightDecoTests(unittest.TestCase):
    def test_all_static_pages_load_theme_after_original_styles(self):
        for name in PUBLIC_PAGES:
            with self.subTest(page=name):
                html = (ROOT / name).read_text(encoding="utf-8")
                original = re.search(r'href="styles\.css\?v=[^"]+"', html)
                theme = html.find('href="deco-theme.css?v=20261104-02"')
                self.assertIsNotNone(original)
                self.assertGreater(theme, original.end())
                self.assertLess(theme, html.find("</head>"))

    def test_generated_detail_pages_load_theme_relative_to_their_folder(self):
        page = build_static_pages.event_page(
            {
                "id": "event-midnight-deco-test",
                "name": "Midnight Sound",
                "start": "2026-11-10T20:00:00+09:00",
                "organizer": "VCC",
            },
            [],
        )
        self.assertIn('href="../deco-theme.css?v=20261104-02"', page)
        self.assertIn('href="../styles.css?v=20261104-event-detail-02"', page)

    def test_nightscape_is_well_formed_original_svg_without_reference_text(self):
        tree = ET.parse(ROOT / "deco-nightscape.svg")
        root = tree.getroot()
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(root.get("viewBox"), "0 0 1600 900")
        scene = (ROOT / "deco-nightscape.svg").read_text(encoding="utf-8")
        self.assertNotIn("HAARLEM", scene)
        self.assertNotIn("FONDATION", scene)

    def test_assets_in_both_static_publishers(self):
        for asset in ("deco-theme.css", "deco-nightscape.svg"):
            self.assertTrue((ROOT / asset).is_file())
            self.assertIn(asset, build_vercel.PUBLIC_FILES)
        pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        for asset in ("deco-theme.css", "deco-nightscape.svg"):
            self.assertIn(f'      - "{asset}"', pages)
            self.assertIn(f" {asset} ", pages)

    def test_only_main_discovery_title_uses_poiret(self):
        css = (ROOT / "deco-theme.css").read_text(encoding="utf-8")
        self.assertIn("--body-font: Inter,", css)
        self.assertIn("font-family: var(--body-font);", css)
        # Restrict the decorative font to the CLUB / DISCOVERY hero words.
        self.assertEqual(css.count("font-family: var(--deco-display);"), 1)
        hero = re.search(
            r"body\\.ranking-home \\.ai-scout-primary \\.title-overline,[\\s\\S]*?"
            r"body\\.ranking-home \\.ai-scout-primary \\.title-main \\{([^}]*)\\}",
            css,
        )
        self.assertIsNotNone(hero)
        self.assertIn("font-family: var(--deco-display);", hero.group(1))
        for selector in (".event-card h3,.dj-card h3", ".world-catalog-name",
                         ".brand > span:last-child", ".event-detail-mark"):
            self.assertIn(selector, css)
        self.assertIn(".ranking-summary strong,", css)
        self.assertIn("font-weight: 750;", css)

    def test_google_font_csp_and_readability_rules(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        headers = config["headers"][0]["headers"]
        csp = next(x["value"] for x in headers if x["key"] == "Content-Security-Policy")
        self.assertIn("https://fonts.googleapis.com", csp)
        self.assertIn("https://fonts.gstatic.com", csp)
        css = (ROOT / "deco-theme.css").read_text(encoding="utf-8")
        self.assertTrue(css.startswith("/* VRC Club Charts"))
        self.assertIn("Poiret+One", css)
        self.assertIn("deco-nightscape.svg", css)
        self.assertIn(".event-detail-page .event-detail-hero h1", css)
        self.assertIn("font-size: clamp(19px, 2.27vw, 32px)", css)
        self.assertIn("font-size: clamp(16px, 4vw, 23px)", css)
        self.assertIn("a:focus-visible", css)
        self.assertIn("@media (max-width: 640px)", css)


if __name__ == "__main__":
    unittest.main()
