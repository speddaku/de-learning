# CI/CD & DevOps — Complete Notes from Scratch

---

## 1. Git

### Core Concepts

Think of Git as a time machine for your codebase. Every commit is a full snapshot you can jump back to, and branches let multiple people work on different snapshots simultaneously without stepping on each other.

```
Repository  — project with full history
Commit      — snapshot of changes with message and hash
Branch      — pointer to a commit (moveable)
HEAD        — pointer to current branch/commit
Remote      — hosted copy (GitHub, GitLab, Bitbucket)
```

### Essential Commands

These are the commands you'll use every single day. The `git add -p` interactive staging is especially powerful — it lets you craft clean, atomic commits even when you've been working on multiple things at once.

```bash
# Setup
git init                              # new repo
git clone <url>                       # clone remote

# Daily workflow
git status                            # see what changed
git diff                              # changes not staged
git diff --staged                     # changes staged for commit
git add file.py                       # stage specific file
git add -p                            # interactively stage hunks
git commit -m "feat: add ETL pipeline"
git push origin main

# Branches
git branch feature/etl-refactor       # create branch
git checkout feature/etl-refactor     # switch
git checkout -b feature/new           # create + switch
git branch -d feature/done            # delete merged branch
git branch -D feature/abandoned       # force delete

# Merging
git checkout main
git merge feature/etl-refactor        # merge feature into main
git merge --squash feature/xxx        # squash all commits into one

# Remote
git fetch origin                      # fetch updates (no merge)
git pull origin main                  # fetch + merge
git push -u origin feature/xxx        # push + set upstream

# History
git log --oneline --graph             # visual branch history
git log --author="Suhas"              # filter by author
git blame file.py                     # who changed each line
git show abc1234                      # show specific commit

# Undo
git restore file.py                   # discard unstaged changes
git restore --staged file.py          # unstage
git revert abc1234                    # new commit that undoes abc1234
git reset --soft HEAD~1               # undo last commit, keep staged
git reset --mixed HEAD~1              # undo last commit, keep unstaged
git reset --hard HEAD~1               # undo last commit, discard changes (dangerous!)

# Stash
git stash                             # save dirty working dir
git stash pop                         # restore stash
git stash list                        # list all stashes
```

### Branching Strategies

The branching strategy your team uses fundamentally shapes how fast you can ship. GitFlow made sense when software was packaged and released on a schedule (think: shrink-wrap software). But for data pipelines that deploy multiple times per week, all that ceremony — develop branch, release branch, hotfix branch — creates bureaucracy that slows you down without adding safety. Trunk-based development bets on small, frequent merges and automated tests as the safety net.

**GitFlow:**
```
main        — production-ready code
develop     — integration branch
feature/*   — new features (branch from develop, merge to develop)
release/*   — release prep (branch from develop, merge to main + develop)
hotfix/*    — urgent prod fixes (branch from main, merge to main + develop)

Good for: versioned releases, complex release processes
Bad for: continuous delivery (too much overhead)
```

**Trunk-Based Development:**

Trunk-based development is the strategy used by high-velocity engineering teams at Google, Facebook, and modern data platform teams. The insight is that long-lived branches are where integration problems accumulate. If a feature isn't ready to show users, hide it behind a feature flag — but still merge the code to main daily so you catch conflicts immediately.

```
main        — single shared trunk, always deployable
feature/*   — very short-lived (< 1 day), merge to main frequently
             Use feature flags to hide incomplete features

Good for: CI/CD, fast-moving teams, microservices
Bad for: large teams with infrequent releases
```

> **💡 Interview tip:** "Why do you prefer trunk-based over GitFlow?" Answer: trunk-based forces small, frequent merges which means smaller diffs, easier code review, and faster detection of integration problems. GitFlow's long-lived branches accumulate divergence and make merges painful. For data engineering pipelines that deploy frequently, the overhead of GitFlow isn't justified.

**Merge vs Rebase:**

Merge and rebase both integrate changes from one branch into another, but they tell a different story. Merge says "these two lines of work came together at this point." Rebase says "I wrote this code as if I had started from the latest main." Rebase creates a cleaner, linear history that's easier to `git log` through — but it rewrites commit hashes, which is why you must never rebase a branch someone else has pulled.

