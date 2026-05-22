# Data Quality & Observability — Complete Notes from Scratch

---

## Why Data Quality Is Not Optional

Before diving into the mechanics, it's worth internalizing why this matters enough to deserve its own discipline. Bad data doesn't announce itself — it silently flows through pipelines, gets aggregated into dashboards, and informs business decisions. By the time someone notices the revenue numbers look wrong, the bad data has already been used to make budget decisions, staffed up teams, or cut product lines. The cost of fixing data quality problems compounds the longer they go undetected, which is why catching them at the pipeline layer — before data reaches consumers — is always cheaper than discovering them downstream.

> **🌍 Real world:** Industry estimates suggest that bad data costs US businesses over $3 trillion per year. For a DE team, a single silent data quality failure can undermine months of trust built with business stakeholders. Once analysts learn to distrust your pipelines, they start building their own — which creates even more inconsistency.

> **💡 Interview tip:** A common interview question is "what's your approach to data quality?" A strong answer covers the full stack: upstream contracts with producers, automated checks in the pipeline (GE or dbt tests), observability (structured logs + metrics), and alerting. Saying "I add some SQL checks" signals junior thinking; talking about the entire system signals senior thinking.

---

## 1. Data Quality Dimensions

These six dimensions are the vocabulary used to describe data quality problems precisely. Knowing the distinction between completeness and accuracy (a common interview gotcha) is important: a dataset can be complete (all rows exist) but inaccurate (the values are wrong), or accurate for the rows it has but incomplete (many rows are missing entirely).

```
Completeness:  Are all expected records present? Are required fields populated?
               → Row count checks, null checks on required columns

Accuracy:      Do values correctly represent reality?
               → Range checks (age 0-120), format checks, business rules

Consistency:   Is data consistent across systems/tables?
               → Referential integrity, cross-system reconciliation

Timeliness:    Is data fresh enough for its intended use?
               → MAX(event_ts) within expected window

Uniqueness:    Are there duplicate records that shouldn't exist?
               → Primary key uniqueness, deduplication checks

Validity:      Do values conform to expected formats/domains?
               → Email format, phone number format, enum values (status in ['active', 'inactive'])
```

> **💡 Interview tip:** "What's the difference between completeness and accuracy?" Completeness is about whether data is *there* — are all expected rows present, are required columns populated? Accuracy is about whether the data *reflects reality* — is the age value 25 or is it -5? A table can score perfectly on completeness (no nulls, all rows present) while being completely inaccurate (all ages are 999 because of a bad default value).

---

## 2. Data Quality Checks in SQL

SQL checks are the lowest-common-denominator approach to data quality — no framework dependencies, runs anywhere you have a query engine. These are often the first checks DE teams add because they're simple to write and easy for non-engineers to read and verify.

### Row Count Checks

Row count is the most fundamental check. A sudden 80% drop in rows usually means a pipeline broke upstream. A 300% spike might mean data is being double-loaded. Comparing today's count to yesterday's detects both anomalies and gradual drift.

```sql
-- Minimum row count
SELECT COUNT(*) FROM daily_sales WHERE date = CURRENT_DATE;
-- Alert if < 1000 (expected minimum)

-- Compare to previous day (detect anomalies)
SELECT 
    today.cnt AS today_count,
    yesterday.cnt AS yesterday_count,
    ROUND(100.0 * (today.cnt - yesterday.cnt) / yesterday.cnt, 1) AS pct_change
FROM
    (SELECT COUNT(*) AS cnt FROM sales WHERE date = CURRENT_DATE) today,
    (SELECT COUNT(*) AS cnt FROM sales WHERE date = CURRENT_DATE - 1) yesterday;
-- Alert if pct_change > 50% or < -50%
```

### Null Checks

Required fields with nulls are a silent killer — downstream code that assumes a column is always populated will either crash or silently produce wrong aggregations. Tracking null *rate* per column (not just binary null/not-null) lets you catch gradual degradation before it becomes a crisis.

```sql
-- Required fields must not be null
SELECT COUNT(*) FROM orders WHERE customer_id IS NULL;  -- must be 0
SELECT COUNT(*) FROM orders WHERE amount IS NULL;       -- must be 0

-- Null rate per column
SELECT 
    COUNT(*) AS total,
    SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS null_customer,
    SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END) AS null_email,
    ROUND(100.0 * SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS null_pct
FROM customers;
```

### Range and Value Checks

