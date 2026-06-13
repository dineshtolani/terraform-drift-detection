import sys
import json
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from features import extract_features
from db import init_db, save_training_sample


def main():
    init_db()

    if len(sys.argv) < 2:
        print("Usage: python ingest.py <plan.json> <label>")
        sys.exit(1)

    plan_path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else "unknown"

    with open(plan_path) as f:
        plan = json.load(f)

    features = extract_features(plan)

    # Add label info
    features["drift_type"] = label

    save_training_sample(label, features)

    changes = features.get("total_changes", 0)
    print(f"  [{label}] features: {changes} changes")


if __name__ == "__main__":
    main()
