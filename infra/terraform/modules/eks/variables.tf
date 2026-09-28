variable "cluster_name" { type = string }
variable "environment" { type = string }
variable "subnet_ids" {
  type    = list(string)
  default = []
}
