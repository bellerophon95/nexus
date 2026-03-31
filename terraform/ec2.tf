resource "aws_iam_role" "ec2_role" {
  name = "nexus-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_readonly" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "nexus-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "nexus_app" {
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.nexus_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  # Note: Instance will install docker and docker-compose via User Data 
  # or you can provide a base AMI with them installed.
  user_data = <<-EOF
              #!/bin/bash
              apt-get update
              apt-get install -y docker.io docker-compose awscli
              systemctl start docker
              systemctl enable docker
              EOF

  tags = {
    Name = "nexus-app-server"
  }
}

resource "aws_eip" "nexus_eip" {
  instance = aws_instance.nexus_app.id
  domain   = "vpc"

  tags = {
    Name = "nexus-static-ip"
  }
}
