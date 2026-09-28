# Sets up the Snowflake side of the project: a warehouse, a database, and a
# role the app connects as. Run with: terraform init && terraform plan

terraform {
  required_version = ">= 1.7"
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 0.94"
    }
  }
}

provider "snowflake" {
  role = var.snowflake_role
}

resource "snowflake_warehouse" "agentevalos" {
  name           = var.warehouse_name
  warehouse_size = "XSMALL"
  auto_suspend   = 60
  auto_resume    = true
}

resource "snowflake_database" "agentevalos" {
  name = var.database_name
}

resource "snowflake_schema" "evals" {
  database = snowflake_database.agentevalos.name
  name     = "EVALS"
}

resource "snowflake_account_role" "app_role" {
  name    = "AGENTEVALOS_APP_ROLE"
  comment = "Role the app connects with"
}

resource "snowflake_grant_privileges_to_account_role" "app_role_db" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.agentevalos.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "app_role_schema" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE STAGE"]
  on_schema {
    schema_name = "\"${snowflake_database.agentevalos.name}\".\"${snowflake_schema.evals.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "app_role_warehouse" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.agentevalos.name
  }
}
