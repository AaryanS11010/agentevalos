variable "database_name" { type = string }
variable "warehouse_name" { type = string }
variable "environment" { type = string }

variable "app_role_user" {
  description = "Snowflake user to grant AGENTEVALOS_APP_ROLE to (the service account eval-engine/agent-orchestrator connect as). Leave empty to skip the grant and assign it manually."
  type        = string
  default     = ""
}
