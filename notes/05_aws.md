# AWS Core Services — Complete Notes from Scratch

---

## 1. IAM — Identity and Access Management

IAM is AWS's permission layer — every API call in AWS goes through it. Understanding IAM deeply separates engineers who can only use AWS from engineers who can architect secure, production-grade systems on it. The mental model that matters most: **start with zero permissions and add only what is explicitly needed**. Never grant broad access and try to narrow it down later — that's how security incidents happen.

### Core Concepts
```
Users      — human identities with long-term credentials
Groups     — collection of users, inherit group policies
Roles      — assumed by services or federated users (no long-term creds)
Policies   — JSON documents that define permissions (Allow/Deny)
```

Think of IAM Roles like a temporary badge system: a Glue job "picks up" a role badge when it starts, uses only the permissions on that badge while running, and hands it back when done. Unlike a User (which has permanent credentials), a Role has no standing credentials — it generates temporary tokens via STS `AssumeRole`. This is the correct model for all AWS services (Lambda, Glue, EC2) — **never embed access keys in code or config files**.

> **💡 Interview tip:** Interviewers love asking "What is least privilege and how do you implement it?" The answer is not just "grant minimum permissions." It's: start with no permissions, use IAM Access Analyzer to discover what a service actually called, then lock the policy to exactly those actions and resources. Condition keys (like restricting to a specific region or VPC) are the next level.

> **🌍 Real world:** In multi-team data platforms, teams routinely over-provision Glue roles with `s3:*` on all buckets because it's easier. This creates blast radius when something goes wrong. Proper least-privilege means a Glue job reading from `raw/` and writing to `processed/` gets exactly those two prefixes — nothing else.

### Policy Structure

