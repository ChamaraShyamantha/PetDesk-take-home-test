variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "demo-app"
}

variable "environment" {
  type = string
}

variable "domain_name" {
  type    = string
  default = ""
}

variable "hosted_zone_id" {
  type    = string
  default = ""
}

variable "image_tag" {
  type = string
}

variable "desired_count" {
  type    = number
  default = 2
}