```
Merge:
- Creates merge commit (non-linear history)
- Preserves context of when feature was developed
- Good for: merging feature branches to main

Rebase:
- Replays commits on top of target branch (linear history)
- Cleaner log
- NEVER rebase shared/public branches (rewrites history)
- Good for: cleaning up feature branch before PR

git rebase main     # replay current branch commits on top of main
git rebase -i HEAD~3  # interactive — squash, reorder, edit last 3 commits
```

> **💡 Interview tip:** The golden rule of rebase: only rebase commits that exist on YOUR local machine. The moment a commit is pushed and someone else has pulled it, rebasing it rewrites history and causes chaos for that person when they try to push.

> **🌍 Real world:** In DE teams, a common workflow is: work on `feature/add-orders-mart`, rebase onto main before opening a PR (to resolve any conflicts cleanly), then merge the PR using a standard merge commit. This gives you clean local history AND a record in main of when the feature landed.

### Conventional Commits

Conventional commits aren't just formatting rules — they're machine-readable metadata. Tools like `semantic-release` and `conventional-changelog` parse these prefixes to automatically determine the next version number and generate changelogs. If your pipeline changes an API, `feat:` bumps minor version; a breaking change bumps major.

```
<type>(<scope>): <description>

Types:
feat:     new feature
fix:      bug fix
refactor: code change that neither fixes nor adds feature
test:     adding tests
docs:     documentation only
chore:    build process, dependency updates
ci:       CI configuration changes

Examples:
feat(etl): add incremental load for orders table
fix(spark): resolve data skew in customer join
ci: add pytest to GitHub Actions workflow
```

### Git Hooks

Git hooks run scripts at key moments in the git lifecycle — before a commit is saved, before a push is sent. Think of them as automated gatekeepers that enforce team standards locally, before code even hits CI. The `pre-commit` tool standardizes hook management across a team so everyone runs the same checks.

```
Pre-commit:  run before commit (linting, formatting, tests)
Pre-push:    run before push (full test suite)
Commit-msg:  validate commit message format

# .git/hooks/pre-commit
#!/bin/sh
python -m flake8 src/
python -m pytest tests/unit/ -q

# Use pre-commit tool (manages hooks across team):
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.0.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

> **🌍 Real world:** Pre-commit hooks for data engineering repos typically check: Black formatting, Flake8 linting, no hardcoded credentials (detect-secrets hook), and SQL linting (sqlfluff). The `pre-commit` framework makes this trivially installable with `pre-commit install` so every developer's local environment matches CI.

---

## 2. Jenkins

### Core Architecture

Jenkins is a battle-tested CI/CD server that orchestrates build pipelines. The controller handles scheduling and the UI; agents are the machines that actually do the work. Think of the controller as a dispatcher and agents as taxi drivers — the dispatcher assigns jobs, the drivers execute them.

```
Jenkins Controller — orchestrates pipelines, UI, job scheduling
Agent (Node)       — runs actual build steps
Executor           — one concurrent build slot on an agent