A policy is just a JSON document with Statements. Each Statement has an Effect (Allow or Deny), Action(s), Resource(s), and optional Condition(s). The key insight: **Deny always wins over Allow**. You can never Allow your way past an explicit Deny.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-bucket/*",
      "Condition": {
        "StringEquals": {"aws:RequestedRegion": "us-east-1"}
      }
    }
  ]
}
```

### IAM Best Practices
```
- Least privilege: grant minimum permissions needed
- Never use root account for daily tasks
- Enable MFA on root and privileged users
- Use roles for EC2/Lambda/Glue — never embed access keys in code
- Rotate access keys regularly
- Use IAM Access Analyzer to find overly broad permissions
- Separate dev/staging/prod using separate AWS accounts or SCPs
```

### Trust Policies (for Roles)

A Trust Policy answers "who is allowed to assume this role?" — it's a separate JSON document attached to every Role (distinct from the permissions policy). Without a trust policy allowing `glue.amazonaws.com`, a Glue job literally cannot pick up the role, even if the permissions policy grants everything.

```json
{
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "glue.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

> **💡 Interview tip:** A common gotcha question: "Your Glue job has full S3 permissions in its policy but is still getting access denied. Why?" — The trust policy is missing or wrong. The permissions policy and the trust policy are two separate documents that must both be correct.

---

## 2. VPC — Virtual Private Cloud

A VPC is your private network inside AWS — isolated from all other customers. Think of it as a data center you define in software. The difference between a public and private subnet is purely a routing table entry: public subnets have a route pointing `0.0.0.0/0` to an Internet Gateway; private subnets don't. That one route entry is what makes the difference between "internet accessible" and "not."

### Core Components
```
VPC           — isolated network (CIDR block: 10.0.0.0/16)
Subnet        — subdivision of VPC (public or private)
Route Table   — rules for where network traffic goes
Internet GW   — enables internet access for public subnets
NAT Gateway   — allows private subnets to reach internet (outbound only)
Security Group — virtual firewall (stateful) at instance level
NACL          — network ACL (stateless) at subnet level
```

### Public vs Private Subnet
```
Public subnet:
- Route to internet gateway (0.0.0.0/0 → igw-xxx)
- Resources with public IPs accessible from internet
- Use for: load balancers, bastion hosts

Private subnet:
- No direct route to internet
- Use NAT gateway for outbound internet (software updates, API calls)
- Use for: databases, Lambda, Glue jobs
```

> **🌍 Real world:** Most data pipelines run in private subnets. Your Glue jobs, RDS databases, and Redshift clusters should never be internet-accessible. They reach S3 and other AWS services via VPC Endpoints (private routes that never traverse the internet), which is both faster and more secure than going through a NAT Gateway.

---

## 3. Amazon S3

S3 is the foundation of every AWS data lake. It's not just "object storage" — it's a globally consistent, 11-nines durable, infinitely scalable file system that most AWS analytics services treat as their native I/O layer. The architectural patterns you build around S3 — partitioning, file formats, lifecycle policies — directly translate to query cost and performance.

### Core Concepts
```
Bucket    — container for objects (globally unique name)
Object    — file + metadata (max 5TB per object)
Key       — full path within bucket (prefix + filename)
Prefix    — like a folder path: s3://bucket/year=2025/month=05/
```

### S3 Storage Classes

Storage classes are a cost optimization lever. The key tradeoff is access frequency vs. storage price vs. retrieval cost. Intelligent-Tiering is underrated — it monitors access patterns and moves objects automatically, making it the right default for most data lake data where access frequency is unpredictable.

```
Standard            — frequent access, low latency
Standard-IA         — infrequent access, cheaper storage, retrieval fee
One Zone-IA         — cheaper, single AZ (not replicated)
Glacier Instant     — archive, ms retrieval
Glacier Flexible    — archive, minutes-to-hours retrieval
Glacier Deep Archive— cheapest, 12-hour retrieval
Intelligent-Tiering — auto-moves between tiers based on access patterns
```

### S3 Lifecycle Policies

Lifecycle policies automate the cost optimization you'd otherwise have to do manually. Define the policy once and let S3 handle it — data moves to cheaper tiers as it ages, and gets deleted when it passes its retention window. This is essential for keeping data lake storage costs under control.

```json
{
  "Rules": [{
    "Status": "Enabled",
    "Transitions": [
      {"Days": 30, "StorageClass": "STANDARD_IA"},
      {"Days": 90, "StorageClass": "GLACIER"}
    ],
    "Expiration": {"Days": 365}
  }]
}
```

### S3 Partitioning for Analytics

Partitioning is the single highest-leverage optimization in any S3 data lake. When you partition by date and query with a date filter, the query engine can skip entire directories of files without opening them — this is called **partition pruning**. On a table with years of history, the difference between a query scanning 1 day's partition vs. the whole table can be 1,000x in both speed and cost.

Think of it this way: if your data is 3TB total but you're querying only today's data (10GB), good partitioning means you read 10GB. Bad partitioning (or no partitioning) means you read 3TB and pay for all of it in Athena.

```
Partition by date and entity for efficient querying:
s3://my-bucket/events/year=2025/month=05/day=21/hour=10/

Hive-style partitions (year=X/month=Y) are auto-recognized by:
- Athena, Glue, Redshift Spectrum

Partition projection (Athena) — auto-generates partitions without crawling:
ALTER TABLE events SET TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.year.type'='integer',
  'projection.year.range'='2020,2030',
  'storage.location.template'='s3://bucket/events/year=${year}'
)
```

> **💡 Interview tip:** "How do you optimize Athena query costs?" — The answer has three layers: (1) partition the data so you scan only relevant prefixes, (2) use Parquet/ORC so column pruning avoids reading irrelevant columns, (3) use compression so fewer bytes traverse the network. Partition projection is the next level — it tells Athena the partition layout directly so it doesn't need to make Glue Catalog API calls to enumerate partitions.

> **🌍 Real world:** Over-partitioning is a real problem. If you partition by hour for a table that's only queried by month, you create thousands of tiny files and slow down listing operations. Partition granularity should match your most common query filter, not the most granular time unit available.

### S3 Event Notifications

S3 events enable fully event-driven pipeline architecture. Instead of polling S3 for new files on a schedule, you configure S3 to push a notification the moment an object lands — eliminating unnecessary polling latency and cost.

```
Events:        s3:ObjectCreated, s3:ObjectRemoved, s3:ObjectRestore
Destinations:  SQS, SNS, Lambda, EventBridge

Use case: new file lands → trigger Lambda/Glue job for processing
```

### S3 Versioning
```
- Keeps all versions of every object
- Protects against accidental delete/overwrite
- Delete marker — soft delete (doesn't remove versions)
- Use with lifecycle to expire old versions
```

---

## 4. AWS Lambda

Lambda is serverless compute — you bring the function, AWS handles everything else (servers, scaling, patching). In data engineering, Lambda plays a specific role: it's excellent for lightweight, event-driven orchestration logic (trigger a Glue job, send an alert, validate a file), but it's the wrong tool for heavy data processing. The 15-minute timeout and memory limits mean that anything Spark-scale should be handed off to Glue or EMR.

### Architecture
```
Trigger → Lambda Function (handler) → Action

Event sources:
- API Gateway / ALB (HTTP requests)
- S3 (object events)
- SQS / Kinesis (message processing)
- DynamoDB Streams
- EventBridge (scheduled / event-driven)
- SNS (notifications)
```

### Handler Structure

The `event` and `context` parameters are always present. `event` is the trigger payload — its structure varies by source (an S3 event looks different from an SQS event, different from a direct invocation). `context` gives you runtime metadata, but the most useful property in practice is `context.get_remaining_time_in_millis()` — use it to detect when you're about to timeout and handle it gracefully.

```python
import json

def handler(event, context):
    # event — the trigger payload (dict)
    # context — runtime info (function name, memory, timeout remaining)
    
    print(f"Received event: {json.dumps(event)}")
    
    # Process event
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    
    # Do work
    result = process_file(bucket, key)
    
    return {
        'statusCode': 200,
        'body': json.dumps({'result': result})
    }
```

### Cold Start vs Warm Start

Cold starts are a fundamental constraint of Lambda's serverless model. When Lambda has no warm execution environment available, it must provision a new one: download your code, start the runtime, run your initialization code outside the handler. This can add hundreds of milliseconds to seconds of latency — a problem for latency-sensitive workloads.

Think of it like a car engine: a warm start is turning the key on an already-warm engine. A cold start means the engine has been sitting overnight — you get all the startup overhead before it's ready to drive.

The mitigation strategies exist on a spectrum from free (keep packages slim, move init code outside handler) to costly (Provisioned Concurrency pre-warms N instances and you pay for them 24/7).

```
Cold start:
- Lambda spins up new execution environment
- Initializes runtime, downloads code, runs init code
- Adds 100ms-2s latency (depends on runtime size)
- Happens when: first invocation, scaling up, after idle period

Warm start:
- Reuses existing execution environment
- Only runs handler function
- Much faster

Minimizing cold starts:
- Provisioned concurrency — pre-warms N instances (costs money)
- Keep packages slim — only import what you need
- Use Lambda Layers for large dependencies
- Keep init code minimal (outside handler)
```

> **💡 Interview tip:** "How would you reduce Lambda cold start latency?" — Know all four strategies and when to use each. Provisioned Concurrency is the nuclear option — it solves cold starts completely but you pay for idle capacity. For most data pipeline use cases (async, triggered by S3/SQS), cold starts are acceptable because latency isn't critical. For synchronous API-backed functions, cold starts matter and Provisioned Concurrency is worth it.

> **🌍 Real world:** A common anti-pattern is importing the entire AWS SDK at module level inside the handler. Move boto3 client initialization outside the handler function so it's reused across warm invocations. That single change can reduce warm execution time significantly since client initialization is not free.

### Concurrency
```
Reserved concurrency:
- Guarantees N instances always available for this function
- Also limits maximum concurrency (throttle protection)
- SET per function

Provisioned concurrency:
- Pre-initializes N instances (eliminates cold starts)
- Costs money even when idle
- Good for latency-sensitive endpoints
```

### Lambda with ETL

This is the canonical pattern for event-driven data pipelines on AWS: S3 event triggers Lambda, Lambda validates/routes and kicks off the real processing in Glue. Lambda acts as the lightweight coordinator — it's not doing the heavy lifting itself.

```python
import boto3
import json

s3 = boto3.client('s3')
glue = boto3.client('glue')

def handler(event, context):
    # Triggered by S3 event
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        # Start Glue job for large files
        response = glue.start_job_run(
            JobName='my-etl-job',
            Arguments={
                '--input_bucket': bucket,
                '--input_key': key
            }
        )
        
        return {'job_run_id': response['JobRunId']}
```

---

## 5. AWS Glue

Glue is AWS's managed Spark ETL service with an integrated metadata catalog. It eliminates the operational overhead of running Spark clusters while providing the Data Catalog — a centralized metadata store that acts as a Hive Metastore for Athena, Redshift Spectrum, and other services. In AWS-native data platforms, the Glue Catalog is the single source of truth for "what tables exist and where they live."

### Architecture Components
```
Data Catalog    — metadata store (databases, tables, schemas, partitions)
Crawlers        — scan data sources, infer schema, update catalog
ETL Jobs        — Spark-based (or Python shell) transformation scripts
Triggers        — start jobs on schedule, event, or job completion
Workflows       — chain of triggers + jobs + crawlers
Connections     — JDBC, network config for databases, Kafka, etc.
```

### Data Catalog
```
Database  — logical container for tables (maps to S3 prefix, database, etc.)
Table     — metadata: schema + location + format + partitions
Partition — subset of table data (e.g., year=2025/month=05)

Used by: Athena, Redshift Spectrum, Glue jobs, EMR

Glue Catalog is essentially a managed Hive Metastore
```

### Crawlers
```python
# Crawlers scan data and create/update table definitions
# No code needed — configure in console or CDK/Terraform

# After crawler runs:
# - Creates table with inferred schema
# - Updates partition list
# - Detects schema changes

# Best practice: schedule crawler before Glue jobs that depend on catalog
# Or use partition indexing to avoid full crawler re-runs
```

> **🌍 Real world:** Crawlers are convenient but dangerous in production. They infer schema from data samples, which means a source schema change can silently change your Glue table definition and break downstream jobs. Production-grade pipelines often define table schemas explicitly (via CDK/Terraform or `CREATE TABLE` DDL) rather than relying on crawlers — you want schema changes to be explicit, reviewed decisions, not automatic drift.

### Glue ETL Jobs — Python Shell
```python
# Lightweight Python script (not Spark) — use for small data, API calls, etc.
import boto3
import json

def main():
    s3 = boto3.client('s3')
    # ... do work
    
if __name__ == '__main__':
    main()
```

### Glue ETL Jobs — Spark (PySpark)

Glue Spark jobs are standard PySpark with an additional `GlueContext` layer on top. The initialization boilerplate below is required for every Glue job. The key pattern: use `getResolvedOptions` to receive job parameters (passed from Triggers, Step Functions, or CLI), and always call `job.commit()` at the end to mark the job as complete and advance the bookmark state.

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# Init
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'input_bucket', 'output_bucket'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Read from Glue catalog
datasource = glueContext.create_dynamic_frame.from_catalog(
    database="my_db",
    table_name="raw_events",
    transformation_ctx="datasource"
)

# Apply schema mapping
applymapping = ApplyMapping.apply(
    frame=datasource,
    mappings=[
        ("event_id", "string", "event_id", "string"),
        ("amount", "double", "amount", "decimal"),
        ("event_ts", "string", "event_ts", "timestamp")
    ],
    transformation_ctx="applymapping"
)

# Resolve ambiguous types
resolved = ResolveChoice.apply(
    frame=applymapping,
    choice="make_struct",
    transformation_ctx="resolved"
)

# Convert to DataFrame for complex transforms
df = resolved.toDF()
df = df.filter(df.amount > 0)

# Back to DynamicFrame for writing
output = DynamicFrame.fromDF(df, glueContext, "output")

# Write to S3 as Parquet, partitioned
glueContext.write_dynamic_frame.from_options(
    frame=output,
    connection_type="s3",
    connection_options={
        "path": f"s3://{args['output_bucket']}/processed/",
        "partitionKeys": ["year", "month"]
    },
    format="glueparquet",
    transformation_ctx="datasink"
)

job.commit()
```

### DynamicFrame vs Spark DataFrame

This is one of the most practically important Glue concepts. DynamicFrame exists specifically to handle the schema chaos common in real-world source data — a column that is sometimes a string and sometimes an integer (a `ChoiceType` in Glue terminology) would crash a standard Spark DataFrame read. DynamicFrame tolerates it.

The recommended pattern in production is a bridge: use DynamicFrame to absorb the messy source data safely, `resolveChoice()` or `applyMapping()` to clean up the ambiguities, convert to DataFrame for all the complex business logic (where PySpark's API is richer), then convert back to DynamicFrame for the Glue-managed write.

```
DynamicFrame:
- Glue-specific abstraction
- Handles schema inconsistencies (choicetypes, null handling)
- resolveChoice() — handle conflicting types
- relationalize() — flatten nested structs/arrays
- Slightly less performant than DataFrames

Spark DataFrame:
- Full PySpark API available
- Better performance, more flexibility
- Convert: df = dynamic_frame.toDF()
           dynamic_frame = DynamicFrame.fromDF(df, glueContext, "name")

Best practice: use DynamicFrame for reading messy source data,
convert to DataFrame for complex transformations, convert back for writing.
```

> **💡 Interview tip:** "Why would you use a Glue DynamicFrame instead of a Spark DataFrame?" — The answer is schema drift tolerance. When your source (e.g., a JSON API or a MySQL table where a column's type changed) produces inconsistent types across records, a Spark DataFrame read with `inferSchema` either crashes or silently coerces data. DynamicFrame reads every record, identifies the type conflicts as `ChoiceType`, and lets you resolve them explicitly with `resolveChoice()`. This is essential when you don't control the source schema.

### Job Bookmarks

Bookmarks are Glue's built-in mechanism for incremental loads on S3 and JDBC sources. Glue stores the state of which files/offsets have been processed, so re-running the job after a failure only processes new data. This is Glue's way of providing idempotency without you having to maintain your own watermark table.

```python
# Tracks which data has been processed — enables incremental loads
# Glue stores bookmark state per job

# Enable in job parameters:
# --job-bookmark-option: job-bookmark-enable

# How it works:
# - Tracks S3 objects/JDBC offsets already processed
# - On re-run, only processes new data
# - Reset bookmark to reprocess everything: AWS CLI or console

# Limitations:
# - Only works with supported sources (S3, JDBC, DynamoDB)
# - Doesn't work with Kinesis
```

### Glue Triggers
```
Scheduled trigger:    cron(0 2 * * ? *)  — runs daily at 2am
On-demand trigger:    manual start
Conditional trigger:  start when previous job succeeds/fails/any
Event trigger:        start on EventBridge event
```

---

## 6. Amazon Athena

Athena is serverless SQL on S3. You write a query, it runs against files in S3, you pay for the bytes scanned. That billing model — **you pay per byte scanned, not per query** — is the most important thing to internalize, because it means every format and partitioning decision is a financial decision. A query that scans 1TB costs $5. The same logical query on well-partitioned Parquet might scan 10GB and cost $0.05.

### What It Is
```
- Serverless interactive query service
- Queries data directly in S3 using SQL
- No infrastructure to manage, no data loading
- Pay per query (per TB scanned)
- Built on Presto/Trino + Apache Hive metastore (Glue Catalog)
```

### Cost Optimisation

These six optimizations are in priority order. Parquet/ORC + partitioning alone typically reduce scanned bytes by 90-99% compared to unpartitioned CSV. Partition projection eliminates the overhead of Glue Catalog API calls when you have thousands of partitions.

```
1. Use columnar formats (Parquet/ORC) → column pruning → scan less data
2. Use compression (Snappy, ZSTD) → fewer bytes to read
3. Partition data (year/month/day) → partition pruning → skip irrelevant files
4. Use partition projection → skip Glue catalog calls
5. Avoid SELECT * → reads all columns even in columnar formats
6. Keep files large-ish (128MB-1GB) → avoid small file overhead
```

> **💡 Interview tip:** "Our Athena bills are too high. Walk me through how you'd diagnose and fix it." — Start with the query history in Athena console or CloudWatch Logs to find the highest-cost queries by bytes scanned. Then check: (1) Are they using partition filters? If not, add partitions and update queries. (2) Is the data in Parquet/ORC? If CSV, migrate. (3) Are there `SELECT *` queries? Refactor. (4) Are files too small? Compact them. This is a real conversation that happens in every data team.

### Table Setup

The `MSCK REPAIR TABLE` command is critical to know — when you add new partitions to S3 (new daily files arrive), Athena doesn't know about them until you register them. `MSCK REPAIR TABLE` scans S3 and registers all discovered Hive-style partitions. For large tables with many partitions, explicit `ALTER TABLE ADD PARTITION` is faster.

```sql
-- Create external table over Parquet in S3
CREATE EXTERNAL TABLE events (
    event_id    STRING,
    user_id     STRING,
    event_type  STRING,
    amount      DOUBLE,
    event_ts    TIMESTAMP
)
PARTITIONED BY (year INT, month INT, day INT)
STORED AS PARQUET
LOCATION 's3://my-bucket/events/'
TBLPROPERTIES ('parquet.compress'='SNAPPY');

-- Load partitions manually
MSCK REPAIR TABLE events;

-- Or add partition explicitly
ALTER TABLE events ADD PARTITION (year=2025, month=5, day=21)
LOCATION 's3://my-bucket/events/year=2025/month=5/day=21/';
```

### Query Optimisation

The most expensive mistake is applying a function to a partition column in the WHERE clause. `WHERE YEAR(event_ts) = 2025` looks like it filters by year, but the optimizer cannot push this down to partition pruning because it needs to evaluate the function on each row. Use the explicit partition column instead.

```sql
-- Good: filter on partition columns first (eliminates files at scan time)
SELECT user_id, SUM(amount)
FROM events
WHERE year = 2025 AND month = 5
GROUP BY user_id;

-- Bad: function on partition column prevents pruning
WHERE DATE_FORMAT(event_ts, '%Y') = '2025'

-- Good: use columnar format + specific columns
SELECT user_id, amount FROM events WHERE year = 2025;

-- Bad: full table scan
SELECT * FROM events;
```

### Athena Workgroups
```
- Separate query environments for different teams
- Set per-workgroup: max data scanned per query, S3 output location
- Enforce cost controls
- Track metrics separately
```

---

## 7. AWS Step Functions

Step Functions is AWS's managed workflow orchestration service — think Airflow but as a managed AWS service with native integration into every AWS service. For data pipelines, Step Functions excels at: sequencing ETL steps with error handling, running parallel file processing, and providing full visibility into pipeline execution state. Unlike Airflow, there's no infrastructure to manage and the execution history is stored natively.

### Concepts

Standard vs. Express workflow is an important distinction. Standard workflows are designed for long-running ETL pipelines (up to a year, though typical pipelines run in minutes-to-hours) with exactly-once guarantees and full audit history. Express workflows are for high-volume, short-duration processing where you're orchestrating thousands of executions per second.

```
State Machine — workflow definition (JSON/YAML in Amazon States Language)
State         — a step in the workflow
Execution     — one run of the state machine with specific input

Standard workflow:
- Max duration: 1 year
- Exactly-once execution
- High cost per state transition
- Full execution history in console

Express workflow:
- Max duration: 5 minutes
- At-least-once execution (for async)
- Much cheaper
- Use for: high-volume, short-duration workflows
```

### State Types

The Amazon States Language (ASL) workflow below shows a complete ETL pipeline: extract → transform (Glue job, waited for with `.sync`) → quality gate (Choice state) → load or alert. The `.sync` suffix on the Glue integration is critical — without it, Step Functions fires the Glue job and immediately moves on without waiting for it to complete.

```json
{
  "Comment": "ETL Pipeline",
  "StartAt": "ExtractData",
  "States": {
    "ExtractData": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:::function:extract",
      "Next": "TransformData"
    },
    "TransformData": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "my-transform-job",
        "Arguments": {"--input": "$.input_path"}
      },
      "Next": "CheckQuality"
    },
    "CheckQuality": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.quality_score",
          "NumericGreaterThan": 0.95,
          "Next": "LoadData"
        }
      ],
      "Default": "AlertFailure"
    },
    "LoadData": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:::function:load",
      "End": true
    },
    "AlertFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:::etl-alerts",
        "Message": "Quality check failed"
      },
      "Next": "Fail"
    },
    "Fail": {
      "Type": "Fail",
      "Error": "QualityCheckFailed"
    }
  }
}
```

### Parallel and Map States

The Map state is the distributed processing primitive of Step Functions. When you receive a batch of files to process, Map lets you kick off parallel Lambda/Glue executions for each file — up to the `MaxConcurrency` limit. This is much more efficient than processing files sequentially and maps naturally to partition-at-a-time ETL patterns.

```json
"ProcessAllFiles": {
  "Type": "Map",
  "ItemsPath": "$.files",
  "MaxConcurrency": 10,
  "Iterator": {
    "StartAt": "ProcessFile",
    "States": {
      "ProcessFile": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:::function:process",
        "End": true
      }
    }
  }
}
```

### Error Handling

The Retry + Catch pattern is one of the most important resilience patterns in production pipelines. Exponential backoff (BackoffRate: 2 means each retry waits 2x as long as the previous one) prevents thundering herd problems and gives transient failures (Lambda throttling, Glue capacity limits, downstream service hiccups) time to resolve. The `BackoffRate: 2` with `IntervalSeconds: 5` means retries happen at 5s, 10s, 20s — which handles most transient AWS service issues.

The `Catch` block is the fallback when all retries are exhausted — use it to route to a notification state (SNS/SQS) that alerts the on-call engineer or writes a failed-execution record for later reprocessing.

```json
"MyTask": {
  "Type": "Task",
  "Resource": "...",
  "Retry": [
    {
      "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
      "IntervalSeconds": 5,
      "MaxAttempts": 3,
      "BackoffRate": 2
    }
  ],
  "Catch": [
    {
      "ErrorEquals": ["States.ALL"],
      "ResultPath": "$.error",
      "Next": "HandleError"
    }
  ]
}
```

> **💡 Interview tip:** "How do you handle transient failures in a Step Functions pipeline?" — The answer is Retry with exponential backoff. Explain why BackoffRate matters: without it, all retries hammer the failing service simultaneously, potentially making the problem worse. With BackoffRate: 2 and MaxAttempts: 3, your worst-case retry window is 5+10+20=35 seconds, which handles virtually all AWS transient errors. Then explain that `Catch` handles the permanent failures — routes to a dead letter state for human review.

> **🌍 Real world:** Step Functions execution history is only retained for 90 days for Standard workflows. For production data pipelines, emit a CloudWatch metric (or write to DynamoDB) on pipeline completion with the run date, status, and row counts. This gives you a queryable pipeline run log independent of Step Functions' retention window.

### Input/Output Processing
```
InputPath    — filters input JSON before passing to task
OutputPath   — filters task output before passing to next state
ResultPath   — where to place task result in the state data
Parameters   — construct new JSON payload for task input

Example:
$.input_path → extract specific field from state
"$"          → pass full state
```

---

## 8. Amazon EventBridge

EventBridge is the event bus that glues AWS services together. It's the modern replacement for CloudWatch Events, with a much richer feature set: custom event buses, schema registry, SaaS integrations. In data engineering, EventBridge is the preferred trigger mechanism for scheduled pipelines (replaces cron-on-EC2) and event-driven workflows (replace polling loops).

### Core Concepts
```
Event Bus    — receives events
Rule         — matches events and routes to targets
Target       — receives matched events (Lambda, Step Functions, SQS, etc.)

Default event bus — AWS service events
Custom event bus  — your own application events
Partner event bus — SaaS integrations (Datadog, Zendesk, etc.)
```

### Scheduled Rules

EventBridge scheduled rules are the clean replacement for any cron-on-EC2 or cron-in-Lambda setup. They support both `rate()` expressions (simple intervals) and full cron syntax. Important: all times are UTC — account for daylight saving time when scheduling pipelines that business users expect at a specific local time.

```
Rate expression:   rate(5 minutes), rate(1 hour), rate(1 day)
Cron expression:   cron(0 2 * * ? *)  — daily at 2am UTC
                   cron(0 8 ? * MON-FRI *)  — weekdays at 8am

Use case: trigger Glue/Lambda on schedule
```

### Event Pattern Rules
```json
{
  "source": ["aws.s3"],
  "detail-type": ["Object Created"],
  "detail": {
    "bucket": {"name": ["my-data-bucket"]},
    "object": {"key": [{"prefix": "landing/"}]}
  }
}
```

### Custom Events

Publishing custom events to EventBridge decouples your pipeline stages. Instead of Job A directly calling Job B, Job A publishes a completion event and any number of downstream consumers can subscribe. This is the foundation of event-driven architecture — adding a new downstream consumer only requires adding an EventBridge rule, not modifying the upstream producer.

```python
import boto3
import json

events = boto3.client('events')

events.put_events(
    Entries=[{
        'Source': 'my-etl-pipeline',
        'DetailType': 'ETLJobCompleted',
        'Detail': json.dumps({
            'job_name': 'daily_sales_load',
            'status': 'SUCCESS',
            'rows_loaded': 50000
        }),
        'EventBusName': 'my-custom-bus'
    }]
)
```

---

## 9. Amazon RDS (PostgreSQL)

RDS PostgreSQL is managed PostgreSQL — AWS handles backups, patching, failover, and replication. For data engineering, RDS typically serves as the source system (OLTP database from which you're doing CDC or batch extracts) or as the metadata/orchestration database (pipeline state, audit tables, watermarks).

### Key Configuration
```
Instance class: db.t3.medium (dev), db.r6g.large (prod)
Storage: gp3 SSD, io1 for high IOPS workloads
Multi-AZ: standby replica in another AZ, auto-failover
Read replica: async replication, for read scaling, reporting
```

### Connection Pooling

Connection pooling is a critical production concern when Lambda or containerized services are connecting to RDS. PostgreSQL has a hard limit on concurrent connections (typically 100-300 depending on instance class). A burst of Lambda invocations can each open a connection and exhaust the pool, causing `too many connections` errors and pipeline failures.

```
Problem: many Lambda/app instances × connection overhead = DB overload
Solution: PgBouncer (connection pooler) or RDS Proxy

RDS Proxy:
- Serverless connection pool managed by AWS
- Sits between app and RDS
- Reduces connection overhead for Lambda/serverless
- IAM authentication support
```

> **🌍 Real world:** RDS Proxy is particularly valuable for Lambda-to-RDS connectivity because Lambda can scale to thousands of concurrent invocations instantly, each wanting its own database connection. RDS Proxy multiplexes these onto a smaller pool of actual database connections, preventing the connection exhaustion problem entirely.

### Automated Backups vs Snapshots
```
Automated backups:
- Daily backup during backup window
- Transaction logs every 5 mins
- Point-in-time recovery (PITR) up to retention period (1-35 days)

Manual snapshots:
- Persist indefinitely (until manually deleted)
- Take before schema changes, migrations
```

---

## Key Summary

| Service | Purpose |
|---------|---------|
| IAM | Identity, permissions, least privilege |
| S3 | Object storage, data lake foundation |
| Lambda | Serverless compute, event-driven |
| Glue | Managed Spark ETL, Data Catalog |
| Athena | Serverless SQL on S3 |
| Step Functions | Orchestrate workflows/pipelines |
| EventBridge | Event-driven triggers and routing |
| RDS | Managed relational DB (PostgreSQL) |
| CloudWatch | Logging, metrics, alarms |
| VPC | Network isolation |
