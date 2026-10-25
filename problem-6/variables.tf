variable "region" {
  description = "Region to deploy the Lambda and SNS topic into (the audit itself scans all enabled regions)"
  type        = string
  default     = "us-east-1"
}

variable "notification_emails" {
  description = "Email addresses to receive the report; each must confirm the SNS subscription"
  type        = list(string)
}

variable "schedule_expression" {
  description = "EventBridge schedule, e.g. \"rate(20 minutes)\" or \"cron(0 0 * * ? *)\" for daily at 00:00 UTC"
  type        = string
  default     = "cron(0 0 * * ? *)"
}

variable "notify_when_clean" {
  description = "Send an email even when there are no findings (noisy on a 20-minute schedule)"
  type        = bool
  default     = false
}
