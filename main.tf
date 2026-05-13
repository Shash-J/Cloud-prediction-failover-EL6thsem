provider "aws" {
  region = "us-east-1" # You can change this to your preferred region (e.g., ap-south-1 for Mumbai)
}

# Generate a new SSH key pair automatically
resource "tls_private_key" "pk" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "kp" {
  key_name   = "cloud-failover-key"
  public_key = tls_private_key.pk.public_key_openssh
}

# Save the private key locally so you can SSH into the instance
resource "local_file" "ssh_key" {
  filename        = "${path.module}/cloud-failover-key.pem"
  content         = tls_private_key.pk.private_key_pem
  file_permission = "0400"
}

# Create a Security Group to allow HTTP (for our app) and SSH (for our stress testing)
resource "aws_security_group" "web_sg" {
  name        = "cloud-failover-web-sg"
  description = "Allow SSH and HTTP inbound traffic"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8081
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Fetch the latest Ubuntu 22.04 AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  owners = ["099720109477"] # Canonical
}

# Create the EC2 instance
resource "aws_instance" "app_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro" # Free tier eligible
  key_name               = aws_key_pair.kp.key_name
  vpc_security_group_ids = [aws_security_group.web_sg.id]

  # User Data script to install Python and NGINX (our example app)
  user_data = <<-EOF
              #!/bin/bash
              apt-get update
              apt-get install -y python3 python3-pip nginx
              systemctl start nginx
              systemctl enable nginx
              EOF

  tags = {
    Name = "CloudFailoverPoC"
  }
}

# Output the public IP address so we can connect to it
output "instance_public_ip" {
  value = aws_instance.app_server.public_ip
}