Build trigger types:
- Webhook:     trigger on git push
- Scheduled:   cron expression (H 2 * * *)
- Upstream:    trigger when another job completes
- Manual:      user clicks Build Now
- API:         POST to Jenkins API
```

### Jenkinsfile — Declarative Pipeline

The Jenkinsfile is "pipeline as code" — it lives in your repository alongside your application code. This means your pipeline definition is version-controlled, peer-reviewed, and reproducible. Before Jenkinsfiles, pipeline configuration lived in the Jenkins UI and was notoriously hard to audit or reproduce after a server failure.

```groovy
pipeline {
    agent any  // run on any available agent
    
    environment {
        AWS_REGION = 'us-east-1'
        ECR_REPO   = '123456789.dkr.ecr.us-east-1.amazonaws.com/my-app'
        DEPLOY_ENV = "${env.BRANCH_NAME == 'main' ? 'prod' : 'staging'}"
    }
    
    triggers {
        cron('H 2 * * *')  // nightly at ~2am
        githubPush()        // on push (requires GitHub plugin)
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Install') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Lint & Test') {
            parallel {
                stage('Lint') {
                    steps {
                        sh 'flake8 src/'
                    }
                }
                stage('Unit Tests') {
                    steps {
                        sh 'pytest tests/unit/ --junitxml=reports/unit-tests.xml'
                    }
                    post {
                        always {
                            junit 'reports/unit-tests.xml'  // publish test results
                        }
                    }
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${ECR_REPO}:${env.BUILD_NUMBER} ."
            }
        }
        
        stage('Push to ECR') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                  credentialsId: 'aws-credentials']]) {
                    sh '''
                        aws ecr get-login-password --region $AWS_REGION | \
                        docker login --username AWS --password-stdin $ECR_REPO
                        docker push $ECR_REPO:$BUILD_NUMBER
                    '''
                }
            }
        }
        
        stage('Deploy') {
            when {
                branch 'main'  // only deploy from main
            }
            steps {
                sh "aws ecs update-service --cluster prod --service my-app \
                    --force-new-deployment"
            }
        }
    }
    
    post {
        failure {
            emailext(
                to: 'team@example.com',
                subject: "Build Failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: "Check: ${env.BUILD_URL}"
            )
        }
        always {
            cleanWs()  // clean workspace after build
        }
    }
}
```

> **💡 Interview tip:** A common question is "what makes Jenkinsfile better than configuring jobs through the UI?" The answer is the three pillars: version control (changes are tracked and reviewable), reproducibility (you can recreate the pipeline from scratch if the Jenkins server dies), and code review (pipeline changes go through the same PR process as application code).

### Credentials Management

Never hardcode secrets in a Jenkinsfile — they'd be visible in your git history forever. Jenkins stores credentials in an encrypted store on the controller and injects them at runtime using `withCredentials`. The credentials never appear in logs (Jenkins masks them).

```groovy
// In Jenkinsfile — never hardcode secrets

// AWS credentials
withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                  credentialsId: 'aws-prod-credentials']]) {
    sh 'aws s3 ls'
}

// Username/password
withCredentials([usernamePassword(credentialsId: 'db-creds',
                                   usernameVariable: 'DB_USER',
                                   passwordVariable: 'DB_PASS')]) {
    sh 'psql -U $DB_USER -W $DB_PASS -h localhost mydb'
}

// Secret text
withCredentials([string(credentialsId: 'slack-token', variable: 'SLACK_TOKEN')]) {
    sh 'curl -H "Authorization: Bearer $SLACK_TOKEN" ...'
}
```

### Jenkins Agents

For data engineering pipelines, you often need different environments for different steps — a machine with Docker for building images, a pod with kubectl for Kubernetes deployments. Jenkins lets you route each stage to the right agent type.

```groovy
// Run stages on specific agents
pipeline {
    agent none  // no default agent
    stages {
        stage('Build') {
            agent {
                label 'linux-docker'  // agent with this label
            }
            steps { ... }
        }
        
        stage('Deploy to K8s') {
            agent {
                kubernetes {
                    yaml '''
                    apiVersion: v1
                    kind: Pod
                    spec:
                      containers:
                      - name: kubectl
                        image: bitnami/kubectl:latest
                    '''
                }
            }
            steps { ... }
        }
    }
}
```

---

## 3. CI/CD Concepts

### Continuous Integration

CI is the practice of merging code into a shared branch frequently — at least once a day — and running automated validation on every merge. The point isn't the tooling; it's the discipline. The tooling just enforces it.

```
Every push to repo triggers automated build + tests.

Benefits:
- Catch integration bugs early
- Small, frequent merges (less conflict)
- Always know if codebase is in a working state

What to automate:
1. Run linter/formatter
2. Run unit tests
3. Run integration tests
4. Build artifact (Docker image, wheel, zip)
5. Publish test report
6. Notify team of failure
```

> **🌍 Real world:** For a data engineering team, the CI pipeline typically runs: SQL linting (sqlfluff), Python linting (flake8/ruff), unit tests for transformation logic, and dbt compile to catch broken `ref()` calls. The whole thing should run in under 5 minutes or developers start skipping it.

### Continuous Delivery vs Continuous Deployment

These terms are often conflated. The distinction is whether a human approves production deploys or not.

```
Continuous Delivery:
- Automated pipeline deploys to staging automatically
- Production deployment requires MANUAL approval
- "We can deploy to prod at any time, but we choose when"

