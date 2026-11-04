"""Regression tests for historical root-level /wrld_*.html profile URLs."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_static_pages import world_root_alias

ROOT = Path(__file__).resolve().parents[1]


class WorldRootAliasTests(unittest.TestCase):
    def test_alias_redirects_to_canonical_world_profile(self):
        wid = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
        redirect = world_root_alias(wid)
        self.assertIn(f'content="0;url=worlds/{wid}.html"', redirect)
        self.assertIn(f'href="worlds/{wid}.html"', redirect)
        self.assertIn(
            f'<link rel="canonical" href="https://vrc-club-charts.vercel.app/worlds/{wid}.html"',
            redirect,
        )
        self.assertIn('content="noindex,follow"', redirect)
        self.assertNotIn('<script', redirect)

    def test_alias_rejects_invalid_path(self):
        with self.assertRaises(ValueError):
            world_root_alias("../index")

    def test_all_generated_worlds_have_root_aliases_and_profiles(self):
        data = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))
        ids = [row["id"] for row in data["worlds"]]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_static_pages.py"), str(output)],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for wid in ids:
                with self.subTest(world=wid):
                    root_alias = output / f"{wid}.html"
                    self.assertTrue(root_alias.is_file())
                    self.assertTrue((output / "worlds" / f"{wid}.html").is_file())
                    self.assertIn(f'url=worlds/{wid}.html', root_alias.read_text(encoding="utf-8"))
            self.assertEqual(len(list(output.glob("wrld_*.html"))), len(ids))


if __name__ == "__main__":
    unittest.main()
