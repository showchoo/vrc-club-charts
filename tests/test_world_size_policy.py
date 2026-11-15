"""Offline tests for source-reported 100MB-or-smaller VRC World delisting."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import world_size_policy as policy
from scripts import update_world_sizes as collector
from scripts import dj_stream_policy as stream

W1 = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
W2 = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
W3 = "wrld_478cf915-abb0-457c-874c-15cb0859ef5e"
NOW = dt.date(2026, 11, 15)


def evidence(wid, size, checked="2026-11-15"):
    return {
        "id": wid, "sizeMB": size,
        "source": "vrcw-reported-file-size",
        "sourceUrl": f"https://en.vrcw.net/world/detail/{wid}",
        "checkedOn": checked,
        "platformInterpretation": "unspecified-single-reported-build",
        "sourceField": "File size",
    }


class WorldSizePolicyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.file = self.folder / "sizes.json"

    def write(self, items):
        self.file.write_text(json.dumps({
            "schemaVersion": 1, "worlds": items,
        }), encoding="utf-8")

    def test_exact_100_megabytes_and_smaller_excluded(self):
        self.write([evidence(W1, 100), evidence(W2, 99.999),
                    evidence(W3, 100.001)])
        removed = policy.excluded_world_ids(self.file, today=NOW)
        self.assertEqual(removed, {W1, W2})

    def test_unknown_invalid_and_outdated_data_do_not_delete(self):
        self.write([evidence(W1, 85.4, checked="2026-09-01")])
        self.assertEqual(policy.excluded_world_ids(self.file, today=NOW), set())
        self.file.write_text("{corrupt", encoding="utf-8")
        self.assertEqual(policy.excluded_world_ids(self.file, today=NOW), set())
        self.file.unlink()
        self.assertEqual(policy.excluded_world_ids(self.file, today=NOW), set())
        self.write([evidence(W1, 99.9)])
        rows = json.loads(self.file.read_text())
        rows["worlds"][0]["sourceUrl"] = "https://malicious.invalid/"
        self.file.write_text(json.dumps(rows))
        self.assertEqual(policy.excluded_world_ids(self.file, today=NOW), set())

    def test_reject_future_date_string_size_and_quest_claims(self):
        for row in [
            evidence(W1, "99.0"),
            evidence(W1, True),
            evidence(W1, -1),
            evidence(W1, 70, checked="2026-12-01"),
            {**evidence(W1, 70), "platformInterpretation": "PC"},
            {**evidence(W1, 70), "sourceField": "Download size"},
        ]:
            with self.subTest(row=row), self.assertRaises(policy.WorldSizePolicyError):
                policy.validated_evidence({"schemaVersion": 1, "worlds": [row]}, today=NOW)

    def test_listing_filter_central_and_does_not_mutate_catalog(self):
        base = [
            {"id": W1, "name": "Small", "genres": ["DJ"], "chartEligible": True},
            {"id": W2, "name": "Large", "genres": ["DJ"], "chartEligible": True},
            {"id": W3, "name": "Unknown", "genres": ["DJ"], "chartEligible": True},
        ]
        before = json.dumps(base)
        with (
            patch.object(stream, "excluded_world_ids", return_value={W1}),
            patch.object(stream, "load_owner_confirmed", return_value={}),
        ):
            admitted = stream.published_worlds(base, verified={})
        self.assertEqual([w["id"] for w in admitted], [W2, W3])
        self.assertEqual(json.dumps(base), before)
        self.assertEqual(len(base), 3)


class SizeParserTests(unittest.TestCase):
    def test_exact_page_with_file_size_parses(self):
        page = (f"<html><h1>Example World</h1><span>World ID</span>"
                f"<div>{W1}</div><dl><dt>File size</dt>"
                f"<dd>82.84MB</dd></dl></html>")
        self.assertEqual(collector.extract_reported_size(page, W1), 82.84)
        self.assertIsNone(collector.extract_reported_size(page, W2))

    def test_missing_or_ambiguous_size_never_removes(self):
        for page in [
            f"<p>{W1}</p><div>File size not available</div>",
            f"<p>{W1}</p><div>File size 101 MB</div><div>File size 40 MB</div>",
            f"<p>{W1}</p><div>File size -20MB</div>",
            f"<p>{W1}</p><div>File size 4 GB</div>",
            f"<p>{W1}</p><script>File size 42 MB</script>",
        ]:
            with self.subTest(page=page):
                self.assertIsNone(collector.extract_reported_size(page, W1))


class SizeCollectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.catalog = self.dir / "worlds.json"
        self.registry = self.dir / "world-size-evidence.json"
        self.catalog.write_text(
            json.dumps([{"id": W1}, {"id": W2}, {"id": W3}]), encoding="utf-8")

    def test_populates_only_known_ids_and_next_run_reuses_schema(self):
        observed = []
        def get_size(world_id):
            observed.append(world_id)
            return {W1: 88, W2: 100, W3: 240}[world_id]
        result = collector.collect(
            catalog_path=self.catalog, output_path=self.registry,
            max_requests=3, today=NOW, fetcher=get_size, sleep=lambda _: None)
        self.assertEqual(result["eligibleForPublicDelisting"], 2)
        self.assertEqual(result["catalogEntriesDeleted"], 0)
        self.assertEqual(result["supabaseRowsDeleted"], 0)
        self.assertEqual(set(observed), {W1, W2, W3})
        rows = json.loads(self.registry.read_text())["worlds"]
        self.assertEqual(len(rows), 3)
        self.assertNotIn("fresh", rows[0])
        self.assertEqual(policy.excluded_world_ids(self.registry, today=NOW), {W1, W2})
        # Regression: collector must not persist derived freshness key.
        result = collector.collect(
            catalog_path=self.catalog, output_path=self.registry,
            max_requests=3, today=NOW, fetcher=lambda _: self.fail("No re-fetch"),
            sleep=lambda _: None)
        self.assertEqual(result["pagesRequested"], 0)
        self.assertEqual(result["eligibleForPublicDelisting"], 2)

    def test_unavailable_world_and_network_errors_keep_unknown_worlds(self):
        def get_size(world_id):
            if world_id == W1:
                return 96
            if world_id == W2:
                raise OSError("down")
            return None
        result = collector.collect(
            catalog_path=self.catalog, output_path=self.registry,
            max_requests=3, today=NOW, fetcher=get_size, sleep=lambda _: None)
        self.assertEqual(result["eligibleForPublicDelisting"], 1)
        self.assertEqual(result["fetchErrors"], 1)
        self.assertEqual(result["unknownWorldsNotRemoved"], 2)
        self.assertEqual(policy.excluded_world_ids(self.registry, today=NOW), {W1})

    def test_scan_budget_never_fetches_more_than_requested(self):
        calls = []
        result = collector.collect(
            catalog_path=self.catalog, output_path=self.registry,
            max_requests=1, today=NOW,
            fetcher=lambda wid: (calls.append(wid) or 55),
            sleep=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["pagesRequested"], 1)

    def test_source_page_100mb_is_inclusive_not_over_100(self):
        p1 = f"<p>{W1}</p><div>File size</div><div>100MB</div>"
        p2 = f"<p>{W2}</p><div>File size</div><div>100.01MB</div>"
        self.assertEqual(collector.extract_reported_size(p1, W1), 100.0)
        self.assertEqual(collector.extract_reported_size(p2, W2), 100.01)


if __name__ == "__main__":
    unittest.main()