Continuous Deployment:
- Automated pipeline deploys to PROD automatically on every merge
- No human gate
- Requires high confidence in test suite
- Used by Netflix, Amazon
```

> **💡 Interview tip:** Most data engineering shops practice Continuous Delivery, not Continuous Deployment. Why? Because a broken ETL that silently loads bad data into a production data warehouse can corrupt reports used for business decisions. Teams want a human review gate before production, even if it's just a 5-minute sanity check.

### Environment Promotion

Code flows through a gauntlet of environments before reaching production. Each environment acts as a filter, catching a different class of problems.

```
Code flows through environments:
Feature Branch → Dev → Staging → Production

Dev:
- Every commit auto-deploys
- May be unstable
- Developers test here

Staging (Pre-prod):
- Mirror of production
- Integration tests, UAT (user acceptance testing)
- Performance testing

Production:
- Live user traffic
- Deploy with approval
- Canary or blue/green
```

### Deployment Strategies

The deployment strategy you choose determines your risk exposure and rollback speed. Think of it this way: how quickly can you undo a bad deploy, and at what cost?

**Blue/Green:**

Blue/green is like having a spare tire already inflated and ready to go. Your old production environment stays up and healthy (blue) while you deploy the new version to an identical, idle environment (green). Once green passes smoke tests, you flip the load balancer. If something goes wrong, flipping back takes seconds.

```
Blue = current production (live)
Green = new version (idle)

1. Deploy new version to Green environment
2. Run smoke tests on Green
3. Switch load balancer from Blue → Green (instant cutover)
4. Keep Blue alive for quick rollback
5. If issues: switch back to Blue

Pros: instant rollback, zero downtime
Cons: requires double infrastructure temporarily
```

**Canary:**

Named after the "canary in a coal mine" — you send a small percentage of real traffic to the new version first, watch for distress signals (elevated error rates, latency spikes, business metric drops), and only proceed with the full rollout if everything looks healthy. The cost is complexity; the benefit is that real users validate your changes before you commit to 100% rollout.

```
1. Deploy new version to small % of servers (1-5%)
2. Monitor error rate, latency, business metrics
3. Gradually increase traffic to new version (10% → 25% → 50% → 100%)
4. Roll back if metrics degrade

Pros: gradual risk exposure, real traffic testing
Cons: slower rollout, complex routing
```

**Rolling:**
```
1. Replace instances one by one
2. New version deployed to one instance
3. Health check passes → move to next instance
4. Continue until all instances updated

Pros: simple, no extra infrastructure
Cons: multiple versions running simultaneously, harder rollback
```

> **💡 Interview tip:** Blue/green is preferred when you need guaranteed instant rollback — e.g., a schema migration that has backward-incompatible changes. Canary is preferred when you want to validate with real traffic before fully committing — e.g., a new ML model serving predictions. For most DE pipeline deployments (Glue jobs, dbt runs, Spark jobs), neither applies — you just redeploy the previous job definition.

---

## 4. GitHub Actions (Alternative to Jenkins)

GitHub Actions brings CI/CD directly into GitHub with zero external infrastructure. Workflows are YAML files in `.github/workflows/`. For data engineering teams already on GitHub, this is often the path of least resistance — no Jenkins server to maintain, no agent pools to manage.

```yaml
# .github/workflows/etl-pipeline.yml
name: ETL Pipeline CI

on:
  push:
    branches: [main, 'feature/*']
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # daily at 2am UTC

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: testdb
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Lint
        run: flake8 src/ tests/
      
      - name: Test
        run: pytest tests/ -v --cov=src --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/testdb
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Deploy Glue job
        run: |
          aws s3 cp src/etl_job.py s3://my-bucket/glue-scripts/
          aws glue update-job --job-name my-etl --job-update '...'
