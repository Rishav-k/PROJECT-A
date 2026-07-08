import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai


SAMPLE_RESPONSE = """HOOK
The Fed just moved markets again.

ANALYSIS
Rates are up a quarter point, and traders are recalibrating expectations.

PROS
- Slows inflation over time
- Signals confidence in the economy
- Rewards savers with higher yields

CONS
- Raises borrowing costs
- Pressures highly leveraged companies

WHO BENEFITS
- Savers and fixed-income investors

WHO LOSES
- Homebuyers with variable-rate mortgages

CTA
What do you think this means for your portfolio?

HASHTAGS
#Fed #RateHike #Markets
"""


class ParseResponseTests(unittest.TestCase):
    def test_extracts_all_sections(self):
        result = ai._parse_response(SAMPLE_RESPONSE, "#BaseTag")

        self.assertEqual(result["hook"], "The Fed just moved markets again.")
        self.assertIn("recalibrating", result["analysis"])
        self.assertEqual(len(result["pros"]), 3)
        self.assertEqual(len(result["cons"]), 2)
        self.assertEqual(result["who_benefits"], ["Savers and fixed-income investors"])
        self.assertEqual(result["who_loses"], ["Homebuyers with variable-rate mortgages"])
        self.assertIn("What do you think", result["cta"])

    def test_hashtags_merge_story_and_base_tags(self):
        result = ai._parse_response(SAMPLE_RESPONSE, "#BaseTag")
        self.assertIn("#Fed", result["hashtags"])
        self.assertIn("#BaseTag", result["hashtags"])

    def test_missing_sections_degrade_gracefully(self):
        result = ai._parse_response("Just a plain caption with no labeled sections.", "#BaseTag")
        self.assertEqual(result["pros"], [])
        self.assertEqual(result["cons"], [])
        self.assertEqual(result["hook"], "Just a plain caption with no labeled sections.")


if __name__ == "__main__":
    unittest.main()
