output "s3_bucket_id" {
  description = "Main S3 bucket ID"
  value       = aws_s3_bucket.data.id
}

output "s3_logs_bucket_id" {
  description = "Logs S3 bucket ID"
  value       = aws_s3_bucket.logs.id
}

output "iam_role_arn" {
  description = "App IAM role ARN"
  value       = aws_iam_role.app.arn
}

output "iam_readonly_role_arn" {
  description = "Read-only IAM role ARN"
  value       = aws_iam_role.read_only.arn
}

output "iam_role_name" {
  description = "App IAM role name"
  value       = aws_iam_role.app.name
}

output "iam_s3_policy_arn" {
  description = "S3 access policy ARN"
  value       = aws_iam_policy.s3_access.arn
}
