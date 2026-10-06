"""Public community review UI stays readable at desktop and mobile sizes."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReviewPageReadabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT / "reviewer.html").read_text(encoding="utf-8")
        cls.css=(ROOT / "styles.css").read_text(encoding="utf-8").split("/* Review page typography:",1)[1]

    def test_readability_styles_scoped_to_review_page(self):
        self.assertIn('body class="reviewer-page community-review-page"',self.html)
        self.assertIn('styles.css?v=20261007-review-01',self.html)
        self.assertIn('body.community-review-page .reviewer-section-head > p:last-child',self.css)
        self.assertIn('body.community-review-page .community-review-comment',self.css)
        self.assertIn('body.community-review-page .reviewer-principles label',self.css)

    def test_small_text_and_form_controls_enlarged(self):
        for name,size in [
            ("community-review-comment","16px"),
            ("community-review-empty","16px"),
            ("reviewer-apply-form small","13px"),
            ("reviewer-apply-form .",None),
        ][:3]:
            idx=self.css.index(name)
            self.assertIn("font-size:"+size, self.css[idx:idx+105])
        self.assertIn("font-size:16px;",self.css)
        self.assertIn("min-height:48px;",self.css)
        self.assertIn("min-height:50px;",self.css)

    def test_mobile_review_cards_are_single_column(self):
        self.assertIn("@media (max-width:700px)",self.css)
        responsive=self.css.split("@media (max-width:700px)",1)[1]
        self.assertRegex(responsive,r"reviewer-criteria\s*\{\s*grid-template-columns:1fr;")
        self.assertRegex(responsive,r"community-review-grid\s*\{\s*grid-template-columns:1fr;")

    def test_form_still_has_required_inputs(self):
        for snippet in ['name="display_name"','name="world_id"','name="reviewed_at"',
                        'name="comment"','type="submit"','name="visited"']:
            self.assertIn(snippet,self.html)


if __name__=="__main__":
    unittest.main()
