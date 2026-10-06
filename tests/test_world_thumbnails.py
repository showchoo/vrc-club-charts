"""World directory imagery must be present in the initial HTML, even with no JS."""
import unittest

from scripts.build_static_pages import (
    WORLD_THUMB_ENDPOINT, index_page, world_page, world_thumbnail_url
)

WORLD_ID="wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"


class WorldThumbnailTests(unittest.TestCase):
    def sample(self, **overrides):
        return {
            "id":WORLD_ID,
            "name":"13th Floor DJ",
            "author":"SaintHaru",
            "genres":["DJ","CLUB"],
            "thumbnail":None,
            "availabilityStatus":"available",
            **overrides,
        }

    def test_missing_snapshot_image_has_cached_proxy_url(self):
        result=world_thumbnail_url(self.sample())
        self.assertEqual(result, WORLD_THUMB_ENDPOINT + "?id=" + WORLD_ID)

    def test_does_not_proxy_invalid_world_ids(self):
        self.assertEqual(world_thumbnail_url(self.sample(id="bad")), "")
        self.assertEqual(world_thumbnail_url(self.sample(id="wrld_invalid")), "")

    def test_catalog_includes_real_image_tag_without_javascript(self):
        html=index_page([self.sample()])
        self.assertIn('src="' + WORLD_THUMB_ENDPOINT + '?id=' + WORLD_ID + '"', html)
        self.assertIn('loading="lazy"',html)
        self.assertIn('data-thumb-ready="true"',html)
        self.assertIn("onerror=",html)

    def test_detail_profile_includes_image_and_error_placeholder(self):
        html=world_page(self.sample(), [], [])
        self.assertIn('src="' + WORLD_THUMB_ENDPOINT + '?id=' + WORLD_ID + '"',html)
        self.assertIn("world-detail-image-placeholder",html)
        self.assertIn("onerror=",html)

    def test_explicit_https_thumbnail_is_preserved(self):
        w=self.sample(thumbnail="https://api.vrchat.cloud/api/1/image/example/1/256")
        self.assertEqual(world_thumbnail_url(w),w["thumbnail"])

    def test_http_thumbnail_not_embedded(self):
        result=world_thumbnail_url(self.sample(thumbnail="http://unsafe.example/pic"))
        self.assertEqual(result,WORLD_THUMB_ENDPOINT + "?id=" + WORLD_ID)


if __name__=="__main__":
    unittest.main()
