"""Tests for feature flag rollout helpers."""

import unittest

from core.feature_flags import (
    parse_rollout_percentage,
    get_rollout_bucket,
    is_feature_enabled,
)


class TestFeatureFlags(unittest.TestCase):
    def test_parse_rollout_percentage(self):
        self.assertEqual(parse_rollout_percentage("150"), 100)
        self.assertEqual(parse_rollout_percentage("-1"), 0)
        self.assertEqual(parse_rollout_percentage("25"), 25)
        self.assertEqual(parse_rollout_percentage(None, default=50), 50)

    def test_bucket_deterministic(self):
        bucket1 = get_rollout_bucket("checkout_multi_step", "ABC123")
        bucket2 = get_rollout_bucket("checkout_multi_step", "ABC123")
        self.assertEqual(bucket1, bucket2)
        self.assertTrue(0 <= bucket1 <= 99)

    def test_is_feature_enabled_bounds(self):
        self.assertTrue(is_feature_enabled("flag", "seed", 100, True))
        self.assertFalse(is_feature_enabled("flag", "seed", 0, True))
        self.assertFalse(is_feature_enabled("flag", "seed", 100, False))

    def test_is_feature_enabled_bucket(self):
        bucket = get_rollout_bucket("flag", "seed")
        self.assertTrue(is_feature_enabled("flag", "seed", bucket + 1, True))
        self.assertFalse(is_feature_enabled("flag", "seed", bucket, True))


if __name__ == "__main__":
    unittest.main()
