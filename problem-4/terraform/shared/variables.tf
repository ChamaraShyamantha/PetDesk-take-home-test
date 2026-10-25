variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "demo-app"
}

variable "github_repo" {
  type        = string
  description = "GitHub repository as owner@owner_id/name@repo_id, matching the OIDC sub claim"
}
