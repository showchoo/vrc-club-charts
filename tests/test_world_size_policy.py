"""Offline tests for fresh Windows-only 100MiB World delisting."""
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
F1 = "file_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
F2 = "file_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
F3 = "file_478cf915-abb0-457c-874c-15cb0859ef5e"
TODAY = dt.date(2026, 11, 15)


def evidence(wid=W1, size=None, scraped="2026-11-10", file_id=F1):
    return {
        "id": wid, "sizeBytes": policy.LIMIT_BYTES if size is None else size,
        "source": policy.SOURCE, "sourceUrl": policy.SOURCE_URL,
        "checkedOn": "2026-11-15", "metadataScrapedOn": scraped,
        "platform": "standalonewindows", "sourceField": policy.SOURCE_FIELD,
        "packageFileId": file_id, "packageVersion": 7,
    }


def mirror_row(wid=W1, size=None, scraped="2026-11-10 12:35:20",
               package="World - Club - Asset bundle - 2022_standalonewindows_Release",
               file_id=F1, version="7"):
    return {
        "world_id": wid, "file_id": file_id,
        "last_scrape_time": scraped,
        "package_name": package, "package_version": version,
        "size_bytes": str(policy.LIMIT_BYTES if size is None else size),
    }


class PolicyTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.folder = Path(t.name)
        self.evidence_file = self.folder / "size.json"

    def write(self, rows):
        self.evidence_file.write_text(json.dumps({
            "schemaVersion": 2, "worlds": rows,
        }), encoding="utf-8")

    def test_inclusive_100_mib_and_not_100_plus_one_byte(self):
        self.write([
            evidence(W1, size=policy.LIMIT_BYTES),
            evidence(W2, size=policy.LIMIT_BYTES + 1, file_id=F2),
            evidence(W3, size=policy.LIMIT_BYTES - 1, file_id=F3),
        ])
        self.assertEqual(policy.excluded_world_ids(
            self.evidence_file, today=TODAY), {W1, W3})

    def test_may_source_data_is_stale_despite_november_check(self):
        self.write([evidence(scraped="2026-05-01", size=55_000_000)])
        self.assertEqual(policy.excluded_world_ids(
            self.evidence_file, today=TODAY), set())
        self.assertFalse(policy.validated_evidence({
            "schemaVersion": 2,
            "worlds": [evidence(scraped="2026-05-01")]
        }, today=TODAY)[W1]["fresh"])

    def test_corruption_invalid_platform_or_untrusted_source_never_delists(self):
        invalid = [
            {**evidence(), "platform": "android"},
            {**evidence(), "sizeBytes": "30MB"},
            {**evidence(), "sourceUrl": "https://evil.invalid"},
            {**evidence(), "sourceField": "File size"},
            {**evidence(), "packageVersion": True},
            {**evidence(), "metadataScrapedOn": "2026-11-16"},
        ]
        for bad in invalid:
            with self.subTest(bad=bad):
                self.write([bad])
                self.assertEqual(policy.excluded_world_ids(
                    self.evidence_file, today=TODAY), set())
        self.evidence_file.write_text("{corrupt", encoding="utf-8")
        self.assertEqual(policy.excluded_world_ids(
            self.evidence_file, today=TODAY), set())

    def test_published_world_filter_removes_only_matching_id(self):
        worlds = [
            {"id": W1, "name": "Small", "genres": ["DJ"], "chartEligible": True},
            {"id": W2, "name": "Large", "genres": ["DJ"], "chartEligible": True},
            {"id": W3, "name": "Unknown", "genres": ["DJ"], "chartEligible": True},
        ]
        original = json.dumps(worlds)
        with (
            patch.object(stream, "excluded_world_ids", return_value={W1}),
            patch.object(stream, "load_owner_confirmed", return_value={}),
        ):
            output = stream.published_worlds(worlds, verified={})
        self.assertEqual([row["id"] for row in output], [W2, W3])
        self.assertEqual(original, json.dumps(worlds))