Business rules encoded as SQL constraints catch the kind of data that passes format validation but violates reality. A negative price, an age of 999, or an order date in the future are all technically valid data types but obviously wrong values.

```sql
-- Price must be positive
SELECT COUNT(*) FROM products WHERE price < 0;  -- must be 0

-- Age must be in valid range
SELECT COUNT(*) FROM users WHERE age < 0 OR age > 150;

-- Status must be in allowed values
SELECT DISTINCT status FROM orders
WHERE status NOT IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled');
-- must return 0 rows

-- Date sanity
SELECT COUNT(*) FROM orders WHERE order_date > CURRENT_DATE;  -- future orders?
SELECT COUNT(*) FROM events WHERE event_ts > NOW() + INTERVAL '1 hour';
```

### Referential Integrity

Referential integrity checks catch the case where a foreign key references a primary key that doesn't exist — orders pointing to customers who aren't in the customers table, line items pointing to deleted orders. These are especially common when multiple source systems are synced independently and the sync processes run at different times.

```sql
-- Orders without matching customer
SELECT COUNT(*) 
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id
WHERE c.id IS NULL;
-- must be 0

-- Orphaned line items
SELECT COUNT(*)
FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.id
WHERE o.id IS NULL;
```

### Uniqueness Checks

Duplicate records are one of the most common data quality problems in ETL pipelines — they typically sneak in through at-least-once delivery semantics (Kafka, SQS) or re-runs of idempotent-but-not-exactly-once pipelines.

```sql
-- No duplicate PKs
SELECT customer_id, COUNT(*) 
FROM customers
GROUP BY customer_id
HAVING COUNT(*) > 1;
-- must return 0 rows

-- Business key uniqueness
SELECT email, COUNT(*)
FROM customers
GROUP BY email
HAVING COUNT(*) > 1;
```

### Freshness Check

A pipeline that ran successfully 3 days ago but hasn't run since is just as bad as a failed pipeline — your data is stale. Freshness checks answer the question: "Is the most recent data recent enough to be useful?"

```sql
-- Data must be loaded within last 2 hours
SELECT 
    MAX(event_ts) AS latest_event,
    NOW() - MAX(event_ts) AS data_age
FROM events;
-- Alert if data_age > INTERVAL '2 hours'

-- Table-level freshness
SELECT 
    schemaname,
    tablename,
    last_vacuum,
    last_analyze,
    n_live_tup
FROM pg_stat_user_tables
WHERE tablename = 'events';
```

> **🌍 Real world:** Freshness SLAs vary by use case. A real-time dashboard might need data < 5 minutes old; a daily finance report just needs it available by 8am. Define freshness thresholds per dataset and tie them to business requirements, not engineering convenience.

---

## 3. Great Expectations

Writing custom SQL checks works, but it doesn't scale — each check is ad hoc, hard to document, and doesn't generate any human-readable report of what passed and what failed. Great Expectations takes a declarative approach: you define *expectations* about your data (like a spec), and GE validates actual data against those expectations, then generates documentation showing results. The philosophy is similar to unit testing: write the contract first, validate reality against it.

### Core Concepts
```
Expectation:    a declarative statement about data ("this column should not have nulls")
Expectation Suite: collection of expectations for a dataset
Validation:     running expectations against actual data
Data Docs:      auto-generated HTML docs showing validation results
Datasource:     connection to data (Spark, Pandas, SQL)
Checkpoint:     combines datasource + suite + action for validation workflow
```

### Basic Setup and Expectations

The GE validator API reads like natural language — `expect_column_values_to_be_between` is self-documenting in a way that a raw SQL range check isn't. This matters when you need non-engineers (analysts, product managers) to review and sign off on data quality rules.

```python
import great_expectations as gx

# Initialize context
context = gx.get_context()

# Create expectation suite
suite = context.add_expectation_suite("orders_suite")

# Create validator
validator = context.sources.pandas_default.read_csv("orders.csv")

# Add expectations
validator.expect_column_to_exist("order_id")
validator.expect_column_values_to_not_be_null("order_id")
validator.expect_column_values_to_not_be_null("customer_id")
validator.expect_column_values_to_be_unique("order_id")
validator.expect_column_values_to_be_in_set("status", 
    ["pending", "confirmed", "shipped", "delivered", "cancelled"])
validator.expect_column_values_to_be_between("amount", 0, 100000)
validator.expect_column_values_to_match_regex("email", 
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
validator.expect_table_row_count_to_be_between(min_value=1000, max_value=10000000)
validator.expect_column_mean_to_be_between("amount", min_value=50, max_value=500)

# Save suite
validator.save_expectation_suite()

# Validate and get results
results = validator.validate()
print(results.success)  # True/False
```

