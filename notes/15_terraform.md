# Terraform — Complete Notes from Scratch

---

## 1. What Is Terraform

Infrastructure as Code (IaC) means treating your cloud infrastructure — S3 buckets, IAM roles, Glue jobs, RDS instances — the same way you treat application code: version controlled, peer-reviewed, tested, and deployed in a repeatable way. Before IaC, infrastructure was "click-ops" — someone logged into the AWS console and manually configured resources. The problem: no audit trail, no reproducibility, "works in prod but not in staging" drift.

Terraform takes a declarative approach: you describe the desired end state ("I want an S3 bucket named X with these settings"), and Terraform figures out what API calls to make to get there from the current state.

```
Infrastructure as Code (IaC) tool by HashiCorp.
- Define infrastructure in HCL (HashiCorp Configuration Language)
- Works with 1000+ providers: AWS, Azure, GCP, Kubernetes, Snowflake...
- Idempotent: apply same config multiple times = same result
- Tracks state: knows what exists vs what's defined

Why Terraform (vs CloudFormation):
- Multi-cloud: one tool for AWS + Azure + GCP
- Larger community, more modules
- More readable HCL vs JSON/YAML CloudFormation
- State management + plan/apply workflow

Core workflow:
terraform init   → download providers
terraform plan   → preview changes
terraform apply  → create/update infrastructure
terraform destroy → tear down
```

> **💡 Interview tip:** "What's the Terraform workflow?" — init, plan, apply is the answer. But the deeper answer is: `plan` is where the value is. It computes an execution diff (what will be created, modified, destroyed) by comparing your desired config against the state file. Always show a `plan` to your team before applying in production — it's the equivalent of a `git diff` for infrastructure.

> **🌍 Real world:** In most DE teams, Terraform runs in CI/CD (Atlantis, Terraform Cloud, or GitHub Actions). A PR to the infra repo triggers `terraform plan` and posts the output as a PR comment for review. Merge triggers `terraform apply`. This gives you peer review, audit trail, and reproducibility for every infrastructure change — the same workflow as application code.

---

## 2. HCL Syntax

HCL (HashiCorp Configuration Language) is Terraform's declarative config language. Every resource follows the same pattern: block type, resource type, logical name, then key-value arguments inside. The logical name is how you reference the resource elsewhere in your config — it never becomes the actual resource name in AWS unless you use it explicitly.

```hcl
# Comment

# Block syntax
resource "aws_s3_bucket" "data_lake" {    # type "resource", label "aws_s3_bucket", name "data_lake"
  bucket = "my-data-lake-dev"             # argument = value
  
  tags = {                                # map/object value
    Environment = "dev"
    Team        = "data-engineering"
  }
}

# Reference: resource_type.name.attribute
# aws_s3_bucket.data_lake.bucket         → "my-data-lake-dev"
# aws_s3_bucket.data_lake.arn            → "arn:aws:s3:::my-data-lake-dev"
# aws_s3_bucket.data_lake.id             → same as bucket name for S3
```

> **💡 Interview tip:** The reference syntax `resource_type.name.attribute` creates an implicit dependency graph in Terraform. If resource B references resource A, Terraform automatically creates A before B, without you having to declare a `depends_on`. Terraform builds a DAG (directed acyclic graph) of resources and parallelises independent ones. This is why Terraform applies can be fast — it provisions many resources simultaneously.

---

## 3. Providers

Providers are the bridge between Terraform and the underlying APIs — each provider is a plugin that knows how to authenticate to and call an API (AWS, Snowflake, GitHub, etc.). The backend configuration in this block is equally important: it defines where the Terraform state file lives. For any team environment, this must be remote.

```hcl
# providers.tf
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"     # ~> 5.0 = >= 5.0, < 6.0
    }
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.70"
    }
  }
  
  # Remote state in S3
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "data-platform/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"    # prevents concurrent applies
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
  
  default_tags {
    tags = {
      ManagedBy   = "Terraform"
      Project     = "data-platform"
      Environment = var.environment
    }
  }
}

# Multiple provider configurations (different regions/accounts)
provider "aws" {
  alias  = "us_west"
  region = "us-west-2"
}

resource "aws_s3_bucket" "west_bucket" {
  provider = aws.us_west
  bucket   = "my-west-bucket"
}
```

> **🌍 Real world:** The DynamoDB lock table (`dynamodb_table = "terraform-locks"`) is not optional in a team environment. Without it, two engineers running `terraform apply` simultaneously will corrupt the state file — both will read the current state, compute a plan based on it, and then both try to write their updated state, with the second writer overwriting the first's changes. The DynamoDB lock creates a mutex: the first `apply` acquires the lock, and the second waits (or fails with a clear "state locked" error).

