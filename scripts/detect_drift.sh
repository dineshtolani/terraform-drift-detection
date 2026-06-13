#!/bin/bash
# detect_drift.sh - Run terraform plan and save JSON output
# Usage: ./detect_drift.sh <drift_type>

set -e

DRIFT_TYPE=${1:-"unknown"}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RAW_DIR="../data/raw"
PLAN_FILE="$RAW_DIR/plan_${DRIFT_TYPE}_${TIMESTAMP}.json"

mkdir -p "$RAW_DIR"

echo "=== Running Terraform Drift Detection ==="

cd ../terraform

# Step 1: Refresh state to match current reality
terraform apply -refresh-only -auto-approve 2>/dev/null

# Step 2: Now run plan to see what drifts from desired state
terraform plan -no-color -out=tfplan 2>/dev/null
terraform show -json tfplan > "$PLAN_FILE"
rm -f tfplan

echo "Plan saved to: $PLAN_FILE"
echo "=== Drift detection complete ==="