### Running with Checkpoint

Checkpoints are what make GE production-ready — they tie together the data source, the expectation suite, and the *actions* to take on validation results (update docs, send Slack notification, fail the pipeline). A checkpoint is the unit you schedule in your CI/CD or Airflow pipeline.

```python
# Checkpoints run validations and trigger actions (slack alert, data docs update)
checkpoint = context.add_checkpoint(
    name="daily_orders_checkpoint",
    validations=[{
        "batch_request": {...},
        "expectation_suite_name": "orders_suite"
    }],
    action_list=[
        {
            "name": "store_validation_result",
            "action": {"class_name": "StoreValidationResultAction"}
        },
        {
            "name": "update_data_docs",
            "action": {"class_name": "UpdateDataDocsAction"}
        },
        {
            "name": "send_slack_notification",
            "action": {
                "class_name": "SlackNotificationAction",
                "slack_webhook": "https://hooks.slack.com/...",
                "notify_on": "failure"
            }
        }
    ]
)

result = checkpoint.run()
```

> **💡 Interview tip:** GE vs custom SQL checks — when does GE win? GE wins when you need: (1) self-documenting checks that non-engineers can read and approve, (2) standardized validation across many datasets, (3) auto-generated Data Docs that act as a data quality catalog. Custom SQL wins when GE's setup overhead isn't justified for a one-off check. In practice, many teams use dbt tests for model-level checks and GE for source data validation.

---

## 4. dbt Tests

dbt tests are the most natural place to enforce data quality for transformed data because they live right next to the models they test and run automatically in CI. The key insight is that a failing dbt test should block a PR merge — this is how you prevent bad data from reaching production.

### Built-in Schema Tests

Schema tests in YAML are declarative and readable. The four built-in tests (`not_null`, `unique`, `accepted_values`, `relationships`) cover the most common data quality assertions. For anything more complex, write a custom SQL test.

```yaml
# models/schema.yml
version: 2

models:
  - name: orders
    columns:
      - name: order_id
        tests:
          - not_null
          - unique
      
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('customers')
              field: id
      
      - name: status
        tests:
          - accepted_values:
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
      
      - name: amount
        tests:
          - not_null

  - name: daily_sales
    tests:
      - dbt_utils.recency:  # from dbt-utils package
          datepart: day
          field: sale_date
          interval: 1
```

### Custom Tests

Custom SQL tests follow a simple contract: the test *fails* if the query returns any rows. Write the query to return rows that represent violations of your business rule.

```sql
-- tests/assert_positive_amounts.sql
-- Test fails if it returns ANY rows
SELECT *
FROM {{ ref('orders') }}
WHERE amount < 0
```

### Running dbt Tests

```bash
dbt test                          # run all tests
dbt test --select orders          # test specific model
dbt test --select source:raw.*    # test source freshness
dbt source freshness              # check source data freshness
```

> **🌍 Real world:** In a mature DE team, dbt tests run in three places: (1) in CI on every PR to catch regressions before merge, (2) after every production dbt run to validate the output, and (3) on a schedule against source data to catch upstream feed problems. Running tests only in CI and not in production is a common gap — source data can fail expectations even when your transformation code is correct.

---

## 5. Soda Core

Soda takes the YAML-declarative approach even further than GE — checks are pure YAML, requiring no Python code to define. This makes it accessible to data analysts and analytics engineers who are comfortable with YAML (from dbt, GitHub Actions, etc.) but not necessarily Python.

```yaml
# checks.yml — declarative YAML-based checks
checks for orders:
  - row_count > 0
  - missing_count(customer_id) = 0
  - duplicate_count(order_id) = 0
  - invalid_count(status) = 0:
      valid values: [pending, confirmed, shipped, delivered, cancelled]
  - min(amount) >= 0
  - max(amount) < 100000
  - freshness(created_at) < 2h
```

```bash
# Run checks
soda scan -d my_postgres -c configuration.yml checks.yml
```

---

## 6. Data Contracts

### What Is a Data Contract

A data contract is a formal agreement between a data producer (the team/system generating data) and data consumers (downstream pipelines, dashboards, data scientists). Without contracts, a producer can rename a column, drop a field, or change a data type — and the first sign that something broke is when a downstream consumer's pipeline fails at 3am. Contracts make breaking changes visible and negotiated, not silent and catastrophic.

