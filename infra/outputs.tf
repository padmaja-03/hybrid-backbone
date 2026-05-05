# infra/outputs.tf

output "aws_region" {
  value = var.aws_region
}

output "kms_key_arn" {
  value = aws_kms_key.backbone.arn
  sensitive = true
}

output "vpc_id" {
  value = aws_vpc.main.id
}