class SourceTests(unittest.TestCase):
    def test_sql_query_only_allowed_ids_and_unity_packages(self):
        query = collector.make_query([W1, W2])
        self.assertIn("fm.file_type = 'UNITY_PACKAGE'", query)
        self.assertIn("fm.scrape_status = 'SUCCESS'", query)
        self.assertIn(W1, query)
        self.assertIn(W2, query)
        self.assertIn("file.sizeInBytes", query)
        for bad in [[W1, W1], [], ["' OR 1=1"], [W1] * 21]:
            with self.subTest(bad=bad), self.assertRaises(collector.SizeCollectionError):
                collector.make_query(bad)

    def test_mirror_windows_pc_exact_package_not_android_or_quest(self):
        rows = [
            mirror_row(W1, size=95_000_000),
            mirror_row(W1, size=5_000_000,
                       package="World Asset bundle 2022_android_Release",
                       file_id=F2),
            mirror_row(W2, size=300_000_000, file_id=F2),
            mirror_row(W3, size=18_000_000,
                       package="World Asset bundle 2022_quest_Release",
                       file_id=F3),
        ]
        parsed = collector.extract_windows_rows(rows, {W1, W2, W3}, TODAY)
        self.assertEqual(set(parsed), {W1, W2})
        self.assertEqual(parsed[W1]["sizeBytes"], 95_000_000)
        self.assertEqual(parsed[W1]["platform"], "standalonewindows")

    def test_stale_data_and_conflicting_windows_packages_discarded(self):
        rows = [
            mirror_row(W1, size=35_000_000, scraped="2026-05-01 13:48:42"),
            mirror_row(W2, size=50_000_000, file_id=F2),
            mirror_row(W2, size=90_000_000, file_id=F3),
        ]
        self.assertEqual(collector.extract_windows_rows(
            rows, {W1, W2}, TODAY), {})

    def test_invalid_or_unexpected_mirror_world_is_rejected(self):
        with self.assertRaisesRegex(collector.SizeCollectionError, "unexpected"):
            collector.extract_windows_rows([mirror_row(W2)], {W1}, TODAY)
        self.assertIsNone(collector.parse_scrape_date("nonsense"))


class CollectorTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.work = Path(t.name)
        self.catalog = self.work / "worlds.json"
        self.out = self.work / "pc-sizes.json"
        self.catalog.write_text(json.dumps([
            {"id": W1}, {"id": W2}, {"id": W3}
        ]), encoding="utf-8")

    def test_mock_api_collects_actual_pc_size_and_preserves_unknown(self):
        request_log = []
        def read_batch(ids):
            request_log.append(ids)
            return [
                mirror_row(W1, size=40_000_000),
                mirror_row(W2, size=200_000_000, file_id=F2),
                mirror_row(W3, size=18_000_000,
                           package="2022_android", file_id=F3),
            ]
        result = collector.collect(catalog_path=self.catalog, output_path=self.out,
                                   today=TODAY, fetcher=read_batch,
                                   sleep=lambda _: None)
        self.assertEqual(result["apiRequests"], 1)
        self.assertEqual(len(request_log), 1)
        self.assertEqual(result["eligibleForPublicDelisting"], 1)
        self.assertEqual(result["unknownOrStaleWorldsNotRemoved"], 1)
        self.assertEqual(result["catalogEntriesDeleted"], 0)
        self.assertEqual(result["supabaseRowsDeleted"], 0)
        self.assertEqual(policy.excluded_world_ids(self.out, today=TODAY), {W1})
        rows = json.loads(self.out.read_text())["worlds"]
        self.assertEqual(len(rows), 2)
        self.assertNotIn("fresh", rows[0])

    def test_old_vrcw_legacy_records_are_not_converted_to_pc_evidence(self):
        self.out.write_text(json.dumps({
            "schemaVersion": 1, "worlds": [
                {"id": W1, "sizeMB": 20, "source": "vrcw-reported-file-size"}
            ]
        }))
        def no_rows(ids):
            return []
        report = collector.collect(catalog_path=self.catalog,
                                   output_path=self.out, today=TODAY,
                                   fetcher=no_rows, sleep=lambda _: None)
        self.assertEqual(report["eligibleForPublicDelisting"], 0)
        self.assertEqual(json.loads(self.out.read_text())["schemaVersion"], 2)

    def test_mirror_errors_never_remove_unknown(self):
        report = collector.collect(
            catalog_path=self.catalog, output_path=self.out,
            today=TODAY, fetcher=lambda ids: (_ for _ in ()).throw(OSError()),
            sleep=lambda _: None,
        )
        self.assertGreater(report["fetchErrors"], 0)
        self.assertEqual(report["eligibleForPublicDelisting"], 0)

    def test_existing_fresh_record_survives_temporary_mirror_failure(self):
        self.out.write_text(json.dumps({
            "schemaVersion": 2, "worlds": [evidence(W1, size=45_000_000)]
        }))
        report = collector.collect(
            catalog_path=self.catalog, output_path=self.out,
            today=TODAY, fetcher=lambda ids: [],
            sleep=lambda _: None,
        )
        self.assertEqual(report["eligibleForPublicDelisting"], 1)
        self.assertEqual(policy.excluded_world_ids(self.out, today=TODAY), {W1})


if __name__ == "__main__":
    unittest.main()