Think of it like a REST API contract: if you're building a service that other teams depend on, you don't just change the API response format without versioning it and notifying consumers. Data contracts apply the same discipline to data feeds.

```
Agreement between data producers and consumers defining:
- Schema: column names, types, nullability
- Semantics: what values mean
- SLAs: freshness guarantees, row count expectations
- Quality checks: validation rules
- Versioning: how breaking changes are handled

Why important:
- Prevents silent schema breaks from breaking downstream pipelines
- Makes producers accountable for quality
- Enables consumers to trust the data
```

> **💡 Interview tip:** "How do you prevent a schema change in source data from breaking your pipelines?" The full answer involves multiple layers: data contracts (agreed spec), schema registry or schema evolution policies, automated schema validation in CI (e.g., dbt `source:` definitions catch schema changes), and monitoring alerts when column distributions shift unexpectedly (data drift detection).

### Example Data Contract

```yaml
# contracts/orders.yaml
name: orders
version: "2.1.0"
owner: data-platform-team
sla:
  freshness: 1 hour
  availability: 99.9%

schema:
  - name: order_id
    type: integer
    nullable: false
    unique: true
  - name: customer_id
    type: integer
    nullable: false
  - name: amount
    type: decimal(10,2)
    nullable: false
    checks:
      - min: 0
  - name: status
    type: string
    nullable: false
    domain: [pending, confirmed, shipped, delivered, cancelled]
  - name: created_at
    type: timestamp with time zone
    nullable: false

quality_checks:
  - name: minimum_daily_rows
    check: row_count > 1000
  - name: no_orphan_orders
    check: "SELECT COUNT(*) FROM orders LEFT JOIN customers ON ... WHERE customers.id IS NULL = 0"
```

> **🌍 Real world:** Data contracts are gaining significant traction in 2024-2025. Tools like Soda, Great Expectations, and purpose-built contract frameworks (datacontract.com specification) are standardizing how contracts are defined and enforced. In interviews for senior DE roles, being able to discuss the organizational challenge of contracts — getting producer teams to agree to and maintain them — is as important as the technical implementation.

---

## 7. Pipeline Observability

### Structured Logging

Plain text logs are written for humans to read when something goes wrong. Structured logs (JSON) are written for machines to parse, aggregate, and alert on. The difference is enormous: with plain text logs, finding all failures for a specific job name requires grep and regex. With structured JSON logs, you write a CloudWatch Insights query like `filter job_name = "daily_sales_load" | filter level = "ERROR"` and get results in seconds.

```python
import structlog
import logging

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),  # output as JSON
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger()

# Structured log with context
log.info("etl_job_started",
    job_name="daily_sales_load",
    date="2025-05-21",
    source_bucket="my-bucket"
)

log.info("etl_job_completed",
    job_name="daily_sales_load",
    rows_processed=50000,
    duration_seconds=120,
    output_path="s3://bucket/output/"
)

log.error("etl_job_failed",
    job_name="daily_sales_load",
    error="Connection timeout",
    retry_count=3
)
```

> **💡 Interview tip:** "What's the difference between logging and monitoring?" Logging is recording *events* that happened (job started, error occurred, rows processed). Monitoring is tracking *metrics* over time (job duration trending up, error rate increasing). Both are necessary: logs for root cause analysis, metrics for alerting and trending. Structured logging is the bridge — structured logs can be parsed into metrics automatically.

### Key Pipeline Metrics

Split your metrics into three categories: operational (is the system running?), data quality (is the data good?), and infrastructure (is the platform healthy?).

```
Operational metrics (is the pipeline running?):
- Job duration (alert if > 2x normal)
- Job success/failure rate
- Last successful run time (freshness)
- Rows processed per run

Data metrics (is the data good?):
- Input row count vs output row count
- Null rates on key columns
- Value distribution changes (drift detection)
- Rejected/quarantined record count

Infrastructure metrics:
- Memory usage, CPU utilization
- Disk I/O, network I/O
- Queue depth (Kafka lag, SQS depth)
```

> **🌍 Real world:** Row count ratio (input vs output) is a powerful signal that's cheap to compute. If your ETL normally outputs 95-100% of input rows (with a few filtered), and suddenly outputs 40%, something went wrong — a filter condition change, a bad join, a schema mismatch. This single metric would catch a huge proportion of silent data quality failures.

