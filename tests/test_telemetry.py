import unittest
import xml.etree.ElementTree as ET
from scripts.telemetry_metrics import (
    LanguageCategory,
    StreakStats,
    TelemetryData,
    build_telemetry,
    compute_languages,
    compute_streaks,
    compute_telemetry_hash,
)
from scripts.telemetry_svg import extract_existing_hash, render_telemetry_svg


class TestTelemetryMetrics(unittest.TestCase):
    def test_streak_grace_period_and_year_boundary(self):
        daily = {
            "2025-12-30": 1,
            "2025-12-31": 3,
            "2026-01-01": 2,
            "2026-01-02": 0,
        }
        days_52w = [{"date": k, "contributionCount": v} for k, v in daily.items()]
        s = compute_streaks(daily, today_wib="2026-01-02", days_52w=days_52w)
        self.assertEqual(s.current_days, 3)
        self.assertEqual((s.current_start, s.current_end), ("2025-12-30", "2026-01-01"))
        self.assertEqual(s.longest_days, 3)
        self.assertEqual(s.active_days_52w, 3)

    def test_streak_all_zero(self):
        daily = {"2026-11-26": 0, "2026-11-27": 0}
        days_52w = [{"date": k, "contributionCount": v} for k, v in daily.items()]
        s = compute_streaks(daily, today_wib="2026-11-27", days_52w=days_52w)
        self.assertEqual(s.current_days, 0)
        self.assertEqual(s.longest_days, 0)
        self.assertEqual((s.current_start, s.current_end), ("", ""))

    def test_languages_normalized_outlier_and_markup_only(self):
        repos = [
            {
                "name": "huge-cpp",
                "isPrivate": False,
                "languages": {"edges": [{"size": 1_500_000_000, "node": {"name": "C++"}}]},
            },
            {
                "name": "py-1",
                "isPrivate": True,
                "languages": {
                    "edges": [
                        {"size": 5000, "node": {"name": "Python"}},
                        {"size": 5000, "node": {"name": "HTML"}},
                    ]
                },
            },
            {
                "name": "py-2",
                "isPrivate": False,
                "languages": {"edges": [{"size": 2000, "node": {"name": "Python"}}]},
            },
            {
                "name": "static-site",
                "isPrivate": False,
                "languages": {"edges": [{"size": 8000, "node": {"name": "HTML"}}]},
            },
        ]
        cats = compute_languages(repos)
        self.assertEqual(cats[0].name, "Python & AI Pipelines")
        self.assertEqual(cats[0].repo_count, 2)
        self.assertEqual(cats[0].percentage, 67)
        cpp = next(c for c in cats if c.name == "C++, Go & Systems")
        self.assertEqual(cpp.percentage, 33)
        self.assertEqual(sum(c.percentage for c in cats), 100)

    def test_build_telemetry_and_hash_determinism(self):
        repos = [
            {
                "name": "app",
                "isPrivate": True,
                "languages": {"edges": [{"size": 1000, "node": {"name": "Dart"}}]},
            }
        ]
        yearly = [
            {"totalContributions": 10, "weeks": [{"contributionDays": [{"date": "2025-12-31", "contributionCount": 2}]}]},
            {"totalContributions": 5, "weeks": [{"contributionDays": [{"date": "2026-01-01", "contributionCount": 5}]}]},
        ]
        cal52 = {
            "totalContributions": 7,
            "weeks": [{"contributionDays": [{"date": "2025-12-31", "contributionCount": 2}, {"date": "2026-01-01", "contributionCount": 5}]}],
        }
        t1 = build_telemetry(repos, yearly, cal52, today_wib="2026-01-01")
        t2 = build_telemetry(repos, yearly, cal52, today_wib="2026-01-01")
        self.assertEqual(t1.total_contributions_all_time, 15)
        self.assertEqual((t1.total_repos, t1.public_repos, t1.private_repos), (1, 0, 1))
        self.assertEqual(compute_telemetry_hash(t1), compute_telemetry_hash(t2))


class TestTelemetrySvg(unittest.TestCase):
    def test_render_svg_valid_xml_and_cards(self):
        data = TelemetryData(
            days_52w=[
                {"date": "2026-11-26", "contributionCount": 0, "weekday": 4},
                {"date": "2026-11-27", "contributionCount": 5, "weekday": 5},
            ],
            total_contributions_52w=5,
            total_contributions_all_time=1542,
            total_repos=55,
            public_repos=50,
            private_repos=5,
            languages=[
                LanguageCategory("Python & AI Pipelines", "FastAPI · AI/ML", "#38bdf8", 17, 60, 12.0),
                LanguageCategory("Java & Kotlin Systems", "Android · JVM", "#60a5fa", 20, 40, 8.0),
            ],
            streak=StreakStats(112, "2026-08-08", "2026-11-27", 112, "2026-08-08", "2026-11-27", 229, 365),
        )
        svg = render_telemetry_svg(data, "NOV 27 · 16:30 WIB")
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["viewBox"], "0 0 1200 540")
        self.assertIn("1,542 Total", svg)
        self.assertIn("55 Projects", svg)
        self.assertIn("112 Days", svg)
        self.assertIn("229 ACTIVE DAYS", svg)
        self.assertIn("SYNCED NOV 27 · 16:30 WIB", svg)
        self.assertIsNotNone(extract_existing_hash(svg))

    def test_render_svg_zero_activity_no_div_zero(self):
        data = TelemetryData(
            days_52w=[{"date": "2026-11-27", "contributionCount": 0, "weekday": 5}],
            total_contributions_52w=0,
            total_contributions_all_time=0,
            total_repos=0,
            public_repos=0,
            private_repos=0,
            languages=[],
            streak=StreakStats(0, "", "", 0, "", "", 0, 1),
        )
        svg = render_telemetry_svg(data, "NOV 27 · 16:30 WIB")
        ET.fromstring(svg)
        self.assertIn("0 Days", svg)

    def test_render_svg_xml_escaping_and_hash_extraction(self):
        data = TelemetryData(
            days_52w=[{"date": "2026-11-27", "contributionCount": 1, "weekday": 5}],
            total_contributions_52w=1,
            total_contributions_all_time=1,
            total_repos=1,
            public_repos=1,
            private_repos=0,
            languages=[LanguageCategory("C++ & Go <CLI>", "A & B", "#94a3b8", 1, 100, 1.0)],
            streak=StreakStats(1, "2026-11-27", "2026-11-27", 1, "2026-11-27", "2026-11-27", 1, 1),
        )
        svg = render_telemetry_svg(data, "NOV 27 <16:30> & WIB")
        ET.fromstring(svg)
        self.assertIn("1 Day", svg)
        self.assertIsNone(extract_existing_hash("<svg></svg>"))


if __name__ == "__main__":
    unittest.main()
