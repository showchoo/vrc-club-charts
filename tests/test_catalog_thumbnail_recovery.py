"""Regression tests for missing World catalog thumbnail recovery."""
from __future__ import annotations

import unittest

from scripts.build_static_pages import index_page


class CatalogThumbnailRecoveryTests(unittest.TestCase):
    def test_cached_image_failure_triggers_metadata_recovery(self):
        world = {
            "id": "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05",
            "name": "_nocturne",
            "author": "_buki",
            "genres": ["DJ"],
        }
        page = index_page([world])
        self.assertIn('data-thumb-ready="true"', page)
        self.assertIn("window.vccQueueThumbnail?.(row)", page)
        self.assertIn("row.dataset.thumbReady='false'", page)
        self.assertIn("window.vccQueueThumbnail = queueThumbnail", page)

    def test_recovered_images_use_proxy_and_have_safe_fallback(self):
        page = index_page([{"id": "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05", "name": "Club"}])
        self.assertIn("world-thumb?id=", page)
        self.assertIn("&refreshed=1", page)
        self.assertIn("thumb.replaceChildren(img)", page)
        self.assertIn("img.onerror = () =>", page)
        self.assertIn("textContent: 'VRC'", page)


if __name__ == "__main__":
    unittest.main()
