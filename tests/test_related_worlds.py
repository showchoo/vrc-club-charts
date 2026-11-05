"""Related club links must be indexable, accurate, and admission-safe."""
from __future__ import annotations

import re
import unittest

from scripts.related_worlds import related_worlds
from scripts.build_static_pages import world_page

W1 = "wrld_1bf5974b-1c7a-43d3-b8e2-0655432dfb91"
W2 = "wrld_2833199f-0e5f-4a5c-b16a-70502160c59c"
W3 = "wrld_ab996bcc-e7b7-47a8-948b-6ddd60503b5e"
W4 = "wrld_97b82aeb-3121-4f64-a9d8-4f89e00fe992"
W5 = "wrld_a2bbcd37-d90d-4cfa-a627-cd92c1220584"
W6 = "wrld_a46939cf-4771-45c6-a837-e01a3f04ae53"
W7 = "wrld_b751c9fa-8731-4308-81e9-8bb9d6643aa8"


def world(wid, name, *, author="Maker A", genres=None, **overrides):
    result = {
        "id": wid,
        "name": name,
        "author": author,
        "genres": genres if genres is not None else ["DJ", "DANCE"],
        "publicationBasis": "dj-tag",
        "releaseStatus": "public",
        "chartEligible": True,
    }
    result.update(overrides)
    return result


class RelatedWorldTests(unittest.TestCase):
    def setUp(self):
        self.focus = world(W1, "Alpha")
        self.same_author = world(W2, "Creator follow-up", genres=["DJ"])
        self.shared_specific = world(W3, "DANCE floor", author="Maker B",
                                     genres=["DJ", "DANCE"])
        self.shared_general = world(W4, "Other DJ", author="Maker C",
                                    genres=["DJ"])
        self.not_related = world(W5, "Unrelated", author="Maker X",
                                 genres=["ART"])

    def test_shared_creator_preferred_then_specific_then_general(self):
        candidates = [self.shared_general, self.shared_specific,
                      self.not_related, self.same_author, self.focus]
        links = related_worlds(self.focus, candidates)
        self.assertEqual([r["id"] for r in links], [W2, W3, W4])
        self.assertEqual(links[0]["reason"], "同じ制作者")
        self.assertEqual(links[1]["reason"], "共通ジャンル：DANCE")
        self.assertEqual(links[2]["reason"], "共通ジャンル：DJ")

    def test_unpublished_and_private_excluded_even_if_creator_matches(self):
        bad = [
            world(W3, "Private", releaseStatus="private"),
            world(W4, "Hidden", releaseStatus="hidden"),
            world(W5, "Unavailable", availabilityStatus="unavailable"),
            world(W6, "Not admitted", publicationBasis=""),
            world(W7, "Disabled", chartEligible=False),
        ]
        self.assertEqual(related_worlds(self.focus, bad), [])

    def test_unknown_invalid_or_duplicate_ids_never_link(self):
        options = [
            self.focus,
            world("not-a-world", "Invalid"),
            self.shared_author_copy(),
            self.same_author,
        ]
        links = related_worlds(self.focus, options)
        self.assertEqual([r["id"] for r in links], [W2])

    def shared_author_copy(self):
        return world(W1, "Same world again")

    def test_deterministic_output_and_size_cap(self):
        candidates = [
            world(wid, "Zed" if i % 2 else "Beta", author="Different",
                  genres=["DJ"])
            for i, wid in enumerate([W7, W2, W4, W3, W6, W5])
        ]
        a = related_worlds(self.focus, candidates, limit=3)
        b = related_worlds(self.focus, list(reversed(candidates)), limit=3)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)
        for invalid_limit in (0, -1, 9, True):
            with self.subTest(limit=invalid_limit), self.assertRaises(ValueError):
                related_worlds(self.focus, candidates, limit=invalid_limit)

    def test_nonpublic_source_has_no_recommendations(self):
        self.assertEqual(
            related_worlds(world(W1, "Private", releaseStatus="private"),
                           [self.same_author]), [])
        self.assertEqual(
            related_worlds(world(W1, "Not admitted", publicationBasis=""),
                           [self.same_author]), [])

    def test_detail_page_links_have_canonical_world_paths(self):
        page = world_page(
            self.focus, [], [], related_catalog=[
                self.focus, self.shared_general, self.same_author,
                self.shared_specific, self.not_related])
        self.assertIn("ほかの公開クラブワールド", page)
        for wid in (W2, W3, W4):
            self.assertIn('href="' + wid + '.html"', page)
        self.assertNotIn('href="' + W5 + '.html"', page)
        self.assertIn("DJ設備の類似性・動作性能を検証したものではありません", page)
        self.assertIn('href="index.html"', page)

    def test_explicitly_excluded_pages_never_get_links(self):
        page = world_page(self.focus, [], [], related_catalog=[
            world(W3, "Exclusion", releaseStatus="private"),
            world(W2, "Not admitted", publicationBasis=None),
        ])
        self.assertNotIn("ほかの公開クラブワールド", page)
        self.assertNotIn('href="' + W3 + '.html"', page)

    def test_untrusted_names_cannot_inject_html(self):
        suspect = world(W2, '</a><img src=x onerror=alert("hello")>',
                        author="Maker A")
        page = world_page(self.focus, [], [], related_catalog=[suspect])
        self.assertIn("&lt;/a&gt;&lt;img", page)
        self.assertNotIn('</a><img', page)
        self.assertNotIn("<img src=x", page)

    def test_only_static_public_world_links_no_live_inspection(self):
        page = world_page(self.focus, [], [], related_catalog=[self.same_author])
        self.assertNotIn("autonomousInspection", page)
        self.assertNotIn("DJ配信動作確認済み", page)
        self.assertRegex(page, re.compile(r'href="' + re.escape(W2) + r'\.html"'))
        self.assertNotIn("VCCDJPROBE", page)


if __name__ == "__main__":
    unittest.main()
