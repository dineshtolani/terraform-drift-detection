#!/usr/bin/env python3
"""Generate labelled training data using synthetic terraform plan JSONs.

Usage:
    python generate_training_data.py [--samples 15] [--seed 42]

Each plan JSON is:
    1. Generated in-memory with known drift pattern
    2. Features extracted via features.py
    3. Labelled and stored in SQLite via db.py
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from synthetic_data import GENERATORS, generate_plan
from features import extract_features, features_to_list
from db import init_db, save_training_sample, get_training_data


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic training data")
    parser.add_argument("--samples", type=int, default=15, help="Samples per drift type")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    init_db()

    drift_types = list(GENERATORS.keys())
    total = len(drift_types) * args.samples
    print(f"Generating {total} training samples ({args.samples} per type)...")
    print(f"Drift types: {', '.join(drift_types)}")
    print()

    for dtype in drift_types:
        print(f"[{dtype}] ", end="", flush=True)
        for i in range(args.samples):
            seed = args.seed + i
            plan = generate_plan(dtype, seed=seed)
            features = extract_features(plan)
            save_training_sample(dtype, features)
            print(".", end="", flush=True)
        print(f" {args.samples} samples")

    print()
    print("Verifying stored data...")
    rows = get_training_data()
    print(f"Total training samples in DB: {len(rows)}")
    print()

    by_type = {}
    for label, feats_json in rows:
        by_type[label] = by_type.get(label, 0) + 1
    for dtype, count in sorted(by_type.items()):
        print(f"  {dtype}: {count}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
