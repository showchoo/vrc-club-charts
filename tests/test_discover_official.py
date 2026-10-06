"""No-network regression tests for public World search, pagination and 401 policy."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import discover_official as official

W1 = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
W2 = "wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


class OfficialSearchTests(unittest.TestCase):
    def test_club_only_results_and_pagination(self):
        def rows(term, offset):
            if term == "club" and offset == 0:
                return [
                    {"id": W1, "name": "Aurora Nightclub", "authorName": "Maker",
                     "releaseStatus": "public"},
                    {"id": W2, "name": "Fighting Club", "authorName": "Maker",
                     "releaseStatus": "public"},
                ]
            return []
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            official, "STATE", Path(tmp) / "state.json"
        ), patch.object(official, "query_worlds", side_effect=rows):
            results, success = official.collect_candidates("2026-10-06")
            self.assertTrue(success)
            self.assertEqual([x["id"] for x in results], [W1])
            self.assertEqual(results[0]["sourceCategories"], ["vrchat_search"])
            self.assertEqual(results[0]["confidence"], "high")
            state = json.loads((Path(tmp) / "state.json").read_text())
            self.assertEqual(state["officialNextOffset"]["club"], 100)

    def test_unauthorized_search_respected(self):
        denied = HTTPError("https://api.vrchat.cloud", 401, "Unauthorized", {}, None)
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            official, "STATE", Path(tmp) / "state.json"
        ), patch.object(official, "query_worlds", side_effect=denied) as search:
            results, success = official.collect_candidates("2026-10-06")
            self.assertEqual(results, [])
            self.assertFalse(success)
            search.assert_called_once()
            self.assertFalse((Path(tmp) / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
