"""Static search sitemap describes only admitted World profiles and canonical URLs."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.build_static_pages import BASE_URL
from scripts.dj_stream_policy import load_verified, published_worlds
import json

ROOT = Path(__file__).resolve().parents[1]
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SearchSiteMapTests(unittest.TestCase):
    def test_all_indexed_worlds_have_real_unique_canonical_profiles(self):
        ranking = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))
        published = published_worlds(ranking["worlds"], load_verified())
        target_ids = {x["id"] for x in published
                      if x.get("availabilityStatus") != "unavailable"}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            subprocess.run(
                [sys.executable, "scripts/build_static_pages.py", str(output)],
                cwd=ROOT, check=True, capture_output=True, text=True)
            xml = ET.parse(output / "sitemap.xml")
            links = [node.text for node in xml.findall(".//sm:loc", NS)]
            self.assertEqual(len(links), len(set(links)))
            self.assertTrue(all(link.startswith(BASE_URL) for link in links))
            actual_ids = {
                link.removeprefix(BASE_URL + "worlds/").removesuffix(".html")
                for link in links if link.startswith(BASE_URL + "worlds/")
                and link != BASE_URL + "worlds/"
            }
            self.assertEqual(target_ids, actual_ids)
            for wid in target_ids:
                with self.subTest(world=wid):
                    url = BASE_URL + "worlds/" + wid + ".html"
                    page_path = output / "worlds" / (wid + ".html")
                    self.assertTrue(page_path.is_file())
                    head = page_path.read_text(encoding="utf-8").split("</head>", 1)[0]
                    self.assertIn('rel="canonical" href="' + url + '"', head)
                    self.assertRegex(head, '<meta name="description" content="[^"]+"')
                    self.assertIn('"mainEntity"', head)
                    self.assertNotIn("noindex", head)
                    self.assertNotIn(BASE_URL + wid + ".html", links)


if __name__ == "__main__":
    unittest.main()
