# Security group open-ingress audit

## Build this, or use AWS Config / Security Hub?

For a production account I would use AWS Config instead of maintaining this Lambda: the managed `restricted-common-ports` rule (or a small custom rule that allows only 80/443) evaluates security groups as soon as they change rather than on a schedule, and Security Hub adds finding history, multi-account aggregation through AWS Organizations, and automated remediation via EventBridge with no code to own. I would only build this custom Lambda when Config isn't enabled and its per-evaluation cost matters, or when all that's needed is a single, simple scheduled email for one account.
