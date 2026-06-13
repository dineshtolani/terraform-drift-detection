#!/bin/bash
# generate_data.sh - Auto-generate training data
# Runs the simulate→detect→restore cycle for each drift type

set -e

DRIFT_TYPES=("security" "config" "tag" "deletion" "no_drift")
SAMPLES_PER_TYPE=${1:-15}  # Default 15 per type = 75 total
TERRAFORM_DIR="../terraform"
SCRIPTS_DIR="."
RAW_DIR="../data/raw"

mkdir -p "$RAW_DIR"

echo "=========================================="
echo "  Training Data Generation"
echo "  Samples per type: $SAMPLES_PER_TYPE"
echo "  Total samples: $((SAMPLES_PER_TYPE * ${#DRIFT_TYPES[@]}))"
echo "=========================================="

for DRIFT_TYPE in "${DRIFT_TYPES[@]}"; do
    echo ""
    echo "========================"
    echo "  Generating: $DRIFT_TYPE"
    echo "========================"

    for i in $(seq 1 $SAMPLES_PER_TYPE); do
        echo ""
        echo "--- Sample $i of $SAMPLES_PER_TYPE ---"

        # Only simulate drift if not no_drift
        if [ "$DRIFT_TYPE" != "no_drift" ]; then
            cd "$SCRIPTS_DIR"
            bash simulate_drift.sh "$DRIFT_TYPE" >/dev/null 2>&1
            cd - >/dev/null
        fi

        # Detect drift (captures terraform plan JSON)
        cd "$SCRIPTS_DIR"
        bash detect_drift.sh "$DRIFT_TYPE" >/dev/null 2>&1
        cd - >/dev/null

        # Extract features and save to DB
        PLAN_FILE=$(ls -t "$RAW_DIR"/plan_${DRIFT_TYPE}_*.json | head -1)
        if [ -f "$PLAN_FILE" ]; then
            python3 ../src/ingest.py "$PLAN_FILE" "$DRIFT_TYPE"
            echo "  Ingested: $(basename $PLAN_FILE) -> DB"
            # Remove raw file after processing
            rm "$PLAN_FILE"
        fi

        # Restore clean state
        cd "$TERRAFORM_DIR"
        terraform apply -auto-approve >/dev/null 2>&1
        cd - >/dev/null

        echo "  Restored clean state"
    done
done

echo ""
echo "=========================================="
echo "  Data Generation Complete!"
echo "=========================================="
python3 ../src/db.py get_training_data
