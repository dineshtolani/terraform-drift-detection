import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from synthetic_data import generate_plan
from features import extract_features, features_to_list, FEATURE_NAMES


def test_no_drift_features():
    plan = generate_plan("no_drift", seed=42)
    feats = extract_features(plan)
    assert feats["total_changes"] == 0
    assert feats["creates"] == 0
    assert feats["updates"] == 0
    assert feats["deletes"] == 0
    assert feats["severity_score"] == 0
    assert feats["unique_resource_types"] == 0


def test_security_drift_has_public_access_flag():
    plan = generate_plan("security", seed=1)
    feats = extract_features(plan)
    assert feats["total_changes"] > 0
    assert feats["has_public_access_change"] == 1
    assert feats["severity_score"] >= 4


def test_config_drift_has_encryption_flag():
    plan = generate_plan("config", seed=1)
    feats = extract_features(plan)
    assert feats["total_changes"] > 0
    assert feats["has_encryption_change"] == 1
    assert feats["has_versioning_change"] == 1
    assert feats["severity_score"] >= 3


def test_deletion_drift_has_iam_flag():
    plan = generate_plan("deletion", seed=1)
    feats = extract_features(plan)
    assert feats["total_changes"] > 0
    assert feats["deletes"] > 0
    assert feats["iam_changes"] > 0
    assert feats["has_iam_change"] == 1


def test_tag_drift_has_tag_flag():
    plan = generate_plan("tag", seed=1)
    feats = extract_features(plan)
    assert feats["total_changes"] > 0
    assert feats["s3_changes"] > 0


def test_all_types_produce_non_empty_features():
    for dtype in ["no_drift", "security", "config", "tag", "deletion"]:
        plan = generate_plan(dtype, seed=7)
        feats = extract_features(plan)
        assert "total_changes" in feats
        assert "severity_score" in feats
        assert len(feats) == 15


def test_features_to_list_has_15_elements():
    plan = generate_plan("security", seed=3)
    feats = extract_features(plan)
    vec = features_to_list(feats)
    assert len(vec) == 15
    assert len(vec) == len(FEATURE_NAMES)


def test_reproducible_features():
    f1 = extract_features(generate_plan("security", seed=99))
    f2 = extract_features(generate_plan("security", seed=99))
    assert f1 == f2

    f3 = extract_features(generate_plan("security", seed=100))
    assert f1 != f3


def test_empty_plan():
    plan = {}
    feats = extract_features(plan)
    assert feats["total_changes"] == 0
    assert feats["creates"] == 0
    assert feats["updates"] == 0
    assert feats["deletes"] == 0
    assert feats["severity_score"] == 0


def test_empty_resource_changes():
    plan = {"resource_changes": []}
    feats = extract_features(plan)
    assert feats["total_changes"] == 0
    assert feats["unique_resource_types"] == 0


def test_all_noop_is_equivalent_to_no_drift():
    plan_empty = generate_plan("no_drift", seed=5)
    plan_noop = {
        "resource_changes": [
            {"type": "aws_s3_bucket", "name": "x", "change": {"actions": ["no-op"]}},
            {"type": "aws_iam_role", "name": "y", "change": {"actions": ["no-op"]}},
        ]
    }
    f1 = extract_features(plan_empty)
    f2 = extract_features(plan_noop)
    assert f1["total_changes"] == f2["total_changes"]
    assert f1["creates"] == f2["creates"]
    assert f1["severity_score"] == f2["severity_score"]


def test_drift_types_have_distinct_feature_patterns():
    vectors = {}
    for dtype in ["no_drift", "security", "config", "tag", "deletion"]:
        plan = generate_plan(dtype, seed=10)
        feats = extract_features(plan)
        vectors[dtype] = tuple(features_to_list(feats))

    for dtype_a in vectors:
        for dtype_b in vectors:
            if dtype_a < dtype_b:
                assert vectors[dtype_a] != vectors[dtype_b], \
                    f"{dtype_a} and {dtype_b} produce identical feature vectors"
