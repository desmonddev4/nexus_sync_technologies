import math

from django.test import SimpleTestCase

from apps.accounts.management.commands.calibrate_face_threshold import (
    _auc,
    _rates,
    _threshold_for_far,
)


class FaceThresholdCalibrationTests(SimpleTestCase):
    def test_zero_target_far_places_cutoff_above_highest_impostor(self):
        cutoff = _threshold_for_far([0.2, 0.4, 0.7], 0.0)

        self.assertIsNotNone(cutoff)
        self.assertGreater(cutoff, 0.7)
        far, _frr = _rates([0.8, 0.9], [0.2, 0.4, 0.7], cutoff)
        self.assertEqual(far, 0.0)

    def test_allowed_far_uses_highest_cutoff_that_meets_empirical_target(self):
        cutoff = _threshold_for_far([0.1, 0.5, 0.7], 0.34)

        self.assertIsNotNone(cutoff)
        far, _frr = _rates([0.6, 0.8], [0.1, 0.5, 0.7], cutoff)
        self.assertLessEqual(far, 0.34)
        self.assertGreater(far, 0.0)
        self.assertTrue(math.isclose(cutoff, math.nextafter(0.5, math.inf)))

    def test_no_cutoff_meets_zero_far_if_impostor_score_is_maximum(self):
        self.assertIsNone(_threshold_for_far([0.4, 1.0], 0.0))

    def test_auc_separates_ordered_score_groups(self):
        self.assertEqual(_auc([0.8, 0.9], [0.1, 0.2]), 1.0)
