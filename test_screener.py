import unittest

from screener import (
    add_deduplicated,
    candidate_fingerprint,
    canonicalize_url,
    normalize_candidate,
    should_screen_source,
)


class ScreenerTests(unittest.TestCase):
    def test_prefilter_requires_state_and_financial_signal(self):
        source = {"source": "Broker", "url": "https://example.com/listings"}
        self.assertTrue(
            should_screen_source(
                "New Jersey service business asking $1,200,000 with SDE $600,000",
                source,
            )
        )
        self.assertFalse(should_screen_source("New Jersey opportunities", source))

    def test_candidate_keeps_missing_financials_for_review(self):
        candidate = normalize_candidate(
            {
                "title": "Commercial cleaning company",
                "industry": "Cleaning",
                "city": "Newark",
                "state": "NJ",
                "disposition": "review",
                "confidence": 0.8,
                "greenFlags": ["Recurring contracts"],
                "redFlags": [],
                "dealBreakers": [],
                "fitSummary": "Financials are not disclosed.",
            },
            "website",
            "Example Broker",
            "https://example.com/listing/1",
        )
        self.assertEqual(candidate["disposition"], "review")
        self.assertIsNone(candidate["sde"])
        self.assertEqual(candidate["canonicalUrl"], "https://example.com/listing/1")

    def test_tracking_parameters_do_not_change_fingerprint(self):
        left = canonicalize_url("https://example.com/deal?utm_source=email&id=7")
        right = canonicalize_url("https://example.com/deal?id=7")
        self.assertEqual(left, right)

    def test_duplicate_is_retained_with_duplicate_disposition(self):
        candidate = {
            "canonicalUrl": "https://example.com/deal/7",
            "title": "A deal",
            "state": "NJ",
            "askingPrice": 1000000,
            "disposition": "review",
            "fitSummary": "Review",
        }
        candidates = []
        seen = set()
        add_deduplicated(candidate, candidates, seen)
        add_deduplicated(dict(candidate), candidates, seen)
        self.assertEqual(candidate_fingerprint(candidates[0]), candidate_fingerprint(candidates[1]))
        self.assertEqual(candidates[1]["disposition"], "duplicate")


if __name__ == "__main__":
    unittest.main()
