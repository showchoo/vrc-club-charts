"""Regression checks for readable event detail typography, without changing World profiles."""
import re
import unittest
from pathlib import Path

from scripts import build_static_pages

ROOT = Path(__file__).resolve().parents[1]


class EventDetailTypographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "styles.css").read_text(encoding="utf-8")

    def test_event_detail_css_is_scoped_and_bounded(self):
        match = re.search(
            r"\.event-detail-page \.event-detail-hero h1\s*\{([^}]*)\}",
            self.css,
        )
        self.assertIsNotNone(match, "Event title requires a dedicated rule")
        declarations = match.group(1)
        self.assertIn("font-size: clamp(28px, 3.4vw, 48px)", declarations)
        self.assertIn("overflow-wrap: anywhere", declarations)
        self.assertIn("line-height: 1.18", declarations)
        # World detail headlines retain their original independent scale.
        self.assertIn("font-size: clamp(3rem, 8vw, 7.2rem)", self.css)

    def test_mobile_event_titles_and_lineup_are_smaller(self):
        self.assertIn("font-size: clamp(24px, 6vw, 34px)", self.css)
        self.assertIn(".event-detail-page .world-relations .section-heading h2", self.css)
        self.assertIn("font-size: clamp(23px, 2.5vw, 32px)", self.css)
        self.assertIn("font-size: clamp(36px, 5vw, 72px)", self.css)

    def test_generated_event_detail_uses_page_scope_and_fresh_css(self):
        html = build_static_pages.event_page(
            {
                "id": "event-typography-sample",
                "name": "A very long VRChat DJ night event title",
                "start": "2026-11-10T19:00:00+09:00",
                "organizer": "VCC",
            },
            [],
        )
        self.assertIn('class="shell world-detail-page event-detail-page"', html)
        self.assertIn("A very long VRChat DJ night event title</h1>", html)
        self.assertIn("styles.css?v=20261104-event-detail-01", html)


if __name__ == "__main__":
    unittest.main()
