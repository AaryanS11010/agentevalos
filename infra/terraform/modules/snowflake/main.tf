terraform {
  required_providers {
    # Child modules need their own required_providers entry to resolve a
    # non-default-namespace provider like this one — without it, Terraform's
    # automatic source resolution guesses hashicorp/snowflake, which doesn't exist.
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 0.94"
    }
  }
}

resource "snowflake_warehouse" "agentevalos" {
  name           = var.warehouse_name
  warehouse_size = "XSMALL"
  auto_suspend   = 60
  auto_resume    = true
  comment        = "AgentEvalOS eval-engine benchmarking warehouse (${var.environment})"
}

resource "snowflake_database" "agentevalos" {
  name    = var.database_name
  comment = "AgentEvalOS eval datasets, model leaderboard, warehouse-scale analytics (${var.environment})"
}

resource "snowflake_schema" "evals" {
  database = snowflake_database.agentevalos.name
  name     = "EVALS"
  comment  = "Model leaderboard, eval results, benchmark datasets"
}

# snowflake_role is deprecated in favor of snowflake_account_role (as of provider
# ~0.94); the old snowflake_*_grant resources this module used to use (database/
# schema/warehouse/role grants) were removed entirely in favor of the single unified
# snowflake_grant_privileges_to_account_role resource below.
resource "snowflake_account_role" "app_role" {
  name    = "AGENTEVALOS_APP_ROLE"
  comment = "Role used by eval-engine's Snowflake connector"
}

resource "snowflake_grant_privileges_to_account_role" "app_role_db_usage" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.agentevalos.name
  }
}

# scripts/seed_snowflake.py and app/snowflake/client.py::ensure_schema() create the
# per-industry schemas (FINANCE, HEALTHCARE) at runtime, so the app role needs
# CREATE SCHEMA at the database level, not just USAGE.
resource "snowflake_grant_privileges_to_account_role" "app_role_db_create_schema" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.agentevalos.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "app_role_schema_usage" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "\"${snowflake_database.agentevalos.name}\".\"${snowflake_schema.evals.name}\""
  }
}

# ensure_schema()'s DDL creates MODEL_LEADERBOARD/EVAL_RESULTS tables and the
# MODEL_STAGE/UDF_STAGE stages under EVALS at runtime.
resource "snowflake_grant_privileges_to_account_role" "app_role_schema_create_table" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["CREATE TABLE"]
  on_schema {
    schema_name = "\"${snowflake_database.agentevalos.name}\".\"${snowflake_schema.evals.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "app_role_schema_create_stage" {
  account_role_name = snowflake_account_role.app_role.name
  privileges        = ["CREATE STAGE"]
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

# Without this, the role exists but nobody can assume it — SNOWFLAKE_USER in .env
# needs AGENTEVALOS_APP_ROLE granted to actually connect as it. Optional since some
# orgs grant roles to users out of band from Terraform.
resource "snowflake_grant_account_role" "app_role_to_user" {
  count     = var.app_role_user != "" ? 1 : 0
  role_name = snowflake_account_role.app_role.name
  user_name = var.app_role_user
}
