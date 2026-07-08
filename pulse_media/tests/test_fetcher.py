import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fetcher


class ScoreArticleTests(unittest.TestCase):
    def test_keyword_matches_raise_score(self):
        now = datetime.now(timezone.utc).isoformat()
        with_kw = {"title": "Fed hikes interest rate again", "summary": "", "published_at": now}
        without_kw = {"title": "A quiet afternoon in the park", "summary": "", "published_at": now}
        source_config = {"trust": "medium"}

        fetcher.score_article(with_kw, "finpulse", source_config)
        fetcher.score_article(without_kw, "finpulse", source_config)

        self.assertGreater(with_kw["score"], without_kw["score"])

    def test_older_article_scores_lower_on_recency(self):
        source_config = {"trust": "medium"}
        fresh = {
            "title": "Fed hikes interest rate",
            "summary": "",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        stale = {
            "title": "Fed hikes interest rate",
            "summary": "",
            "published_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        }
        fetcher.score_article(fresh, "finpulse", source_config)
        fetcher.score_article(stale, "finpulse", source_config)

        self.assertGreater(fresh["score_breakdown"]["recency"], stale["score_breakdown"]["recency"])

    def test_score_never_exceeds_100(self):
        article = {
            "title": "Fed rate hike inflation cpi gdp recession rally crash surge",
            "summary": "stocks bitcoin crypto market nasdaq dow",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        source_config = {"trust": "primary", "score_boost": 30}
        fetcher.score_article(article, "finpulse", source_config)
        self.assertLessEqual(article["score"], 100)


class DeduplicateInMemoryTests(unittest.TestCase):
    def test_near_duplicate_titles_are_collapsed(self):
        articles = [
            {"title": "Fed raises interest rates by quarter point", "article_hash": "a", "score": 50},
            {"title": "Fed raises interest rate by a quarter point", "article_hash": "b", "score": 90},
        ]
        result = fetcher.deduplicate_in_memory(articles)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["score"], 90)

    def test_distinct_titles_are_kept(self):
        articles = [
            {"title": "Fed raises interest rates", "article_hash": "a", "score": 50},
            {"title": "Apple unveils new iPhone", "article_hash": "b", "score": 40},
        ]
        result = fetcher.deduplicate_in_memory(articles)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
