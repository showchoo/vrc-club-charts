"""Offline regression tests for Gemini-gated discovery candidate admissions."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts import review_discovery_candidates as worker

WID="wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
WID2="wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OFFICIAL={
    "id": WID,"name":"Aurora DJ Club","authorName":"Official Creator",
    "releaseStatus":"public",
    "description":"Nightclub for techno DJ events with dance floor and visuals",
    "tags":["club","audiolink"]
}
ASSESS={
    "verdict":"club","confidence":0.97,
    "evidence":["Nightclub","DJ dance floor"],
    "reasonJa":"公式説明にナイトクラブとDJフロアの記載がある",
    "imageConsidered":False
}


class DiscoveryAIReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.worlds=root/"worlds.json"
        self.candidates=root/"world-candidates.json"
        self.decisions=root/"world-candidate-ai-decisions.json"
        self.worlds.write_text("[]\n",encoding="utf-8")
        self.candidates.write_text(json.dumps([{
            "id":WID,"name":"Aurora DJ Club","confidenceScore":97,
            "source":"https://vrcmap.com/world/"+WID,
            "sourceCategories":["vrcmap_cafe"]
        }]),encoding="utf-8")
        self.decisions.write_text("[]\n",encoding="utf-8")
        patches=[
            patch.object(worker,"WORLDS",self.worlds),
            patch.object(worker,"CANDIDATES",self.candidates),
            patch.object(worker,"DECISIONS",self.decisions),
            patch.object(worker,"moderation_decisions",return_value={}),
            patch.dict(worker.os.environ,{"GEMINI_API_KEY":"fake-test-key","VCC_DISCOVERY_AI_MAX_PER_RUN":"6"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def read(self,path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_high_confidence_public_club_is_added_without_fabricated_ratings(self):
        with patch.object(worker.classifier,"public_metadata",return_value=OFFICIAL) as verify,patch.object(
            worker.classifier,"classify_world",return_value=ASSESS
        ) as gemini:
            outcome=worker.review_candidates()
        self.assertEqual(outcome["approved"],1)
        verify.assert_called_once_with(WID)
        gemini.assert_called_once()
        row=self.read(self.worlds)[0]
        self.assertEqual(row["name"],"Aurora DJ Club")
        self.assertEqual(row["author"],"Official Creator")
        self.assertEqual(row["editorialStatus"],"unreviewed")
        self.assertTrue(row["chartEligible"])
        self.assertEqual(row["discoveredBy"],"automatic-discovery-gemini-reviewed")
        self.assertNotIn("editorial",row)
        self.assertNotIn("visualScore",row)
        self.assertEqual(self.read(self.candidates),[])
        self.assertEqual(self.read(self.decisions)[0]["status"],"approved")

    def test_uncertain_stays_in_admin_candidate_queue(self):
        with patch.object(worker.classifier,"public_metadata",return_value=OFFICIAL),patch.object(
            worker.classifier,"classify_world",return_value={**ASSESS,"confidence":0.62}
        ):
            result=worker.review_candidates()
        self.assertEqual(result["approved"],0)
        self.assertEqual(self.read(self.worlds),[])
        self.assertEqual(len(self.read(self.candidates)),1)
        self.assertEqual(self.read(self.decisions)[0]["status"],"needs_review")

    def test_moderator_rejection_cannot_be_overwritten_by_ai(self):
        with patch.object(worker,"moderation_decisions",return_value={WID:"rejected"}),patch.object(
            worker.classifier,"public_metadata"
        ) as verify:
            result=worker.review_candidates()
        verify.assert_not_called()
        self.assertEqual(result["approved"],0)
        self.assertEqual(self.read(self.worlds),[])

    def test_moderator_status_endpoint_fails_closed(self):
        before=self.candidates.read_bytes()
        with patch.object(worker,"moderation_decisions",side_effect=OSError("down")),patch.object(
            worker.classifier,"public_metadata"
        ) as verify:
            with self.assertRaisesRegex(OSError,"down"):
                worker.review_candidates()
        verify.assert_not_called()
        self.assertEqual(self.candidates.read_bytes(),before)
        self.assertEqual(self.read(self.worlds),[])

    def test_401_does_not_reject_or_auto_approve(self):
        code=urllib.error.HTTPError("https://api.vrchat.cloud/",401,"Unauthorized",{},None)
        with patch.object(worker.classifier,"public_metadata",side_effect=code),patch.object(
            worker.classifier,"classify_world"
        ) as gemini:
            worker.review_candidates()
        gemini.assert_not_called()
        self.assertEqual(self.read(self.worlds),[])
        self.assertEqual(self.read(self.candidates)[0]["id"],WID)
        self.assertEqual(self.read(self.decisions)[0]["status"],"verification_unavailable")

    def test_failed_401_is_rate_limited_before_retry(self):
        now=dt.datetime.now(dt.timezone.utc)
        record={"status":"verification_unavailable","reviewedAt":now.isoformat()}
        self.assertFalse(worker.retry_due(record,now))
        self.assertTrue(worker.retry_due(record,now+dt.timedelta(hours=7)))
        self.assertFalse(worker.retry_due({"status":"needs_review","reviewedAt":"bad"},now))

    def test_heuristic_score_100_without_ai_key_cannot_publish(self):
        with patch.dict(worker.os.environ,{"GEMINI_API_KEY":""}),patch.object(
            worker.classifier,"public_metadata"
        ) as verify:
            result=worker.review_candidates()
        verify.assert_not_called()
        self.assertEqual(result["approved"],0)
        self.assertEqual(self.read(self.candidates)[0]["confidenceScore"],97)

    def test_original_discovery_script_no_longer_promotes_without_gemini(self):
        code=(Path(__file__).resolve().parents[1]/"scripts"/"discover_worlds.py").read_text(encoding="utf-8")
        self.assertNotIn("new_ids = auto_register(",code)
        self.assertIn("moderation_status_ids()",code)
        pipeline=(Path(__file__).resolve().parents[1]/".github/workflows"/"review-submitted-worlds.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/review_discovery_candidates.py",pipeline)


if __name__=="__main__":
    unittest.main()
