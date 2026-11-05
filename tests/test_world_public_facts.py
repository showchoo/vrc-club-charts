"""Factual World tags and evidence status must never become feature claims."""
from __future__ import annotations

import datetime as dt
import unittest

from scripts import build_static_pages
from scripts.world_public_facts import (
    creator_tags, safe_source_url, count_text, update_day, provenance
)

WID = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def sample(**changes):
    item = {
        "id": WID, "name": "_nocturne", "author": "_buki",
        "genres": ["DJ"], "publicationBasis": "dj-tag",
        "officialTags": ["author_tag_dj", "author_tag_audiolink",
                         "author_tag_vizvid", "system_approved"],
        "releaseStatus": "public",
        "totals": {}, "weekly": {},
    }
    item.update(changes)
    return item


class WorldFactsTests(unittest.TestCase):
    def test_tags_are_author_labels_not_system_flags(self):
        self.assertEqual(creator_tags(sample()), ["DJ", "AUDIOLINK", "VIZVID"])
        page = build_static_pages.world_page(sample(), [], [])
        self.assertIn("VRChat上の制作者タグ", page)
        self.assertIn("AUDIO", page)
        self.assertNotIn("SYSTEM APPROVED", page)
        self.assertIn("配信機能の実証を意味しません", page)

    def test_duplicate_and_dangerous_tags_not_embedded(self):
        w = sample(officialTags=[
            "author_tag_dj", "AUTHOR_TAG_DJ", "author_tag_valid_tag",
            "system_approved", "author_tag_<script>",
            "author_tag_blah\\nstuff", "author_tag_a" * 30,
            99, None,
        ])
        self.assertEqual(creator_tags(w), ["DJ", "VALID TAG"])
        page = build_static_pages.world_page(w, [], [])
        self.assertNotIn("author_tag_<script>", page)

    def test_tier_dj_tag_is_not_functionality_proof(self):
        label, note = provenance(sample())
        self.assertIn("DJタグ", label)
        self.assertIn("動作は未確認", note)
        page = build_static_pages.world_page(sample(), [], [])
        self.assertIn("掲載情報と確認範囲", page)
        self.assertIn("掲載根拠", page)
        self.assertIn("DJタグによる掲載", page)

    def test_tier_owner_is_a_statement_not_a_technical_test(self):
        w = sample(publicationBasis="owner-favorite-confirmed",
                   djStreamOwnerConfirmed=True,
                   ownerStreamConfirmation={"attestedAt": "2026-11-05"})
        label, note = provenance(w)
        self.assertEqual(label, "運営者による確認申告")
        self.assertIn("独立した機器検証ではありません", note)
        page = build_static_pages.world_page(w, [], [])
        self.assertIn(note, page)
        self.assertNotIn("配信の品質を保証", page)

    def test_tier_verified_does_not_claim_all_equipment_verified(self):
        w = sample(publicationBasis="live-playback-verified",
                   djStreamTested=True,
                   djStreamVerification={
                       "method": "live-playback-tested", "platform": "PC",
                       "verifiedAt": "2026-10-20",
                       "evidenceUrl": "https://vrchat.com/home/world/" + WID
                   })
        label, note = provenance(w)
        self.assertEqual(label, "検査記録あり")
        self.assertIn("全設備の動作を保証するものではありません", note)
        page = build_static_pages.world_page(w, [], [])
        self.assertIn("検査記録あり", page)

    def test_mismatched_admission_flags_fail_closed(self):
        for altered in [
            sample(publicationBasis="live-playback-verified", djStreamTested=False),
            sample(publicationBasis="owner-favorite-confirmed",
                   djStreamOwnerConfirmed=False),
            sample(publicationBasis="arbitrary"),
        ]:
            with self.subTest(altered=altered):
                label, _ = provenance(altered)
                self.assertEqual(label, "確認情報なし")

    def test_https_sources_allowlisted_and_safely_displayed(self):
        good = [
            "https://vrchat.com/home/world/" + WID + "/info",
            "https://www.vrcw.net/world/detail/" + WID,
            "https://vrcmap.com/world/" + WID,
        ]
        for uri in good:
            with self.subTest(uri=uri):
                self.assertEqual(safe_source_url(uri), uri)
                self.assertIn('href="' + uri + '"',
                              build_static_pages.world_page(sample(source=uri), [], []))
        for uri in [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "https://evil.example/world", "http://vrchat.com/world",
            "https://vrchat.com.evil.example/world",
            "https://user:password@vrchat.com/world",
            "https://vrchat.com:444/world", "https://vrchat.com",
            "https://vrchat.com/\nunsafe", "https://vrchat.com:invalid/world",
        ]:
            with self.subTest(uri=uri):
                self.assertFalse(safe_source_url(uri))
                page = build_static_pages.world_page(sample(source=uri), [], [])
                self.assertNotIn("PUBLIC SOURCE ↗", page)

    def test_capacity_and_recommended_counts_are_conservative(self):
        self.assertEqual(count_text(80), "80")
        for v in (0, -1, 10001, 3.5, True, "80", None):
            self.assertEqual(count_text(v), "—")
        good = build_static_pages.world_page(
            sample(capacity=80, recommendedCapacity=16), [], [])
        self.assertIn("<strong>80</strong>", good)
        self.assertIn("RECOMMENDED CAPACITY", good)
        self.assertIn("<strong>16</strong>", good)
        impossible = build_static_pages.world_page(
            sample(capacity=16, recommendedCapacity=80), [], [])
        self.assertNotIn("RECOMMENDED CAPACITY", impossible)

    def test_updated_date_uses_valid_timezone_date_only(self):
        self.assertEqual(update_day("2026-08-20T02:17:09.088Z",
                                    today=dt.date(2026, 11, 6)), "2026-08-20")
        for bad in ("2028-01-01T00:00:00Z", "2026-08-20", "2010-01-01T00:00:00Z",
                    "<script>", "", None):
            self.assertEqual(update_day(bad, today=dt.date(2026, 11, 6)), "—")
        self.assertIn("2026-08-20", build_static_pages.world_page(
            sample(worldUpdatedAt="2026-08-20T02:17:09.088Z"), [], []))

    def test_missing_tags_are_honestly_absent(self):
        page = build_static_pages.world_page(sample(officialTags=[]), [], [])
        self.assertIn("制作者タグは取得できていません", page)
        self.assertNotIn("メーカー認定", page)


if __name__ == "__main__":
    unittest.main()
