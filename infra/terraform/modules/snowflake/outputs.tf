output "database_name" {
  value = snowflake_database.agentevalos.name
}

output "app_role_name" {
  value = snowflake_account_role.app_role.name
}
