"""Tests for read-only and redacted VRChat local join-log diagnostics."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import inspection_preflight as doctor
from scripts import run_one_world_inspection as launcher
from scripts import inspection_world_log as logs

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def check(report: dict, name: str) -> dict:
    return next(item for item in report["checks"] if item["check"] == name)


class LocalLogDiagnosticTests(unittest.TestCase):
    def base_preflight(self, **kwargs):
        # Platform dependencies are mocked: tests never read user logs,
        # touch the Windows client, make cloud requests or send OSC.
        with (patch.object(doctor.platform, "system", return_value="Linux"),
              patch.object(doctor.shutil, "which", return_value=None),
              patch.object(doctor, "dependency_exists", return_value=False)):
            return doctor.preflight(check_window=False, **kwargs)

    def test_diagnostic_is_off_by_default(self):
        with patch.object(logs, "corroborate_world",
                          side_effect=AssertionError("No log read without opt-in")):
            result = self.base_preflight()
        self.assertFalse(any(c["check"] == "world-log" for c in result["checks"]))

    def test_good_join_never_exposes_hash_or_private_fields(self):
        fake = {"status": "corroborated", "worldId": WORLD,
                "joinFingerprint": "deadbeef" * 8,
                "secret": "usr_PRIVATE_ONLY", "instance": "instance_PRIVATE"}
        with patch.object(logs, "corroborate_world", return_value=fake) as mocked:
            result = self.base_preflight(verify_world_log=True, world_id=WORLD)
        self.assertTrue(check(result, "world-log")["ok"])
        self.assertTrue(check(result, "world-log")["required"])
        dumped = json.dumps(result)
        self.assertNotIn("deadbeef", dumped)
        self.assertNotIn("usr_PRIVATE", dumped)
        self.assertNotIn("instance_PRIVATE", dumped)
        mocked.assert_called_once_with(WORLD, max_age_seconds=logs.MAX_ACTIVE_SESSION_AGE_SECONDS)

    def test_missing_invalid_world_id_rejected_before_log_read(self):
        for bad in (None, "", "bad_id", WORLD + "&instance=secret"):
            with self.subTest(bad=bad), patch.object(
                logs, "corroborate_world",
                side_effect=AssertionError("Log access forbidden on bad ID")
            ):
                result = self.base_preflight(verify_world_log=True, world_id=bad)
                self.assertFalse(check(result, "world-log")["ok"])

    def test_known_failure_reason_is_redacted_and_provides_diagnostic(self):
        with patch.object(logs, "corroborate_world",
                          return_value={"status": "unconfirmed",
                                        "reason": "wrong-world",
                                        "instance": "SECRET_INSTANCE"}):
            result = self.base_preflight(verify_world_log=True, world_id=WORLD)
        self.assertIn("wrong-world", check(result, "world-log")["detail"])
        self.assertNotIn("SECRET_INSTANCE", json.dumps(result))

    def test_unexpected_reason_or_exception_never_leaks_private_text(self):
        with patch.object(logs, "corroborate_world",
                          return_value={"status": "unconfirmed",
                                        "reason": "PRIVATE_USER_TOKEN"}):
            result = self.base_preflight(verify_world_log=True, world_id=WORLD)
        self.assertNotIn("PRIVATE_USER_TOKEN", json.dumps(result))
        self.assertIn("unconfirmed", check(result, "world-log")["detail"])
        with patch.object(logs, "corroborate_world",
                          side_effect=RuntimeError("C:\\Users\\PrivateUser\\VRChat\\very_secret")):
            result = self.base_preflight(verify_world_log=True, world_id=WORLD)
        self.assertFalse(check(result, "world-log")["ok"])
        self.assertNotIn("PrivateUser", json.dumps(result))

    def test_existing_sweep_diagnostic_requests_pillow(self):
        result = self.base_preflight(wants_sweep=True)
        self.assertFalse(check(result, "pillow")["ok"])
        self.assertTrue(check(result, "pillow")["required"])

    def test_one_world_diagnose_routes_sweep_and_world_id_read_only(self):
        report = {"schemaVersion": 1, "ready": True,
                  "checks": [], "doesNotAccessVRChatOrCloud": True}
        stdout = io.StringIO()
        with (patch.object(launcher, "preflight", return_value=report) as preflight,
              patch.object(launcher, "inspect",
                           side_effect=AssertionError("Recording must not start")),
              redirect_stdout(stdout)):
            rc = launcher.main([
                "--diagnose", "--sweep", "--verify-local-log", "--world-id", WORLD
            ])
        self.assertEqual(rc, 0)
        preflight.assert_called_once_with(
            wants_ai=False, wants_video_ai=False, wants_sweep=True,
            verify_world_log=True, world_id=WORLD)
        self.assertTrue(json.loads(stdout.getvalue())["doesNotAccessVRChatOrCloud"])

    def test_power_shell_launcher_has_read_only_diagnostic_arguments(self):
        script = (Path(launcher.__file__).parent /
                  "launch_one_world_inspection.ps1").read_text(encoding="utf-8")
        self.assertIn('if ($VerifyLocalLog) {', script)
        self.assertIn('if (-not $WorldId)', script)
        self.assertIn('"--verify-local-log", "--world-id", $WorldId', script)


if __name__ == "__main__":
    unittest.main()
