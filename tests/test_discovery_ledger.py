"""Offline regression coverage for durable World evidence and event discovery."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_discovery_ledger as ledger
from scripts import import_event_feed as feed
from scripts import sync_discovery_to_supabase as mirror

W1 = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
W2 = "wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
W3 = "wrld_cccccccc-cccc-cccc-cccc-cccccccccccc"


class DiscoveryLedgerTests(unittest.TestCase):
    def test_extracts_only_explicit_world_ids_from_public_venue_fields(self):
        row = {
            "id": "grp_11111111-1111-1111-1111-111111111111",
            "name": "Night party",
            "worldName": "Unnamed stage",
            "location": "Group instance in " + W1,
            "description": "Visit https://vrchat.com/home/world/" + W2 + "/info",
            "url": "https://vrchat.com/home/group/grp_x/calendar/cal_y",
        }
        self.assertEqual(ledger.event_ids(row), [W1, W2])
        self.assertEqual(ledger.event_ids({"name": "At Aurora Club"}), [])

    def test_event_leads_are_unapproved_and_unscored(self):
        events = [{"name": "Techno night", "worldId": W2,
                   "worldName": "Encode", "url": "https://example.com/event/1"}]
        result = ledger.event_leads(events, "event-feed", "2026-10-06")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], W2)
        self.assertEqual(result[0]["confidence"], "event-evidence-only")
        self.assertNotIn("visualPotential", result[0])

    def test_preserves_old_evidence_and_reports_historical_worlds(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            def write(name, obj):
                (folder / name).write_text(json.dumps(obj), encoding="utf-8")
            write("worlds.json", [{"id": W1, "name": "Aurora", "author": "Maker"}])
            write("world-candidates.json", [{
                "id": W2, "name": "Event venue", "source": "https://example.com",
                "sourceCategories": ["event-feed"]}])
            write("discovery-seeds.json", [{"id": W2,
                "source": "https://vrchat.com/home/world/" + W2 + "/info"}])
            write("events.json", [{"worldId": W2, "url": "https://example.com/e"}])
            write("events-auto.json", [])
            write("discovery-state.json", {"sourceHealth":
                {"vrcmap_music": {"status": "ok", "lastAttemptAt": "2026-10-06"}}})
            old = [
                {"id": W1, "name": "Aurora", "firstSeenAt": "2026-10-01",
                 "lastSeenAt": "2026-10-05", "status": "published", "evidence": [
                    {"source": "catalog", "ref": "data/worlds.json",
                     "firstSeenAt": "2026-10-01", "lastSeenAt": "2026-10-05"}]},
                {"id": W3, "name": "Old club", "firstSeenAt": "2026-09-01",
                 "lastSeenAt": "2026-09-05", "status": "pending", "evidence": [
                    {"source": "vrcmap_music", "ref": "https://vrcmap.com",
                     "firstSeenAt": "2026-09-01", "lastSeenAt": "2026-09-05"}]},
            ]
            write("world-discovery-ledger.json", old)
            with patch.object(ledger, "DATA", folder), patch.object(
                ledger, "LEDGER", folder / "world-discovery-ledger.json"
            ):
                entries, report = ledger.build_ledger("2026-10-06")
                entries_again, report_again = ledger.build_ledger("2026-10-06")
        self.assertEqual(entries, entries_again)
        self.assertEqual(report, report_again)
        by_id = {r["id"]: r for r in entries}
        self.assertEqual(len(by_id), 3)
        self.assertEqual(by_id[W1]["firstSeenAt"], "2026-10-01")
        self.assertEqual(by_id[W3]["lastSeenAt"], "2026-09-05")
        self.assertEqual(by_id[W3]["status"], "historical")
        self.assertEqual(by_id[W2]["status"], "pending")
        self.assertEqual(report["registeredWorlds"], 1)
        self.assertEqual(report["pendingCandidates"], 1)
        self.assertEqual(report["historicalOnly"], 1)
        self.assertEqual(report["bySource"]["event-curated"], 1)
        self.assertEqual(report["sourceHealth"]["vrcmap_music"]["status"], "ok")

    def test_public_event_import_retains_explicit_world_id_only(self):
        self.assertEqual(feed.explicit_venue_world_id({
            "description": "Stage world: " + W1
        }), W1)
        self.assertIsNone(feed.explicit_venue_world_id({
            "location": "Aurora Nightclub", "url": "https://vrchat.com/home/group/grp_x"
        }))

    def test_private_mirror_is_optional_without_service_key(self):
        with patch.dict(mirror.os.environ, {"SUPABASE_SERVICE_ROLE_KEY": ""}):
            with patch.object(mirror, "post_rows") as send:
                mirror.main()
                send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
