import json


def extract_features(plan_dict):
    """Convert a terraform plan JSON dict into numerical features."""

    resource_changes = plan_dict.get("resource_changes", [])

    total_changes = len(resource_changes)
    creates = 0
    updates = 0
    deletes = 0
    no_ops = 0

    resource_types = {}
    has_public_access_change = 0
    has_encryption_change = 0
    has_versioning_change = 0
    has_tag_change = 0
    has_policy_change = 0
    has_iam_change = 0
    has_sg_change = 0
    has_rds_change = 0

    for rc in resource_changes:
        actions = rc.get("change", {}).get("actions", [])
        resource_type = rc.get("type", "unknown")
        resource_name = rc.get("name", "unknown")

        # Count action types
        if "create" in actions and "delete" not in actions:
            creates += 1
        if "update" in actions:
            updates += 1
        if "delete" in actions:
            deletes += 1
        if actions == ["no-op"]:
            no_ops += 1
            continue

        # Track resource types
        resource_types[resource_type] = resource_types.get(resource_type, 0) + 1

        # Track specific change types — check TYPE and NAME
        if "public_access_block" in resource_type or "public" in str(rc.get("change", {})).lower():
            has_public_access_change = 1
        if "encryption" in resource_type or "encrypt" in str(rc.get("change", {})).lower():
            has_encryption_change = 1
        if "versioning" in resource_type or "versioning" in resource_name:
            has_versioning_change = 1
        if "tag" in resource_type or "tag" in resource_name:
            has_tag_change = 1
        if "policy" in resource_type or "policy" in resource_name:
            has_policy_change = 1
        if resource_type.startswith("aws_iam"):
            has_iam_change = 1
        if resource_type.startswith("aws_security_group"):
            has_sg_change = 1
        if resource_type.startswith("aws_db_instance") or resource_type.startswith("aws_rds"):
            has_rds_change = 1

    total_non_noop = total_changes - no_ops

    # Severity score (heuristic)
    severity_score = 0
    if has_public_access_change:
        severity_score += 4
    if has_policy_change:
        severity_score += 3
    if has_encryption_change:
        severity_score += 2
    if deletes > 0:
        severity_score += 2
    if has_iam_change:
        severity_score += 2
    if has_sg_change:
        severity_score += 3
    if has_versioning_change:
        severity_score += 1
    if has_tag_change:
        severity_score += 0.5

    severity_score = min(severity_score, 10)

    features = {
        "total_changes": total_non_noop,
        "creates": creates,
        "updates": updates,
        "deletes": deletes,
        "s3_changes": resource_types.get("aws_s3_bucket", 0) + resource_types.get("aws_s3_bucket_public_access_block", 0) + resource_types.get("aws_s3_bucket_policy", 0) + resource_types.get("aws_s3_bucket_versioning", 0) + resource_types.get("aws_s3_bucket_server_side_encryption_configuration", 0),
        "iam_changes": resource_types.get("aws_iam_role", 0) + resource_types.get("aws_iam_policy", 0) + resource_types.get("aws_iam_role_policy_attachment", 0),
        "has_public_access_change": has_public_access_change,
        "has_encryption_change": has_encryption_change,
        "has_versioning_change": has_versioning_change,
        "has_tag_change": has_tag_change,
        "has_policy_change": has_policy_change,
        "has_iam_change": has_iam_change,
        "has_sg_change": has_sg_change,
        "severity_score": severity_score,
        "unique_resource_types": len(resource_types),
    }

    return features


def features_to_list(features):
    """Convert features dict to a list in consistent order."""
    return [
        features["total_changes"],
        features["creates"],
        features["updates"],
        features["deletes"],
        features["s3_changes"],
        features["iam_changes"],
        features["has_public_access_change"],
        features["has_encryption_change"],
        features["has_versioning_change"],
        features["has_tag_change"],
        features["has_policy_change"],
        features["has_iam_change"],
        features["has_sg_change"],
        features["severity_score"],
        features["unique_resource_types"],
    ]


FEATURE_NAMES = [
    "total_changes", "creates", "updates", "deletes",
    "s3_changes", "iam_changes",
    "has_public_access_change", "has_encryption_change",
    "has_versioning_change", "has_tag_change",
    "has_policy_change", "has_iam_change", "has_sg_change",
    "severity_score", "unique_resource_types",
]


def load_plan_file(path):
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        plan = load_plan_file(sys.argv[1])
        feats = extract_features(plan)
        print(json.dumps(feats, indent=2))
    else:
        print("Usage: python features.py <plan.json>")