---

## 4. Variables and Outputs

Variables are how you parameterise Terraform configs so the same code can be applied to dev, staging, and prod with different values. Outputs are how you expose values from one Terraform module or workspace to another — or just for human reference after an apply.

```hcl
# variables.tf
variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "glue_workers" {
  type    = number
  default = 5
}

variable "enable_encryption" {
  type    = bool
  default = true
}

# List variable
variable "allowed_ips" {
  type    = list(string)
  default = ["10.0.0.0/8"]
}
```

```hcl
# outputs.tf
output "bucket_name" {
  value       = aws_s3_bucket.data_lake.bucket
  description = "Data lake S3 bucket name"
}

output "glue_role_arn" {
  value = aws_iam_role.glue_role.arn
}

output "database_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = true   # hide from output (not from state file!)
}
```

```hcl
# terraform.tfvars  (auto-loaded)
environment   = "prod"
region        = "us-east-1"
glue_workers  = 10

# Or pass at runtime:
terraform apply -var="environment=prod" -var="region=us-east-1"
terraform apply -var-file="prod.tfvars"
```

> **💡 Interview tip:** `sensitive = true` on an output hides the value from terminal output — but it does NOT encrypt it in the state file. The state file contains all sensitive values in plain text, which is why the state bucket should have encryption, strict IAM policies, and access logging enabled. Never store state locally in a shared team environment.

---

## 5. Locals

Locals let you compute values once and reuse them — they're the DRY (Don't Repeat Yourself) principle applied to Terraform. A common use is building a consistent name prefix (`${var.project}-${var.environment}`) and a common tags map that gets merged with resource-specific tags.

```hcl
# Computed values, used to avoid repetition
locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "Terraform"
  })
  
  # Conditional
  is_prod = var.environment == "prod"
  
  # Function usage
  bucket_name = lower(replace("${local.name_prefix}-data-lake", "_", "-"))
}

resource "aws_s3_bucket" "data_lake" {
  bucket = local.bucket_name
  tags   = local.common_tags
}
```

> **🌍 Real world:** The `local.is_prod` pattern is very common for prod vs non-prod configuration differences — instance sizes, multi-AZ, backup retention, deletion protection. Rather than duplicating resource blocks for prod and dev, you use locals to conditionally set values: `instance_class = local.is_prod ? "db.r6g.large" : "db.t3.micro"`. This keeps the code DRY and makes the prod/dev differences explicit and auditable.

---

## 6. Data Sources

Data sources let you query existing AWS resources without managing them with Terraform. This is crucial for referencing infrastructure that already exists (was created outside Terraform, or is managed by a different Terraform workspace) — like an existing VPC, a Secrets Manager secret, or the current AWS account ID.

```hcl
# Read existing resources (don't manage them)
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Use the values
resource "aws_s3_bucket" "logs" {
  bucket = "my-logs-${data.aws_caller_identity.current.account_id}"
}

# Get existing VPC
data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = ["main-vpc"]
  }
}

# Get latest Amazon Linux AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# Fetch SSM Parameter Store value (secrets)
data "aws_ssm_parameter" "db_password" {
  name            = "/myapp/db/password"
  with_decryption = true
}
```

> **💡 Interview tip:** Data sources are how you bridge between Terraform workspaces or managed/unmanaged infrastructure. A common pattern: the networking team manages the VPC in their own Terraform workspace and exports the VPC ID as an output. Your data platform workspace reads it with a `data "terraform_remote_state"` or a `data "aws_vpc"` — you reference the VPC without owning it or risking accidentally modifying it.

---

## 7. Data Platform Resources Example

This is what a real-world data platform looks like in Terraform — S3 data lake with lifecycle policies, IAM roles with least-privilege policies, a Glue job, and an RDS instance that's configured differently in prod vs dev.

