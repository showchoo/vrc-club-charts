"""Publishing integration is opt-in, sanitized and never force-pushes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import publish_interior_visual_previews as pub


def example_feed():
    return {"schemaVersion": 1, "method": "consented-video-visual-only-provisional",
            "worlds": [{"worldId": "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05",
                        "visualScore": 80, "craftsmanshipScore": None}]}


class PublicationTests(unittest.TestCase):
    def test_preview_mode_never_modifies_or_pushes(self):
        with tempfile.TemporaryDirectory() as folder:
            with (patch.object(pub, "compile_feed", return_value=example_feed()),
                  patch.object(pub, "eligible_catalog_ids", return_value=set()),
                  patch.object(pub, "git", side_effect=AssertionError("git must not run"))):
                result = pub.release(Path(folder), publish_and_push=False)
            self.assertEqual(result["status"], "preview")
            self.assertFalse(result["published"])

    def test_publication_requires_additional_rights_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            with (patch.object(pub, "compile_feed", return_value=example_feed()),
                  patch.object(pub, "eligible_catalog_ids", return_value=set()),
                  patch.object(pub, "git", side_effect=AssertionError("git must not run"))):
                with self.assertRaisesRegex(ValueError, "permission"):
                    pub.release(Path(folder), publish_and_push=True)

    def test_empty_feed_does_not_clear_existing_public_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            with (patch.object(pub, "compile_feed", return_value={"worlds": []}),
                  patch.object(pub, "eligible_catalog_ids", return_value=set()),
                  patch.object(pub, "git", side_effect=AssertionError("git must not run"))):
                result = pub.release(Path(folder), publish_and_push=True,
                                     copyright_clearance_confirmed=True)
            self.assertEqual(result["status"], "no-eligible-records")

    def test_revocation_updates_public_feed_to_empty_when_drafts_exist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            draft = root / "drafts"
            draft.mkdir()
            (draft / "one.draft.json").write_text("{}")
            target = root / "data" / "interior-visual-estimates.json"
            target.parent.mkdir()
            target.write_text(json.dumps(example_feed()))
            ops = []
            with (patch.object(pub, "ROOT", root), patch.object(pub, "OUTPUT", target),
                  patch.object(pub, "compile_feed", return_value={"schemaVersion": 1, "worlds": []}),
                  patch.object(pub, "eligible_catalog_ids", return_value=set()),
                  patch.object(pub, "check_git_safety"),
                  patch.object(pub, "git", side_effect=lambda *args, **kw: ops.append(args))):
                result = pub.release(draft, publish_and_push=True,
                                     copyright_clearance_confirmed=True)
            self.assertEqual(result["status"], "pushed")
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["worlds"], [])
            self.assertEqual(ops[-1], ("push", "origin", "main"))

    def test_unchanged_feed_has_no_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "data" / "interior-visual-estimates.json"
            target.parent.mkdir()
            target.write_text(json.dumps(example_feed()))
            with (patch.object(pub, "ROOT", root), patch.object(pub, "OUTPUT", target),
                  patch.object(pub, "compile_feed", return_value=example_feed()),
                  patch.object(pub, "eligible_catalog_ids", return_value=set()),
                  patch.object(pub, "check_git_safety") as check,
                  patch.object(pub, "git", side_effect=AssertionError("git must not run"))):
                result = pub.release(root, publish_and_push=True,
                                     copyright_clearance_confirmed=True)
            check.assert_called_once()
            self.assertEqual(result["status"], "unchanged")

    def test_new_feed_git_actions_are_fixed_and_never_force_push(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "data" / "interior-visual-estimates.json"
            target.parent.mkdir()
            target.write_text(json.dumps({"schemaVersion": 1, "worlds": []}))
            ops = []
            def record_git(*args, **kw):
                ops.append(args)
            with (patch.object(pub, "ROOT", root), patch.object(pub, "OUTPUT", target),
                  patch.object(pub, "compile_feed", return_value=example_feed()),
                  patch.object(pub, "eligible_catalog_ids", return_value=set()),
                  patch.object(pub, "check_git_safety"),
                  patch.object(pub, "git", side_effect=record_git)):
                result = pub.release(root, publish_and_push=True,
                                     copyright_clearance_confirmed=True)
            self.assertEqual(result["status"], "pushed")
            self.assertEqual(ops[0], ("add", "--", "data/interior-visual-estimates.json"))
            self.assertEqual(ops[-1], ("push", "origin", "main"))
            self.assertNotIn("--force", str(ops))
            self.assertNotIn("notes", target.read_text(encoding="utf-8"))

    def test_git_check_only_allows_clean_up_to_date_known_origin(self):
        from subprocess import CompletedProcess
        steps = [
            CompletedProcess([], 0, stdout="main\n"),
            CompletedProcess([], 0, stdout="https://github.com/showchoo/vrc-club-charts.git\n"),
            CompletedProcess([], 0, stdout=""),
            CompletedProcess([], 0, stdout=""),
            CompletedProcess([], 0, stdout="a1b2c3\n"),
            CompletedProcess([], 0, stdout="a1b2c3\n"),
        ]
        with patch.object(pub, "git", side_effect=steps) as git:
            pub.check_git_safety()
            self.assertEqual(git.call_count, 6)


if __name__ == "__main__":
    unittest.main()
