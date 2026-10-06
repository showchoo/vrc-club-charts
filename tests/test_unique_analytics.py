"""Privacy and aggregate-only regression checks for anonymous analytics."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UniqueAnalyticsTests(unittest.TestCase):
    def test_private_rls_and_restricted_roles(self):
        sql = (ROOT / "supabase/migrations/20261006235000_site_analytics_unique_visitors.sql").read_text("utf-8")
        self.assertIn("enable row level security", sql)
        self.assertIn("revoke all on table public.site_analytics_unique_visits from public, anon, authenticated", sql)
        self.assertIn("to service_role", sql)
        self.assertIn("primary key (visitor_hash, visit_day)", sql)

    def test_server_hashes_raw_token_without_storing_token_or_ip(self):
        function = (ROOT / "supabase/functions/analytics-track/index.ts").read_text("utf-8")
        self.assertIn('crypto.subtle.digest("SHA-256"', function)
        self.assertIn('new TextEncoder().encode("VCC:ANALYTICS:UNIQUE:v1:"+serverKey+":"+value)', function)
        self.assertIn("if(UUID.test(visitorId))", function)
        self.assertIn("visitor_hash, visit_day:jstDay(new Date())", function)
        self.assertIn('.delete().lt("visit_day",cutoff)', function)
        self.assertNotIn("ip_hash", function)

    def test_admin_receives_only_aggregate_numbers(self):
        function = (ROOT / "supabase/functions/reviewer-admin/index.ts").read_text("utf-8")
        self.assertIn("uniqueVisitors:{", function)
        self.assertIn("today:todayBrowserIds.size", function)
        self.assertIn("last7:sevenBrowserIds.size", function)
        self.assertIn("last30:thirtyBrowserIds.size", function)
        self.assertNotIn("visitorHashList:", function)
        page = (ROOT / "reviewer-admin.html").read_text("utf-8")
        for element in ("analyticsUniqueToday", "analyticsUnique7d", "analyticsUnique30d"):
            self.assertIn(element, page)

    def test_privacy_policy_explains_browser_pseudonyms(self):
        privacy = (ROOT / "privacy.html").read_text("utf-8")
        self.assertIn("ブラウザ識別子", privacy)
        self.assertIn("40日", privacy)
        self.assertIn("過去のPVから人数は復元できません", privacy)


if __name__ == "__main__":
    unittest.main()