```

> **🌍 Real world:** GitHub Actions `services:` block is a killer feature for DE testing. You can spin up a real PostgreSQL or MySQL container as a sidecar to your test job and run integration tests against it — no mocking, no external database dependencies. This is how you test actual SQL logic in CI.

---

## 5. Infrastructure as Code

IaC is the practice of managing infrastructure (S3 buckets, IAM roles, VPCs, Glue jobs, RDS clusters) through code files rather than clicking around in a web console. The analogy: clicking in the console is like configuring servers by SSHing in and running commands by hand — it works, but it's not repeatable, not auditable, and creates "snowflake servers" that are impossible to recreate exactly. IaC eliminates snowflakes by making infrastructure declarative, versioned, and reproducible.

> **💡 Interview tip:** A "snowflake server" is a server (or any piece of infrastructure) that has been hand-configured to the point where nobody knows exactly what's on it. If it dies, you can't reproduce it. IaC solves this by making every infrastructure change a code change — tracked in git, applied consistently.

### CloudFormation (AWS native)

CloudFormation is AWS's native IaC service. You describe the desired end state as YAML or JSON, and CloudFormation figures out how to create, update, or delete resources to reach that state. The `!Sub`, `!Ref`, and `!GetAtt` intrinsic functions let you wire resources together without hardcoding ARNs.

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: ETL Pipeline Infrastructure

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, staging, prod]

Resources:
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub 'my-data-lake-${Environment}'
      VersioningConfiguration:
        Status: Enabled
      LifecycleConfiguration:
        Rules:
          - Status: Enabled
            Transitions:
              - TransitionInDays: 90
                StorageClass: GLACIER
  
  GlueJobRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: glue.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
  
  ETLJob:
    Type: AWS::Glue::Job
    Properties:
      Name: !Sub 'daily-etl-${Environment}'
      Role: !GetAtt GlueJobRole.Arn
      Command:
        Name: glueetl
        ScriptLocation: !Sub 's3://${DataBucket}/scripts/etl.py'
        PythonVersion: '3'
      DefaultArguments:
        '--job-bookmark-option': 'job-bookmark-enable'

Outputs:
  BucketName:
    Value: !Ref DataBucket
    Export:
      Name: !Sub '${AWS::StackName}-BucketName'
```

### Terraform Basics

Terraform is cloud-agnostic IaC — the same workflow covers AWS, GCP, Azure, and dozens of other providers. Terraform maintains a "state file" that maps your config to real-world resources. Storing state in S3 with DynamoDB locking is critical for team usage — it prevents two engineers from running `terraform apply` simultaneously and corrupting the state.

```hcl
# main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "etl/terraform.tfstate"
    region = "us-east-1"
    dynamodb_table = "terraform-locks"  # state locking
  }
}

provider "aws" {
  region = var.region
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

resource "aws_s3_bucket" "data_lake" {
  bucket = "my-data-lake-${var.environment}"
  
  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

output "bucket_name" {
  value = aws_s3_bucket.data_lake.bucket
}
```

The Terraform workflow follows a strict plan-before-apply discipline. `terraform plan` shows you exactly what will change before you touch anything — treat it like a `--dry-run`. Always review the plan in CI before allowing `apply`.

```bash
# Terraform workflow
terraform init    # download providers, configure backend
terraform plan    # preview changes
terraform apply   # apply changes (prompts for confirmation)
terraform destroy # tear down infrastructure

# Target specific resource
terraform apply -target=aws_s3_bucket.data_lake

# Auto-approve (CI/CD)
terraform apply -auto-approve
```

> **🌍 Real world:** In a DE team, Terraform is typically used for: S3 bucket policies, Redshift/RDS cluster specs, IAM roles for Glue/EMR, Kinesis streams, and MSK (Kafka) clusters. The Glue job code itself lives in git and gets deployed by CI, but the Glue job definition (worker count, role, script location) is managed by Terraform. Separation of concerns: infrastructure in Terraform, application code in CI/CD.

> **💡 Interview tip:** "What's in Terraform state and why does it matter?" Terraform state maps every resource in your config to its real-world ID (e.g., `aws_s3_bucket.data_lake` → `arn:aws:s3:::my-data-lake-prod`). Without state, Terraform can't know what already exists and would try to recreate everything. Losing state is catastrophic — it's why you store it in versioned S3 with locking, never locally.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Git branch | Feature branches, short-lived, merge via PR |
| Trunk-based | Single main branch, frequent merges, feature flags |
| Merge vs rebase | Merge for features→main, rebase to clean local branch |
| Conventional commits | feat/fix/refactor/chore: scope: description |
| CI | Every push triggers automated tests |
| CD | Automated deploy to staging/prod |
| Blue/green | Deploy to idle env, flip traffic — instant rollback |
| Canary | Gradual traffic shift — real-world risk mitigation |
| Jenkinsfile | Pipeline as code — declarative or scripted |
| GitHub Actions | Cloud-native CI/CD, YAML workflows, free for public |
| IaC | Infrastructure defined in code — repeatable, versioned |
| Terraform state | Tracks real world vs config — store in S3 + DynamoDB lock |
