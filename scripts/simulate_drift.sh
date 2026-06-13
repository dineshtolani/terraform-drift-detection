#!/bin/bash
# simulate_drift.sh - Make manual changes to create drift
# Each drift type changes DIFFERENT resources so ML can distinguish them

set -e

AWS="aws --endpoint-url=http://localhost:4566 --region=us-east-1"
TERRAFORM_DIR="../terraform"

# Get bucket IDs from terraform output
BUCKET_ID=$(cd "$TERRAFORM_DIR" && terraform output -raw s3_bucket_id 2>/dev/null)
LOGS_BUCKET_ID=$(cd "$TERRAFORM_DIR" && terraform output -raw s3_logs_bucket_id 2>/dev/null)
ROLE_NAME=$(cd "$TERRAFORM_DIR" && terraform output -raw iam_role_arn 2>/dev/null | awk -F/ '{print $NF}')

DRIFT_TYPE=${1:-"no_drift"}

echo "=== Simulating Drift: $DRIFT_TYPE ==="

case $DRIFT_TYPE in
  security)
    # Only change PUBLIC ACCESS BLOCK - leaves everything else
    $AWS s3api put-public-access-block \
      --bucket "$BUCKET_ID" \
      --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
    echo "  Public access block opened (security risk)"
    ;;

  config)
    # Change ENCRYPTION + VERSIONING - leaves public access alone
    $AWS s3api delete-bucket-encryption --bucket "$BUCKET_ID" 2>/dev/null || true
    echo "  Encryption disabled (config change)"

    $AWS s3api put-bucket-versioning \
      --bucket "$BUCKET_ID" \
      --versioning-configuration "Status=Suspended"
    echo "  Versioning suspended (config change)"
    ;;

  tag)
    # Change TAGS on both buckets - nothing else
    $AWS s3api put-bucket-tagging \
      --bucket "$BUCKET_ID" \
      --tagging "TagSet=[{Key=Environment,Value=production},{Key=Owner,Value=manual}]"
    echo "  Tags changed on data bucket"

    $AWS s3api put-bucket-tagging \
      --bucket "$LOGS_BUCKET_ID" \
      --tagging "TagSet=[{Key=Environment,Value=production},{Key=Owner,Value=manual}]"
    echo "  Tags changed on logs bucket"
    ;;

  deletion)
    # Delete IAM policy attachment - different resource type entirely
    POLICY_ARN="arn:aws:iam::000000000000:policy/drift-detector-s3-access"
    $AWS iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN" 2>/dev/null || true
    echo "  IAM policy detached from role (deletion drift)"
    ;;

  no_drift)
    echo "  No drift simulated. Resources are clean."
    ;;
esac

echo "=== Drift simulation complete ==="
