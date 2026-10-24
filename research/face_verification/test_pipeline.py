import json
import tempfile
import unittest
from pathlib import Path

from pipeline import DatasetError, load_manifest, metrics, select_threshold, split_by_subject


class PipelineTests(unittest.TestCase):
    def test_manifest_rejects_unapproved_or_unconsented_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "face.jpg").write_bytes(b"test")
            path = root / "manifest.jsonl"
            path.write_text(json.dumps({"sample_id": "s1", "subject_id": "p1", "image_path": "face.jpg", "consent": False, "review_status": "approved"}), encoding="utf-8")
            with self.assertRaises(DatasetError):
                load_manifest(path, root)

    def test_manifest_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            outside = Path(directory) / "outside.jpg"
            outside.write_bytes(b"x")
            path = Path(directory) / "manifest.jsonl"
            path.write_text(json.dumps({"sample_id": "s1", "subject_id": "p1", "image_path": "../outside.jpg", "consent": True, "review_status": "approved"}), encoding="utf-8")
            with self.assertRaises(DatasetError):
                load_manifest(path, root)

    def test_split_is_reproducible_and_identity_disjoint(self):
        rows = [{"sample_id": f"{s}-{i}", "subject_id": s} for s in "abcdef" for i in range(2)]
        result = split_by_subject(rows, "test-seed")
        self.assertEqual(result, split_by_subject(rows, "test-seed"))
        sets = [set(result[k]) for k in ("train", "validation", "test")]
        self.assertFalse(sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
        self.assertEqual(set.union(*sets), set("abcdef"))

    def test_threshold_is_selected_with_requested_far(self):
        validation = [(True, 0.95), (True, 0.80), (False, 0.70), (False, 0.20)]
        threshold = select_threshold(validation, 0.0)
        self.assertEqual(metrics(validation, threshold)["false_match_rate"], 0.0)
        self.assertGreaterEqual(threshold, 0.70)

    def test_metrics_count_false_matches_and_non_matches(self):
        result = metrics([(True, 0.9), (True, 0.4), (False, 0.8), (False, 0.1)], 0.7)
        self.assertEqual(result["false_match_rate"], 0.5)
        self.assertEqual(result["false_non_match_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