### CloudWatch for ETL Monitoring

Custom CloudWatch metrics let you treat your ETL pipelines like services with SLAs. Once metrics are emitted, you can build dashboards, set alarms, and use CloudWatch Insights to query log data — all within the AWS ecosystem your infrastructure already lives in.

```python
import boto3

cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

def emit_metric(name, value, unit='Count', dimensions=None):
    cloudwatch.put_metric_data(
        Namespace='ETLPipeline',
        MetricData=[{
            'MetricName': name,
            'Value': value,
            'Unit': unit,
            'Dimensions': dimensions or []
        }]
    )

# Emit after job completes
emit_metric('JobDuration', 120.5, 'Seconds',
    [{'Name': 'JobName', 'Value': 'daily_sales_load'}])
emit_metric('RowsProcessed', 50000, 'Count',
    [{'Name': 'JobName', 'Value': 'daily_sales_load'}])
emit_metric('JobStatus', 1, 'Count',  # 1=success, 0=failure
    [{'Name': 'JobName', 'Value': 'daily_sales_load'}])
```

### CloudWatch Alarms

The `TreatMissingData='breaching'` setting is critical for data pipelines. If your daily job didn't emit any metrics (because it didn't run at all), you want the alarm to fire — not silently pass. Missing data in a monitoring system is itself a signal of failure.

```python
# Create alarm for job failure
cloudwatch.put_metric_alarm(
    AlarmName='ETL-DailySalesLoad-Failure',
    MetricName='JobStatus',
    Namespace='ETLPipeline',
    Dimensions=[{'Name': 'JobName', 'Value': 'daily_sales_load'}],
    Statistic='Minimum',
    Period=3600,  # 1 hour
    EvaluationPeriods=1,
    Threshold=1.0,
    ComparisonOperator='LessThanThreshold',
    TreatMissingData='breaching',  # alert if no data (job didn't run)
    AlarmActions=['arn:aws:sns:::etl-alerts'],
    OKActions=['arn:aws:sns:::etl-alerts']
)
```

---

## 8. Data Lineage

Data lineage answers the question: "Where did this number come from?" For compliance (GDPR, CCPA), lineage answers: "Where does PII flow?" For impact analysis, it answers: "If I rename this column, which 30 downstream dashboards will break?" Without lineage, these questions require manually tracing through code and documentation — which may be stale or nonexistent.

```
Data lineage tracks: where data came from → how it was transformed → where it went

Levels:
1. Table-level: orders → daily_sales_agg → finance_report
2. Column-level: orders.amount → SUM(amount) → daily_sales_agg.total_revenue

Tools:
- dbt: auto-generates lineage DAG (dbt docs generate)
- Apache Atlas: enterprise data catalog with lineage
- OpenLineage: open standard, Marquez backend
- DataHub: LinkedIn's open-source data catalog
- AWS Glue Data Catalog: partial lineage

Why important:
- Impact analysis: "which dashboards break if I rename this column?"
- Root cause: "this report is wrong — trace back to source data"
- Compliance: "where does PII flow?"
```

> **🌍 Real world:** dbt's lineage graph (generated by `dbt docs generate`) is one of the most underappreciated features for senior DE interviews. Being able to say "we use dbt's lineage to do impact analysis before any schema changes — we can see all downstream models before touching a source" demonstrates mature data platform thinking, not just pipeline coding.

> **💡 Interview tip:** "How do you handle PII in your data pipelines?" A complete answer mentions: (1) lineage to track where PII flows, (2) classification in a data catalog, (3) masking/tokenization in the staging layer, (4) access controls at the warehouse level, and (5) retention policies. Lineage is the foundation — you can't enforce policies on data you can't find.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Completeness | All expected records present, required fields populated |
| Accuracy | Values in valid range, correct format |
| Freshness | Data arrived within expected window |
| Uniqueness | No unexpected duplicates |
| Great Expectations | Python DQ framework — expectations + validation + docs |
| dbt tests | YAML schema tests — not_null, unique, accepted_values, relationships |
| Soda Core | YAML checks — simpler than GE |
| Data contracts | Producer-consumer agreement on schema + SLAs + quality |
| Structured logging | JSON logs with context — parseable by CloudWatch Insights |
| CloudWatch metrics | Custom metrics for job duration, rows, success/failure |
| Data lineage | Track data flow — impact analysis, root cause, compliance |
