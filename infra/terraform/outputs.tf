output "snowflake_database" {
  value = module.snowflake.database_name
}

output "postgres_endpoint" {
  value = module.postgres.endpoint
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}
