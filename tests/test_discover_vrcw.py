"""Offline tests for paginated club discovery, admission and omission regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import discover_vrcw as discovery

W1 = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
W2 = "wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def card(name, wid, author="World Maker", extra="クラブ"):
    return (
        '<h3><a>' + name + '</a></h3>'
        '<div>ワールドID</div><div>' + wid + '</div>'
        '<div>制作</div><a>' + author + '</a> さん'
        '<div>' + extra + '</div>'
    )


class DiscoveryTests(unittest.TestCase):
    def test_parse_directory_cards_and_filter_false_positives(self):
        raw = (card("AURORA CLUB", W1) +
               card("Avatar Clubhouse", W2) +
               card("Fighting Club", "wrld_cccccccc-cccc-cccc-cccc-cccccccccccc"))
        results = discovery.parse_listing(
            raw, "vrcw_club", "https://www.vrcw.net/category/detail/club", "2026-10-06")
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["id"], W1)
        self.assertEqual(result["authorHint"], "World Maker")
        self.assertIn("vrcw_club", result["sourceCategories"])
        self.assertTrue(discovery.eligible_for_admission(result))

    def test_dj_category_non_club_stays_unapproved(self):
        result = discovery.parse_listing(
            card("Set to ソウコ", W1, extra="DJ"), "vrcw_dj", "url", "2026-10-06")
        self.assertEqual(len(result), 1)
        self.assertFalse(discovery.eligible_for_admission(result[0]))

    def test_pagination_remembers_historical_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"nextPage":
                {"vrcw_club":4, "vrcw_dj":7}}))
            urls = []
            def fetch(url):
                urls.append(url)
                return card("Aurora Club", W1)
            with patch.object(discovery, "STATE", state), patch.object(
                discovery, "fetch_listing", side_effect=fetch
            ), patch.object(discovery.time, "sleep"):
                with patch.dict(discovery.os.environ,
                                {"VCC_DISCOVERY_PAGES_PER_SOURCE": "2"}):
                    result, succeeded = discovery.discover_candidates("2026-10-06")
            self.assertTrue(succeeded)
            self.assertEqual(len(result), 1)
            pages = json.loads(state.read_text())["nextPage"]
            self.assertEqual(pages["vrcw_club"], 5)
            self.assertEqual(pages["vrcw_dj"], 8)
            self.assertTrue(any("page=4" in url for url in urls))
            self.assertTrue(any("page=7" in url for url in urls))

    def test_missing_source_does_not_clear_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            with patch.object(discovery, "STATE", state), patch.object(
                discovery, "fetch_listing", side_effect=OSError("blocked")
            ), patch.dict(discovery.os.environ, {"VCC_DISCOVERY_PAGES_PER_SOURCE": "2"}):
                rows, success = discovery.discover_candidates("2026-10-06")
            self.assertEqual(rows, [])
            self.assertFalse(success)
            self.assertFalse(state.exists())

    def test_autopromotion_uses_public_vrchat_metadata_and_de_dupes(self):
        item = discovery.parse_listing(card("AURORA CLUB", W1), "vrcw_club", "source", "2026-10-06")[0]
        catalog = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            discovery, "STATE", Path(tmp) / "state.json"
        ):
            with patch.object(discovery, "verify_public_world", return_value={
                "name": "Official Aurora Club", "author": "Official Creator"
            }) as verify, patch.object(discovery.time, "sleep"):
                ids = discovery.auto_register([item, item], catalog, set())
            self.assertEqual(ids, [W1])
            verify.assert_called_once()
            self.assertEqual(catalog[0]["name"], "Official Aurora Club")
            self.assertEqual(catalog[0]["author"], "Official Creator")
            self.assertEqual(catalog[0]["editorialStatus"], "unreviewed")
            self.assertEqual(catalog[0]["chartEligible"], True)
            with patch.object(discovery, "verify_public_world") as verify:
                self.assertEqual(discovery.auto_register([item], catalog, set()), [])
                verify.assert_not_called()

    def test_failed_verification_waits_before_retry(self):
        item = discovery.parse_listing(card("AURORA CLUB", W1), "vrcw_club", "source", "2026-10-06")[0]
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            discovery, "STATE", Path(tmp) / "state.json"
        ), patch.object(discovery, "verify_public_world", return_value=None) as lookup:
            self.assertEqual(discovery.auto_register([item], [], set()), [])
            self.assertEqual(discovery.auto_register([item], [], set()), [])
            lookup.assert_called_once()

    def test_private_world_cannot_be_autopromoted(self):
        with patch.object(discovery.urllib.request, "urlopen") as op:
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *a): return None
                def read(self, *a): return json.dumps({
                    "id": W1, "releaseStatus": "private",
                    "name": "AURORA CLUB", "authorName": "Maker"
                }).encode()
            op.return_value = FakeResponse()
            self.assertIsNone(discovery.verify_public_world(W1, "agent"))


if __name__ == "__main__":
    unittest.main()
