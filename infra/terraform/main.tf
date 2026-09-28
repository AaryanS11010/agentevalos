terraform {
  required_version = ">= 1.7"
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 0.94"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # backend "s3" {} # configure per environment in environments/<env>/backend.tfvars
}

provider "snowflake" {
  role = var.snowflake_role
}

provider "aws" {
  region = var.aws_region
}

module "snowflake" {
  source         = "./modules/snowflake"
  database_name  = var.snowflake_database
  warehouse_name = var.snowflake_warehouse
  environment    = var.environment
  app_role_user  = var.snowflake_app_user
}

module "postgres" {
  source      = "./modules/postgres"
  environment = var.environment
  db_name     = var.postgres_db_name
}

module "eks" {
  source       = "./modules/eks"
  environment  = var.environment
  cluster_name = "agentevalos-${var.environment}"
}
