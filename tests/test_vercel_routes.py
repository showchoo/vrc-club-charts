"""Guard against Vercel silently deploying the raw repository instead of generated pages."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class VercelWorldDirectoryTests(unittest.TestCase):
    def test_vercel_builds_generated_static_world_pages(self):
        cfg=json.loads((ROOT/"vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("buildCommand"),"python3 scripts/build_vercel.py")
        self.assertEqual(cfg.get("outputDirectory"),"_site")
        self.assertEqual(cfg.get("cleanUrls"),False)
        routes={r["source"]:r["destination"] for r in cfg.get("rewrites",[])}
        self.assertEqual(routes.get("/worlds"),"/worlds/index.html")
        self.assertEqual(routes.get("/worlds/"),"/worlds/index.html")

    def test_vercel_does_not_ignore_required_build_scripts(self):
        exclusions=(ROOT/".vercelignore").read_text(encoding="utf-8").splitlines()
        self.assertFalse(any(x.strip() in ("scripts","scripts/","scripts/**") for x in exclusions))

    def test_static_builder_writes_the_worlds_directory(self):
        builder=(ROOT/"scripts/build_static_pages.py").read_text(encoding="utf-8")
        self.assertIn('world_dir = out / "worlds"',builder)
        self.assertIn('(world_dir / "index.html").write_text',builder)
        vercel=(ROOT/"scripts/build_vercel.py").read_text(encoding="utf-8")
        self.assertIn('"build_static_pages.py"',vercel)


if __name__=="__main__":
    unittest.main()
