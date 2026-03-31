variable "aws_region" {
  description = "Target AWS region"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance size"
  type        = string
  default     = "t3a.medium" # Cheapest 4GB instance in us-east-1
}

variable "ami_id" {
  description = "Ubuntu 22.04 LTS AMI"
  type        = string
  default     = "ami-0c7217cdde317cfec" # Replace with valid regional AMI
}

output "instance_id" {
  value = aws_instance.nexus_app.id
}

output "public_ip" {
  value = aws_eip.nexus_eip.public_ip
}

output "ecr_backend_url" {
  value = aws_ecr_repository.nexus_backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.nexus_frontend.repository_url
}
