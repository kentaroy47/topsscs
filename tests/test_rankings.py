"""Regression checks for country/world attribution and independent rankings."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as site


class RankingsTest(unittest.TestCase):
    def setUp(self):
        self.original = site.REG
        site.REG = {
            "u:jp": {"kind": "univ", "cc": "JP", "en": "Japan U"},
            "us": {"kind": "univ", "cc": "US", "en": "US U"},
            "de": {"kind": "univ", "cc": "DE", "en": "Germany U"},
            "company": {"kind": "org", "cc": "US", "en": "Company"},
        }
        self.jp, self.us, self.world = site.SCOPES[0], site.SCOPES[1], site.SCOPES[-1]

    def tearDown(self):
        site.REG = self.original

    def paper(self, *entities):
        paper = {"authors": [{"affs": [], "x": es} for es in entities]}
        site.attach_credits(paper)
        return paper

    def test_country_ranks_are_recomputed_before_points(self):
        papers = [self.paper(["us"]) for _ in range(3)] + [self.paper(["u:jp"]) for _ in range(2)]
        papers += [self.paper(["de"])]
        country = site.championship({"isscc": site.tally(papers, self.jp, "univ", "full")})[0]
        world = site.championship({"isscc": site.tally(papers, self.world, "univ", "full")})[0]
        self.assertEqual((country[0]["eid"], country[0]["rank"], country[0]["points"]), ("u:jp", 1, 25))
        self.assertEqual((world[1]["eid"], world[1]["rank"], world[1]["points"]), ("u:jp", 2, 18))
        self.assertIn("de", [r["eid"] for r in world])

    def test_fractional_credit_keeps_global_denominator(self):
        paper = self.paper(["u:jp", "us"], ["us"], ["company"], [])
        self.assertEqual(site.tally([paper], self.jp, "univ", "full"), {"u:jp": 1})
        self.assertEqual(site.tally([paper], self.us, "univ", "first"), {"us": 1})
        self.assertEqual(site.tally([paper], self.jp, "univ", "frac"), {"u:jp": .125})
        self.assertEqual(site.tally([paper], self.us, "univ", "frac"), {"us": .375})
        self.assertEqual(site.tally([paper], self.world, "org", "frac"), {"company": .25})

    def test_duplicate_author_affiliation_counts_once(self):
        paper = {"authors": [{"affs": [{"u": "jp", "o": None}] * 2, "x": ["u:jp"]}]}
        site.attach_credits(paper)
        for mode, *_ in site.MODES:
            self.assertEqual(paper["c"][mode], {"u:jp": 1})

    def test_ties_and_tier_weight(self):
        rows, _ = site.championship({"cicc": {"us": 2, "u:jp": 2, "de": 1}})
        self.assertEqual([r["rank"] for r in rows], [1, 1, 3])
        self.assertEqual([r["points"] for r in rows], [12.5, 12.5, 7.5])

    def test_real_data_covers_five_countries_and_rest_of_world(self):
        site.REG = site.build_registry()
        papers = json.loads((site.ROOT / "data/papers.json").read_text(encoding="utf-8"))
        countries = set()
        for paper in papers:
            if paper.get("track") == "T":
                continue
            for author in paper["authors"]:
                for eid in site.author_entities(author):
                    self.assertIn(eid, site.REG)
                    countries.add(site.REG[eid]["cc"])
        expected = {s["cc"] for s in site.SCOPES if s["cc"]}
        self.assertTrue(expected.issubset(countries))
        self.assertTrue(countries - expected - {""})
        self.assertEqual(site.scope_path(site.EDITIONS[0], site.SCOPES[0], "univ", "index.html"), "index.html")


if __name__ == "__main__":
    unittest.main()
