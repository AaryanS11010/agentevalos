resource "aws_db_instance" "agentevalos" {
  identifier                  = "agentevalos-${var.environment}"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = var.environment == "prod" ? "db.r6g.large" : "db.t4g.micro"
  allocated_storage           = var.environment == "prod" ? 100 : 20
  db_name                     = var.db_name
  username                    = "agentevalos"
  manage_master_user_password = true
  skip_final_snapshot         = var.environment != "prod"
  publicly_accessible         = false

  tags = {
    Project     = "agentevalos"
    Environment = var.environment
  }
}
