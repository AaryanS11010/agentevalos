variable "environment" {
  description = "Deployment environment (dev | prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "snowflake_role" {
  type    = string
  default = "SYSADMIN"
}

variable "snowflake_database" {
  type    = string
  default = "AGENTEVALOS"
}

variable "snowflake_warehouse" {
  type    = string
  default = "AGENTEVALOS_WH"
}

variable "postgres_db_name" {
  type    = string
  default = "agentevalos"
}

variable "snowflake_app_user" {
  description = "Snowflake user eval-engine/agent-orchestrator connect as (SNOWFLAKE_USER in .env). AGENTEVALOS_APP_ROLE is granted to this user. Leave empty to skip and assign it manually."
  type        = string
  default     = ""
}