```hcl
# S3 Data Lake
resource "aws_s3_bucket" "data_lake" {
  bucket = "${local.name_prefix}-data-lake"
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  
  rule {
    id     = "archive-old-data"
    status = "Enabled"
    
    filter {
      prefix = "landing/"
    }
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    
    expiration {
      days = 365
    }
  }
}

# IAM Role for Glue
resource "aws_iam_role" "glue_role" {
  name = "${local.name_prefix}-glue-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3_access" {
  name = "s3-access"
  role = aws_iam_role.glue_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.data_lake.arn,
        "${aws_s3_bucket.data_lake.arn}/*"
      ]
    }]
  })
}

# Glue Job
resource "aws_glue_job" "daily_etl" {
  name     = "${local.name_prefix}-daily-etl"
  role_arn = aws_iam_role.glue_role.arn
  
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = var.glue_workers
  
  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.data_lake.bucket}/scripts/etl.py"
    python_version  = "3"
  }
  
  default_arguments = {
    "--job-bookmark-option"      = "job-bookmark-enable"
    "--enable-metrics"           = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                  = "s3://${aws_s3_bucket.data_lake.bucket}/tmp/"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier        = "${local.name_prefix}-postgres"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = local.is_prod ? "db.r6g.large" : "db.t3.medium"
  allocated_storage = local.is_prod ? 100 : 20
  storage_encrypted = true
  
  db_name  = "dataplatform"
  username = "admin"
  password = data.aws_ssm_parameter.db_password.value
  
  multi_az               = local.is_prod
  deletion_protection    = local.is_prod
  skip_final_snapshot    = !local.is_prod
  
  backup_retention_period = local.is_prod ? 14 : 1
  
  tags = local.common_tags
}
```

> **🌍 Real world:** The `deletion_protection = local.is_prod` line is a safeguard that has saved production databases from accidental `terraform destroy` many times. When deletion protection is enabled, Terraform will refuse to destroy the RDS instance — you have to disable it explicitly first, which forces a deliberate "yes, I really want to delete this" step.

---

## 8. Count and for_each — Dynamic Resources

Both `count` and `for_each` let you create multiple resources from a single block, but they have an important difference in how they track resources. `count` creates resources indexed by integer (0, 1, 2...). `for_each` creates resources keyed by string. When you remove an item from the middle of a `count` list, all higher-indexed resources shift — Terraform sees this as "destroy resource[1], create new resource[1] with different config, rename resource[2] to resource[1]". With `for_each`, removing `"staging"` from a map only affects the `staging` resource — others are untouched.

Think of `count` like a Python list and `for_each` like a Python dict. Deleting the middle element of a list shifts all subsequent indices; deleting a key from a dict doesn't affect any other key.

```hcl
# count — create N identical resources
variable "environment_names" {
  default = ["dev", "staging", "prod"]
}

resource "aws_s3_bucket" "envs" {
  count  = length(var.environment_names)
  bucket = "my-data-${var.environment_names[count.index]}"
}

# Reference: aws_s3_bucket.envs[0].bucket, [1], [2]

# for_each — create resource per map/set item (better for most cases)
variable "buckets" {
  default = {
    landing  = "landing zone for raw data"
    raw      = "cleaned raw data"
    curated  = "business-ready data"
  }
}

resource "aws_s3_bucket" "layers" {
  for_each = var.buckets
  bucket   = "${local.name_prefix}-${each.key}"
  
  tags = {
    Purpose = each.value
  }
}

# Reference: aws_s3_bucket.layers["landing"].bucket
# for_each is better than count when:
# - You might remove an item from the middle (count[1] would shift)
# - Each item has distinct properties
```

> **💡 Interview tip:** "When do you use `for_each` vs `count`?" is a classic Terraform interview question. The answer: prefer `for_each` almost always. `count` is fine for creating N identical resources (like N identical worker nodes). `for_each` is better when resources have distinct identities or when you might add/remove specific items — because removing item at index 1 from a `count` list causes cascading destroy/recreate of all higher-indexed resources, which can be destructive in production.

---

## 9. Modules

Modules are Terraform's DRY principle for infrastructure. Instead of copy-pasting the same S3 + lifecycle + versioning + policy block for every environment, you write it once as a module and call it with different variables. This is the difference between a 2,000-line monolith and a clean, maintainable infrastructure codebase.

Modules also serve as the boundary for abstractions: a `data-lake` module encapsulates all the AWS resources needed for a data lake, exposing only the inputs (name, environment, retention policy) and outputs (ARN, bucket name) that callers need to know about.

```hcl
# Reusable modules — avoid copy-paste across environments

# modules/data-lake/main.tf
resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name
}
resource "aws_s3_bucket_versioning" "versioning" { ... }

# modules/data-lake/variables.tf
variable "bucket_name" { type = string }
variable "environment" { type = string }

# modules/data-lake/outputs.tf
output "bucket_arn" { value = aws_s3_bucket.bucket.arn }
```

