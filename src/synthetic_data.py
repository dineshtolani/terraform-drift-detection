import json
import random
from copy import deepcopy


RESOURCE_TEMPLATES = [
    {"address": "aws_s3_bucket.data", "type": "aws_s3_bucket", "name": "data"},
    {"address": "aws_s3_bucket.logs", "type": "aws_s3_bucket", "name": "logs"},
    {"address": "aws_s3_bucket_versioning.data", "type": "aws_s3_bucket_versioning", "name": "data"},
    {"address": "aws_s3_bucket_server_side_encryption_configuration.data", "type": "aws_s3_bucket_server_side_encryption_configuration", "name": "data"},
    {"address": "aws_s3_bucket_public_access_block.data", "type": "aws_s3_bucket_public_access_block", "name": "data"},
    {"address": "aws_s3_bucket_policy.data", "type": "aws_s3_bucket_policy", "name": "data"},
    {"address": "aws_iam_role.app", "type": "aws_iam_role", "name": "app"},
    {"address": "aws_iam_policy.s3_access", "type": "aws_iam_policy", "name": "s3_access"},
    {"address": "aws_iam_role_policy_attachment.s3_access", "type": "aws_iam_role_policy_attachment", "name": "s3_access"},
    {"address": "aws_iam_role.read_only", "type": "aws_iam_role", "name": "read_only"},
    {"address": "aws_iam_policy.read_only", "type": "aws_iam_policy", "name": "read_only"},
    {"address": "aws_iam_role_policy_attachment.read_only", "type": "aws_iam_role_policy_attachment", "name": "read_only"},
]


def _make_resource(actions, template):
    return {
        "address": template["address"],
        "mode": "managed",
        "type": template["type"],
        "name": template["name"],
        "provider_name": "registry.terraform.io/hashicorp/aws",
        "change": {
            "actions": actions,
            "before": {},
            "after": {},
            "after_unknown": {},
        }
    }


def _base_noop_resources(exclude_indices=None):
    resources = []
    for i, tmpl in enumerate(RESOURCE_TEMPLATES):
        if exclude_indices and i in exclude_indices:
            continue
        resources.append(_make_resource(["no-op"], tmpl))
    return resources


def _pick_random_subset(n):
    indices = list(range(len(RESOURCE_TEMPLATES)))
    random.shuffle(indices)
    return set(indices[:n])


def generate_no_drift(seed=None):
    """All resources unchanged."""
    if seed is not None:
        random.seed(f"no_drift_{seed}")
    return {
        "format_version": "1.2",
        "terraform_version": "1.9.0",
        "resource_changes": [_make_resource(["no-op"], tmpl) for tmpl in RESOURCE_TEMPLATES],
    }


def generate_security(seed=None):
    """Public access block changed — security drift."""
    if seed is not None:
        random.seed(f"security_{seed}")

    extra = set()
    if random.random() < 0.2:
        extra = _pick_random_subset(random.randint(1, 2))

    changed_indices = {4} | extra  # index 4 = public_access_block
    resources = []
    for i, tmpl in enumerate(RESOURCE_TEMPLATES):
        if i in changed_indices and i == 4:
            resources.append(_make_resource(["update"], tmpl))
        elif i in changed_indices:
            resources.append(_make_resource(["update"], tmpl))
        else:
            resources.append(_make_resource(["no-op"], tmpl))

    return {
        "format_version": "1.2",
        "terraform_version": "1.9.0",
        "resource_changes": resources,
    }


def generate_config(seed=None):
    """Encryption deleted + versioning suspended — config drift."""
    if seed is not None:
        random.seed(f"config_{seed}")

    extra = set()
    if random.random() < 0.15:
        extra = _pick_random_subset(random.randint(1, 2))

    changed_indices = {3, 2} | extra  # 3=encryption, 2=versioning
    resources = []
    for i, tmpl in enumerate(RESOURCE_TEMPLATES):
        if i == 3:
            resources.append(_make_resource(["delete"], tmpl))
        elif i == 2:
            resources.append(_make_resource(["update"], tmpl))
        elif i in extra:
            resources.append(_make_resource(["update"], tmpl))
        else:
            resources.append(_make_resource(["no-op"], tmpl))

    return {
        "format_version": "1.2",
        "terraform_version": "1.9.0",
        "resource_changes": resources,
    }


def generate_tag(seed=None):
    """Bucket tags changed — tag drift."""
    if seed is not None:
        random.seed(f"tag_{seed}")

    r = random.random()
    extra = set()
    if r < 0.3:
        extra = _pick_random_subset(random.randint(1, 2))

    changed_indices = {0, 1} | extra  # 0=data bucket, 1=logs bucket
    resources = []
    for i, tmpl in enumerate(RESOURCE_TEMPLATES):
        if i in changed_indices:
            resources.append(_make_resource(["update"], tmpl))
        else:
            resources.append(_make_resource(["no-op"], tmpl))

    return {
        "format_version": "1.2",
        "terraform_version": "1.9.0",
        "resource_changes": resources,
    }


def generate_deletion(seed=None):
    """IAM policy attachment deleted — deletion drift."""
    if seed is not None:
        random.seed(f"deletion_{seed}")

    extra = set()
    if random.random() < 0.15:
        extra = _pick_random_subset(random.randint(1, 2))

    changed_indices = {8} | extra  # 8 = s3_access attachment
    resources = []
    for i, tmpl in enumerate(RESOURCE_TEMPLATES):
        if i == 8:
            resources.append(_make_resource(["delete"], tmpl))
        elif i in extra:
            resources.append(_make_resource(["update"], tmpl))
        else:
            resources.append(_make_resource(["no-op"], tmpl))

    return {
        "format_version": "1.2",
        "terraform_version": "1.9.0",
        "resource_changes": resources,
    }


GENERATORS = {
    "no_drift": generate_no_drift,
    "security": generate_security,
    "config": generate_config,
    "tag": generate_tag,
    "deletion": generate_deletion,
}


def generate_plan(drift_type, seed=None):
    gen = GENERATORS.get(drift_type)
    if gen is None:
        raise ValueError(f"Unknown drift type: {drift_type}")
    return gen(seed)


def generate_and_save(drift_type, db_path, seed=None):
    import sys
    sys.path.insert(0, __file__)
    from features import extract_features
    from db import save_training_sample, init_db

    init_db()
    plan = generate_plan(drift_type, seed)
    features = extract_features(plan)
    save_training_sample(drift_type, features)
    return features
