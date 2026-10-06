"""Offline regression coverage for VCC moderation email-notification bridge."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import notify_pending_reviews as alerts

W1 = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
W2 = "wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
DIGEST = "0123456789abcdef0123456789abcdef01234567"


class PendingAlertsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.patch=patch.object(alerts,"DATA",self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, filename, contents):
        (self.root/filename).write_text(json.dumps(contents),encoding="utf-8")

    def setup_queue(self):
        self.write("world-candidates.json",[
            {"id":W1,"name":"Uncertain Nightclub","confidenceScore":83},
            {"id":W2,"name":"Not yet reviewed","confidenceScore":97}])
        self.write("world-candidate-ai-decisions.json",[
            {"id":W1,"status":"needs_review","classification":{"verdict":"uncertain"}}])
        self.write("world-submission-decisions.json",[])

    def test_only_real_waiting_cases_trigger_alerts(self):
        self.setup_queue()
        wanted=alerts.desired_alerts(decided=set(),tokens={DIGEST})
        self.assertEqual(set(wanted),{"candidate:"+W1,"review:"+DIGEST})
        self.assertIn("Uncertain Nightclub",wanted["candidate:"+W1][0])
        self.assertIn(alerts.ADMIN,wanted["review:"+DIGEST][1])
        self.assertNotIn("Not yet reviewed",str(wanted))

    def test_manually_resolved_candidates_are_not_notified(self):
        self.setup_queue()
        wanted=alerts.desired_alerts(decided={W1},tokens=set())
        self.assertEqual(wanted,{})

    def test_idempotent_issue_creation_and_auto_close(self):
        self.setup_queue()
        wanted=alerts.desired_alerts(decided=set(),tokens={DIGEST})
        created=[]
        def write_api(url,**kwargs):
            created.append((url,kwargs))
            return {"number":100}
        with patch.object(alerts,"request_json",side_effect=write_api):
            result=alerts.sync_alerts(repository="showchoo/vrc-club-charts",
                owner="showchoo",token="test",desired=wanted,existing={})
        self.assertEqual(result["created"],2)
        self.assertTrue(all(entry[1]["payload"]["assignees"]==["showchoo"] for entry in created))
        self.assertTrue(all(entry[1]["payload"]["labels"]==[alerts.LABEL] for entry in created))
        self.assertTrue(all("<!-- vcc-review-alert:" in entry[1]["payload"]["body"] for entry in created))

        issues={}
        for i,(_,request) in enumerate(created,1):
            body=request["payload"]["body"]
            key=alerts.MARKER.search(body).group(1)
            issues[key]={"number":i,"state":"open","body":body}
        with patch.object(alerts,"request_json") as api:
            again=alerts.sync_alerts(repository="showchoo/vrc-club-charts",
                owner="showchoo",token="test",desired=wanted,existing=issues)
            self.assertEqual(again["created"],0)
            api.assert_not_called()

        with patch.object(alerts,"request_json",return_value={}) as api:
            completed=alerts.sync_alerts(repository="showchoo/vrc-club-charts",
                owner="showchoo",token="test",desired={},existing=issues)
            self.assertEqual(completed["resolved"],2)
            self.assertEqual(api.call_count,2)

    def test_private_review_token_has_no_content_or_original_uuid(self):
        self.write("world-candidates.json",[])
        self.write("world-candidate-ai-decisions.json",[])
        self.write("world-submission-decisions.json",[])
        wanted=alerts.desired_alerts(decided=set(),tokens={DIGEST})
        body=wanted["review:"+DIGEST][1]
        self.assertNotIn(DIGEST,body)
        self.assertIn("レビュー本文や投稿者情報はGitHubには保存していません",body)

    def test_fail_closed_on_incomplete_supabase_response(self):
        with patch.object(alerts,"request_json",return_value={"complete":False,"pending":[]}):
            with self.assertRaisesRegex(ValueError,"unavailable"):
                alerts.pending_review_tokens()

    def test_github_issue_marker_extracts_from_older_closed_issues(self):
        issues=[{"number":19,"state":"closed",
                 "body":"old\n<!-- vcc-review-alert:review:"+DIGEST+" -->"}]
        with patch.object(alerts,"request_json",return_value=issues):
            existing=alerts.existing_alert_issues(repository="showchoo/vrc-club-charts",token="test")
        self.assertIn("review:"+DIGEST,existing)


if __name__ == "__main__":
    unittest.main()
