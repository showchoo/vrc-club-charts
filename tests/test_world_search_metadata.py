"""Search metadata must describe *only* the actual published World evidence."""
from __future__ import annotations

import html
import json
import re
import unittest
from pathlib import Path

from scripts.build_static_pages import BASE_URL, page_head, world_page
from scripts.world_search_metadata import safe_json_ld, world_search_metadata

WORLD_ID = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
WORLD_URL = BASE_URL + "worlds/" + WORLD_ID + ".html"


def world(**overrides):
    return {
        "id": WORLD_ID, "name": "_nocturne", "author": "_buki",
        "genres": ["DJ", "CLUB"], "publicationBasis": "dj-tag",
        "totals": {}, "weekly": {}, **overrides,
    }


def extract_head(document):
    return document.split("</head>", 1)[0]


def structured_data(document):
    fragments = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        document, re.DOTALL)
    return [json.loads(fragment) for fragment in fragments]


class WorldSearchMetadataTests(unittest.TestCase):
    def test_world_profile_unique_factual_title_and_description(self):
        document = world_page(world(), [], [])
        head = extract_head(document)
        self.assertIn(
            "<title>_nocturne｜VRChatクラブ・DJワールド紹介 - VRC Club Charts</title>",
            head)
        self.assertIn("制作者：_buki", head)
        self.assertIn("ジャンル：DJ、CLUB", head)
        self.assertIn("DJ配信設備の動作は未確認", head)
        self.assertIn('rel="canonical" href="' + WORLD_URL + '"', head)
        self.assertIn('property="og:description"', head)
        self.assertNotIn("配信機能確認済み", head)

    def test_json_ld_identifies_actual_vrchat_world_without_fake_ratings(self):
        head = extract_head(world_page(world(), [], []))
        entities = structured_data(head)
        self.assertEqual(len(entities), 1)
        document = entities[0]
        self.assertEqual(document["@type"], "WebPage")
        self.assertEqual(document["url"], WORLD_URL)
        item = document["mainEntity"]
        self.assertEqual(item["@type"], "CreativeWork")
        self.assertEqual(item["@id"], WORLD_URL + "#world")
        self.assertEqual(item["url"], "https://vrchat.com/home/world/" + WORLD_ID)
        self.assertEqual(item["creator"], "_buki")
        self.assertEqual(item["genre"], ["DJ", "CLUB"])
        self.assertEqual(item["isPartOf"]["name"], "VRChat")
        self.assertTrue(item["image"].startswith("https://"))
        for field in ("aggregateRating", "review", "ratingValue", "offers",
                      "award", "audio", "video", "interactionStatistic"):
            self.assertNotIn(field, item)

    def test_owner_confirmation_is_not_independent_verification(self):
        data = world()
        data["publicationBasis"] = "owner-favorite-confirmed"
        head = extract_head(world_page(data, [], []))
        self.assertIn("サイト運営者による配信機能の確認申告", head)
        self.assertIn("独立した実地検証ではありません", head)
        self.assertNotIn("DJ配信機能検証済み", head)

    def test_independent_playback_proof_not_general_functionality(self):
        data = world()
        data["publicationBasis"] = "live-playback-verified"
        head = extract_head(world_page(data, [], []))
        self.assertIn("公開されたDJ再生検査記録", head)
        self.assertNotIn("音響性能を確認", head)
        self.assertNotIn("Craftsmanship Rankingで検証済み", head)

    def test_empty_author_genres_and_status_do_not_invent(self):
        data = world()
        data.update(author="", genres=[], publicationBasis="unknown")
        head = extract_head(world_page(data, [], []))
        self.assertNotIn("制作者：", head)
        self.assertNotIn("ジャンル：", head)
        self.assertIn("掲載情報は公式ワールドページなどの公開資料を参照", head)

    def test_unsafe_names_cannot_break_json_ld_script(self):
        data = world()
        data.update(name='</script><script>alert("hacked")</script>&',
                    author='" <img src=x onerror=alert(1)>')
        head = extract_head(world_page(data, [], []))
        self.assertNotIn('</script><script>alert', head)
        self.assertNotIn('<img src=x onerror=', head)
        self.assertEqual(len(structured_data(head)), 1)
        self.assertIn('</script><script>', structured_data(head)[0]["mainEntity"]["name"])
        self.assertIn("&lt;/script&gt;", head)
        self.assertIn("&amp;", head)

    def test_long_and_duplicate_genres_are_bounded(self):
        record = world()
        record.update(name="N" * 240, author="A" * 180,
                      genres=["DJ", "DJ", "CLUB", "a" * 60, "RAVE", "NIGHT", "VIRTUAL"])
        meta = world_search_metadata(record, canonical=WORLD_URL, thumbnail="")
        self.assertEqual(len(meta["entity"]["name"]), 100)
        self.assertEqual(len(meta["entity"]["creator"]), 60)
        self.assertLessEqual(len(meta["entity"]["genre"]), 5)
        self.assertEqual(meta["entity"]["genre"][:2], ["DJ", "CLUB"])
        self.assertNotIn("image", meta["entity"])

    def test_non_world_pages_keep_generic_webpage_markup(self):
        head = extract_head(page_head("About", "About us", BASE_URL + "about.html"))
        data = structured_data(head)[0]
        self.assertEqual(data["@type"], "WebPage")
        self.assertNotIn("mainEntity", data)

    def test_json_ld_html_safe_with_unusual_characters(self):
        raw = safe_json_ld({"name": "<tag>&\u2028\u2029"})
        self.assertNotIn("<", raw)
        self.assertNotIn("&", raw)
        self.assertEqual(json.loads(raw)["name"], "<tag>&\u2028\u2029")


if __name__ == "__main__":
    unittest.main()