```hcl
# environments/prod/main.tf — use the module
module "data_lake" {
  source = "../../modules/data-lake"     # local path
  # Or: source = "git::https://github.com/org/tf-modules//data-lake?ref=v1.0.0"
  # Or: source = "hashicorp/consul/aws"  # Terraform Registry
  
  bucket_name = "my-prod-data-lake"
  environment = "prod"
}

# Use module output
resource "aws_glue_job" "etl" {
  # ...
  default_arguments = {
    "--bucket_arn" = module.data_lake.bucket_arn
  }
}
```

> **🌍 Real world:** Large data platform teams maintain a private Terraform module registry (Git repo with versioned tags, or Terraform Cloud private registry). Teams consume modules like `source = "git::https://github.com/org/tf-modules//glue-job?ref=v2.1.0"`. This means one team owns the Glue job module, handles security updates and best practices, and all teams get the benefit automatically by bumping the version pin. This is treating infra modules exactly like library dependencies.

---

## 10. State Management

The Terraform state file is Terraform's memory. It records every resource Terraform has created, along with all their attributes (IDs, ARNs, DNS names, etc.). Terraform needs this to compute the diff between "what exists" and "what you want" during `terraform plan`. Without state, Terraform would have no idea what's already been created.

The state file is not optional, not ignorable, and not something to edit manually. Lose the state file and you lose Terraform's ability to manage your existing infrastructure — you'd either need to recreate everything or painstakingly `import` every resource. Store it in S3 with DynamoDB locking. Always.

```
terraform.tfstate — JSON file tracking what Terraform created
- Never edit manually
- Contains sensitive values (DB passwords, etc.)

Local state:
- Fine for personal projects
- BAD for teams — file conflicts, no locking

Remote state (required for teams):
- S3 + DynamoDB (AWS)
- Terraform Cloud
- GCS (Google)

DynamoDB locking:
- Prevents two people running apply simultaneously
- Table: partition key = "LockID" (string)

terraform state commands:
terraform state list              # list all managed resources
terraform state show aws_s3_bucket.data_lake  # inspect resource
terraform state rm aws_s3_bucket.data_lake    # remove from state (don't destroy)
terraform state mv src dst        # rename resource in state (after refactor)
terraform import aws_s3_bucket.existing my-existing-bucket  # import existing resource
```

> **💡 Interview tip:** "How do you bring existing AWS resources under Terraform management without recreating them?" — `terraform import`. You write the resource block in HCL (describing the desired state), then run `terraform import resource_type.name existing-resource-id`. Terraform reads the actual resource state and writes it to the state file. Then you run `terraform plan` — ideally it shows no changes (your HCL matches reality). If it shows changes, those are configuration drifts you need to reconcile. This is a common task when inheriting legacy infrastructure.

> **🌍 Real world:** `terraform state rm` (remove from state without destroying the real resource) is useful when you want to stop managing something with Terraform — perhaps moving it to a different workspace or a different tool. The resource continues to exist in AWS; Terraform just forgets it. Use with care: on the next `terraform plan`, Terraform will see the resource in your config but not in state and try to create a new one (failing because it already exists).

---

## 11. Workspaces

Workspaces let you maintain multiple independent state files from the same Terraform configuration directory. The most common use is managing multiple environments (dev/staging/prod) without separate directories, using `terraform.workspace` to inject the environment name into resource names and configurations.

```bash
# Workspaces = multiple state files from same config
# Use for: different environments (dev/staging/prod)

terraform workspace new staging
terraform workspace select staging
terraform workspace list

# In config:
resource "aws_s3_bucket" "data_lake" {
  bucket = "my-data-lake-${terraform.workspace}"  # my-data-lake-staging
}
```

> **💡 Interview tip:** Workspaces vs separate directories for environments is a contested design choice in the Terraform community. Workspaces share the same configuration code — good for keeping envs in sync, risky if a change intended for dev accidentally destroys prod (same state prefix, different state files but same backend bucket). Separate environment directories (with shared modules) are safer for prod isolation. Many teams use directories for environment separation and workspaces only for ephemeral feature environments.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| HCL | Resource blocks, argument = value, reference via type.name.attr |
| init | Download providers, configure backend |
| plan | Dry-run — shows what will be created/changed/destroyed |
| apply | Execute the plan — creates real infrastructure |
| State | JSON record of what exists — store remotely in S3 |
| DynamoDB lock | Prevents concurrent applies — required for teams |
| Variables | Parameterize config — set via .tfvars or -var flag |
| Locals | Computed values, avoid repetition |
| Data sources | Read existing resources without managing them |
| for_each | Better than count — keyed resources, stable plan on changes |
| Modules | Reusable config blocks — avoid copy-paste between envs |
| terraform import | Bring existing resources under Terraform management |
