"""Safety tests for the navigation novelty monitor."""
import unittest
from unittest.mock import patch
from scripts import inspection_navigation_guard as nav


class NavigationGuardTests(unittest.TestCase):
    def test_repeated_motion_without_visual_progress_fails_closed(self):
        guard = nav.NavigationGuard(stale_limit=2, max_recoveries=2)
        with patch.object(nav, "signature", return_value=(60,) * 16):
            actions = [guard.decide(b"mock", "forward") for _ in range(7)]
        self.assertEqual(actions[0][0], "forward")
        self.assertEqual(actions[2], ("turn_right", "bounded_recovery_turn"))
        self.assertEqual(actions[4], ("turn_left", "bounded_recovery_turn"))
        self.assertEqual(actions[6], ("stop", "no_visual_progress_after_recovery"))
        self.assertEqual(guard.metrics()["recoveryTurns"], 2)

    def test_novel_view_resets_staleness(self):
        guard = nav.NavigationGuard(stale_limit=2)
        samples = [(10,) * 16, (10,) * 16, (220,) * 16, (220,) * 16]
        with patch.object(nav, "signature", side_effect=samples):
            results = [guard.decide(b"mock", "forward") for _ in samples]
        self.assertEqual([v[0] for v in results], ["forward"] * 4)
        self.assertEqual(guard.metrics()["visualChanges"], 1)

    def test_model_stop_is_honored_in_spite_of_possible_stale_state(self):
        guard = nav.NavigationGuard(stale_limit=1)
        with patch.object(nav, "signature", return_value=(10,) * 16):
            guard.decide(b"mock", "forward")
            self.assertEqual(guard.decide(b"mock", "stop"),
                             ("stop", "model_requested_stop"))

    def test_never_uses_unrecognized_actions(self):
        guard = nav.NavigationGuard()
        with self.assertRaises(ValueError):
            guard.decide(b"mock", "click_player")
        with self.assertRaises(ValueError):
            nav.signature(b"")
        self.assertFalse(guard.metrics()["reliableCollisionDetection"])
        self.assertFalse(guard.metrics()["independentWorldCoverageVerified"])

    def test_distance_reports_no_change_for_same_signature(self):
        self.assertEqual(nav.distance((1, 2, 3), (1, 2, 3)), 0)
        self.assertEqual(nav.distance((1, 2, 3), (1, 2)), 1)
        self.assertGreater(nav.distance((0,) * 32, (255,) * 32), .99)


if __name__ == "__main__":
    unittest.main()
