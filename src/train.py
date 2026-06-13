#!/usr/bin/env python3
"""Train Random Forest classifier on drift detection data.

Usage:
    python train.py [--model-dir ../models] [--mlflow]
"""

import argparse
import json
import os
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report

sys.path.insert(0, os.path.dirname(__file__))
from features import features_to_list, FEATURE_NAMES
from db import get_training_data

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")
MLFLOW_EXPERIMENT_NAME = "terraform-drift-detector"


def main():
    parser = argparse.ArgumentParser(description="Train drift classifier")
    parser.add_argument("--model-dir", default=os.path.join(os.path.dirname(__file__), "..", "models"))
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=10)
    parser.add_argument("--mlflow", action="store_true", help="Log to MLflow")
    args = parser.parse_args()

    os.makedirs(args.model_dir, exist_ok=True)

    rows = get_training_data()
    if not rows:
        print("No training data found. Run generate_training_data.py first.")
        sys.exit(1)

    labels = []
    X = []
    for label, feats_json in rows:
        feats = json.loads(feats_json)
        X.append(features_to_list(feats))
        labels.append(label)

    X = np.array(X)
    y = np.array(labels)

    class_names = sorted(set(labels))
    print(f"Training samples: {len(X)}")
    print(f"Features: {len(FEATURE_NAMES)}")
    print(f"Classes: {class_names}")

    for cls in class_names:
        count = sum(1 for l in labels if l == cls)
        print(f"  {cls}: {count}")

    print()
    print("Cross-validation (5-fold stratified)...")
    model = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        random_state=42,
        class_weight="balanced",
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
    cv_mean = scores.mean()
    cv_std = scores.std()
    print(f"  CV Accuracy: {cv_mean:.3f} +/- {cv_std:.3f}")
    print(f"  Per fold: {[f'{s:.3f}' for s in scores]}")

    print()
    print("Training final model on all data...")
    model.fit(X, y)

    y_pred = model.predict(X)
    print()
    print("Classification Report (training set):")
    print(classification_report(y, y_pred))

    model_path = os.path.join(args.model_dir, "drift_classifier.joblib")
    joblib.dump(model, model_path)
    print(f"Model saved to: {model_path}")

    print()
    print("Top 10 Feature Importances:")
    importances = sorted(zip(FEATURE_NAMES, model.feature_importances_), key=lambda x: -x[1])
    for name, imp in importances[:10]:
        print(f"  {name:<30s} {imp:.4f}")

    if args.mlflow:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

        with mlflow.start_run() as run:
            mlflow.log_params({
                "n_estimators": args.n_estimators,
                "max_depth": args.max_depth,
                "n_samples": len(X),
                "n_features": len(FEATURE_NAMES),
                "n_classes": len(class_names),
                "class_names": ",".join(class_names),
            })
            mlflow.log_metrics({
                "cv_accuracy_mean": cv_mean,
                "cv_accuracy_std": cv_std,
            })
            for name, imp in importances:
                mlflow.log_metric(f"importance_{name}", imp)
            mlflow.sklearn.log_model(model, artifact_path="model", input_example=X[:1])
            mlflow.log_artifact(model_path, artifact_path="joblib_model")
            print()
            print(f"MLflow run: {mlflow.get_tracking_uri()}/#/experiments/"
                  f"{run.info.experiment_id}/runs/{run.info.run_id}")


if __name__ == "__main__":
    main()
