# Solutions Summary

## Problem 1 – IAM Access Control

### 1a. S3 Access Policy (`problem-1/s3-access-policy`)
An IAM policy that lets the user list all buckets and read, write and delete objects only in the `xyz-media` bucket. An explicit deny blocks deleting the bucket or changing its bucket policy.

### 1b. Admin Self-Service (`problem-1/admin-self-service`)
A policy that grants full administrative access to every service except IAM, with read-only IAM access on top. Users can still change their own password, rotate their own access keys and manage their own MFA device, while being unable to administer other users, roles or policies.

### 1c. Per-User Secrets (`problem-1/admin-self-service/per-user-secrets`)
A single policy that lets each user read only the Secrets Manager secret named after their own username (`<username>-rds-credentials`). The `${aws:username}` variable and an account condition keep users from reading anyone else's database credentials.

## Problem 2 – EC2 Bootstrap Script (`problem-2`)
An idempotent Bash script, run on every boot by a systemd service, installs the latest OpenJDK LTS if Java is missing, enables unattended security updates and installs the Datadog Agent. The API key is read at runtime from an SSM SecureString using a least-privilege instance role, and every run publishes a `BootstrapFailed` CloudWatch metric so failures across the fleet trigger an alarm.

## Problem 3 – Architecture Scenarios

### 3a. Static Website (`problem-3/static-website`)
The site is hosted in a private S3 bucket behind CloudFront with Origin Access Control, a free ACM certificate and Route 53 alias records, so there are no servers to manage and the cost is close to zero. A GitHub Actions pipeline syncs changes to S3 and invalidates the CloudFront cache on every push to `main`.

### 3b. S3 Cross-Region Move (`problem-3/s3-cross-region`)
Two buckets are moved from Sydney to Oregon with AWS DataSync in Basic mode, for a one-time cost of about $62 that I checked in the AWS Pricing Calculator. The copy is verified with DataSync checksums and task reports, then with object count and size comparisons, and finally with CloudWatch storage metrics.

### 3c. Cross-Cloud Transfer (`problem-3/cross-cloud-transfer`)
Google Cloud Datastream replicates a 20-million-row RDS MySQL table into BigQuery through binlog-based CDC: an initial backfill followed by ongoing changes, all defined in Terraform. The document covers MySQL-to-BigQuery type mapping and validates the result with Google's Data Validation Tool at the row-count, column-aggregate and row-hash levels.

### 3d. Scheduled Processing (`problem-3/scheduled-processing`)
The Python data-processing job runs as a Fargate task, orchestrated by Step Functions and triggered by EventBridge Scheduler every 6 hours, so compute is billed only while the job runs. Idempotent staging-table writes, overlap checks, a hard timeout, selective retries and SNS alerts handle failed or overrunning runs.

## Problem 4 – Containerised Web App on ECS (`problem-4`)
A Flask app served by Gunicorn behind Nginx is packaged in a multi-stage, non-root Docker image and deployed to ECS Fargate in private subnets behind an ALB with WAF and HTTPS. Terraform is split into a shared stack (ECR and GitHub OIDC deploy role) and an app stack with separate staging and production tfvars that deploy the same immutable image tag.

## Problem 6 – Security Group Open-Ingress Audit (`problem-6`)
A scheduled Lambda scans security groups in every enabled region for inbound rules open to `0.0.0.0/0` or `::/0` on any port other than 80/443, then emails a single report through SNS. It is deployed with Terraform, includes unit tests and a CloudWatch alarm for when the audit itself fails, and the README explains when AWS Config or Security Hub would be the better choice.
