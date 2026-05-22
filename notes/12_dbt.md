# dbt (Data Build Tool) — Complete Notes from Scratch

---

## Why dbt Changed Data Engineering

Before dbt, the transformation layer in a data warehouse was a graveyard of stored procedures, undocumented SQL scripts, and ad-hoc queries. Changes were made directly in the warehouse UI, nobody knew where the truth was, and rolling back a transformation meant hoping you remembered what you did yesterday.

dbt changed this by treating SQL transformations like software: version-controlled, tested, documented, and deployed through CI/CD.

> **🌍 Real world:** dbt's rise mirrors the shift from ETL to ELT. When compute was expensive, you transformed before loading (ETL). Now that warehouse compute is cheap (Snowflake, BigQuery, Redshift), the bottleneck is I/O and data quality, not transformation speed. So the pattern flipped: extract raw data directly into the warehouse, then transform in place (ELT). dbt became the standard tool for the T in ELT.

---

## 1. What Is dbt

The most important thing to understand is what dbt does NOT do. It does not extract data from source systems. It does not load data into the warehouse. It only transforms data that is already in the warehouse.

```
dbt = transformation layer only (the T in ELT)
- Write SELECT statements, dbt handles the CREATE TABLE/VIEW
- Version-controlled SQL transformations
- Built-in testing, documentation, lineage
- Works with: Snowflake, BigQuery, Redshift, PostgreSQL, Databricks

What dbt does NOT do:
- Data extraction (no connectors to source systems)
- Data loading (that's Fivetran, Airbyte, COPY command)
- Orchestration (use Airflow, dbt Cloud Scheduler)

The modern ELT stack:
Fivetran/Airbyte → warehouse (raw data) → dbt → analytics/dashboards
```

> **💡 Interview tip:** "What does dbt do?" A common trap is saying dbt is an ETL tool. It is NOT. It's purely the T in ELT. You still need a separate tool (Fivetran, Airbyte, Kafka, custom script) to get data into the warehouse. dbt only transforms what's already there.

---

## 2. Project Structure

dbt's folder structure is opinionated by convention, and the convention reflects a layered data modeling philosophy. Staging models clean raw source data (rename columns, cast types, filter deletes). Intermediate models combine staging with business logic. Marts are business-ready tables and views.

```
my_dbt_project/
├── dbt_project.yml          ← project config (name, profile, paths)
├── profiles.yml             ← connection details (usually in ~/.dbt/)
├── models/                  ← SQL transformations (the main work)
│   ├── staging/             ← clean raw source data
│   │   ├── stg_orders.sql
│   │   ├── stg_customers.sql
│   │   └── _staging__sources.yml  ← source definitions
│   ├── intermediate/        ← complex joins/business logic
│   │   └── int_orders_with_customers.sql
│   └── marts/               ← final business-ready models
│       ├── orders/
│       │   ├── fct_orders.sql
│       │   └── dim_customers.sql
│       └── _orders__models.yml  ← model documentation + tests
├── seeds/                   ← static CSV data loaded to DB
│   └── country_codes.csv
├── snapshots/               ← SCD Type 2 snapshots
│   └── customers_snapshot.sql
├── tests/                   ← custom data tests
│   └── assert_positive_amounts.sql
├── macros/                  ← reusable Jinja/SQL snippets
│   └── generate_schema_name.sql
└── analyses/                ← ad-hoc SQL (not materialized)
```

> **🌍 Real world:** The staging → intermediate → marts layer structure is the Kimball-influenced pattern that most dbt shops converge on. Staging models are 1:1 with source tables (one staging model per source table). This makes it easy to reason about data quality at the entry point. Intermediate models combine multiple staging models with joins and filtering. Marts are the final, optimized tables that dashboards and analysts use.

---

## 3. Models — SQL SELECT Statements

### Basic Model

dbt's core abstraction is beautiful in its simplicity: you write a SELECT statement, dbt figures out whether to wrap it in `CREATE VIEW AS` or `CREATE TABLE AS` or `MERGE INTO`. You focus on the transformation logic, not the DDL.

```sql
-- models/staging/stg_orders.sql
-- dbt creates a table/view named 'stg_orders' in your warehouse

SELECT
    id                          AS order_id,
    customer_id,
    CAST(amount AS DECIMAL(10,2)) AS amount,
    status,
    LOWER(TRIM(source_channel)) AS channel,
    CAST(created_at AS TIMESTAMP) AS created_at
FROM {{ source('raw', 'orders') }}   -- reference a source table
WHERE _fivetran_deleted = FALSE
```

### Referencing Other Models

`ref()` is the magic that makes dbt more than just a SQL runner. When you write `{{ ref('stg_orders') }}`, dbt knows this model depends on `stg_orders` and will build `stg_orders` first, every time, automatically.

```sql
-- models/marts/fct_orders.sql

SELECT
    o.order_id,
    o.amount,
    o.status,
    o.created_at,
    c.customer_name,
    c.country,
    d.year,
    d.quarter
FROM {{ ref('stg_orders') }} o          -- ref() creates dependency
JOIN {{ ref('stg_customers') }} c ON o.customer_id = c.customer_id
JOIN {{ ref('dim_date') }} d ON DATE(o.created_at) = d.full_date
WHERE o.status = 'completed'
```

**`ref()` vs `source()`:**
```
ref('model_name')         — reference a dbt model you've built
source('source', 'table') — reference raw source table in warehouse
```

> **💡 Interview tip:** "How does dbt determine the order in which to build models?" dbt parses all `ref()` calls in all models to build a Directed Acyclic Graph (DAG) of dependencies. It then topologically sorts the DAG and builds models in dependency order. This is why circular dependencies are not allowed.

---

## 4. Materialisation Types

Materialization is how dbt decides what SQL to execute when building a model. Choose it based on the tradeoff between query freshness and build cost.

- Views: free to build, cost at query time (recalculated every time someone runs the view)
- Tables: cost at build time, free at query time (pre-computed)
- Incremental: cost at build time for new data only
- Ephemeral: zero cost — inlined as a CTE, never actually written to the warehouse

```sql
-- Set globally in dbt_project.yml or per-model with config block

-- View (default): recreated every run, no storage
{{ config(materialized='view') }}
SELECT ...

-- Table: drops and recreates table every run
{{ config(materialized='table') }}
SELECT ...

-- Incremental: only process new/changed records
{% raw %}
{{ config(
    materialized='incremental',
    unique_key='order_id',
    on_schema_change='append_new_columns'
) }}
{% endraw %}
SELECT ...
{% raw %}
{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
{% endraw %}

-- Ephemeral: not materialized — injected as CTE into downstream models
{{ config(materialized='ephemeral') }}
SELECT ...
```

### dbt_project.yml — Global Materialisation Config

Set materialization defaults at the folder level so individual models don't need config blocks. Staging = views (cheap, always fresh from source). Intermediate = ephemeral (no storage needed, just CTEs). Marts = tables (expensive to build, cheap to query).

```yaml
name: my_project
version: '1.0.0'
profile: my_profile

models:
  my_project:
    staging:
      +materialized: view        # all staging models = views
    intermediate:
      +materialized: ephemeral   # injected as CTEs
    marts:
      +materialized: table       # all marts = tables
      orders:
        fct_orders:
          +materialized: incremental  # override specific model
```

---

## 5. Sources

Sources are how dbt knows about raw data that wasn't built by dbt itself. Declaring sources in YAML does two things: (1) it gives you `source()` function references with proper schema resolution, (2) it lets dbt monitor source freshness (how recently raw data was updated).

```yaml
# models/staging/_staging__sources.yml
version: 2

sources:
  - name: raw                     # source name used in source()
    database: my_warehouse
    schema: raw_data
    
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    loaded_at_field: _fivetran_synced  # field to check freshness
    
    tables:
      - name: orders
        description: "Raw orders from Fivetran Shopify connector"
        columns:
          - name: id
            description: "Order ID from Shopify"
          - name: created_at
      
      - name: customers
        identifier: shopify_customers   # actual table name if different
```

```bash
# Check source freshness
dbt source freshness
```

---

## 6. Tests

dbt tests are the mechanism that lets you catch data regressions before they reach production. The workflow is: tests run in CI on every PR. A failing test blocks the PR merge. No bad data reaches production dashboards. Ever.

### Schema Tests (YAML)

The four built-in tests cover the most common assertions. The `relationships` test is particularly powerful — it's a foreign key check that ensures referential integrity between your dbt models (unlike traditional database FKs, dbt doesn't enforce them in the warehouse, it just tests them).

```yaml
# models/marts/_orders__models.yml
version: 2

models:
  - name: fct_orders
    description: "One row per completed order"
    
    columns:
      - name: order_id
        description: "Unique order identifier"
        tests:
          - not_null
          - unique
      
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
      
      - name: status
        tests:
          - accepted_values:
              values: ['completed', 'refunded', 'cancelled']
      
      - name: amount
        tests:
          - not_null
    
    tests:
      - dbt_utils.recency:
          datepart: day
          field: created_at
          interval: 1
```

### Custom Data Tests (SQL)

Custom SQL tests let you encode any business rule that doesn't fit the four built-in tests. The contract is simple: write a query that returns rows when the rule is VIOLATED. dbt runs the query and fails the test if any rows are returned (meaning the rule was violated).

```sql
-- tests/assert_positive_order_amounts.sql
-- Test FAILS if this query returns ANY rows

SELECT order_id, amount
FROM {{ ref('fct_orders') }}
WHERE amount <= 0
```

```bash
dbt test                           # run all tests
dbt test --select fct_orders       # test specific model
dbt test --select tag:daily        # test models with tag
```

> **💡 Interview tip:** "How do you prevent data quality regressions in dbt?" Full answer: (1) dbt schema tests (not_null, unique, accepted_values, relationships) catch structural problems, (2) custom SQL tests catch business rule violations, (3) tests run in CI/CD on every PR before merge, (4) Great Expectations or Soda can be run post-dbt for advanced profiling.

---

## 7. Incremental Models — Deep Dive

Incremental models are the most important materialization to deeply understand. The premise: if your `fct_events` table has 10 billion rows and you add 5 million new rows per day, rebuilding the entire table from scratch every day is wasteful. Instead, process only the new/changed rows and merge them into the existing table.

The key concepts to understand:
- `unique_key` — the column dbt uses to identify whether a row is new (insert) or existing (update)
- `is_incremental()` — a Jinja function that returns `True` during incremental runs and `False` during full refreshes, used to filter the source data
- `{{ this }}` — a special reference to the *current state of the model's table* in the warehouse, used to find the high-water mark

```sql
-- models/marts/fct_events.sql
{% raw %}
{{ config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    partition_by={
        "field": "event_date",
        "data_type": "date",
        "granularity": "day"
    }
) }}

SELECT
    event_id,
    user_id,
    event_type,
    amount,
    event_ts,
    CAST(event_ts AS DATE) AS event_date
FROM {{ source('raw', 'events') }}

{% if is_incremental() %}
    WHERE event_ts > (
        SELECT COALESCE(MAX(event_ts), '1900-01-01'::TIMESTAMP)
        FROM {{ this }}
    )
{% endif %}
{% endraw %}
```

**Incremental strategies:**
```
append:         insert new rows only (no dedup, no updates)
merge:          UPSERT on unique_key (handles updates)
delete+insert:  delete matching rows, re-insert (partition refresh)
```

> **💡 Interview tip:** This is one of the most common dbt deep-dive interview questions. Key points: (1) `is_incremental()` is `False` on the first run (when the table doesn't exist yet) and on `dbt run --full-refresh` (force rebuild), (2) the high-water mark pattern filters to new data, (3) `unique_key` tells dbt which rows are duplicates to deduplicate/update, (4) `on_schema_change` handles when new columns are added to the source.

> **🌍 Real world:** A subtle incremental model gotcha: if your source data can arrive *late* (events from yesterday appearing today), your high-water mark approach (`WHERE event_ts > MAX(event_ts)`) will miss those rows. Use `dbt run --full-refresh` on a schedule (weekly), or use a check-based strategy that compares hashes of all columns.

---

## 8. Snapshots — SCD Type 2

SCD Type 2 (Slowly Changing Dimensions) is the pattern of tracking historical changes to dimension records: when a customer changes their email address, you want to keep both the old and new email, with timestamps indicating when each was valid.

Before dbt, implementing SCD Type 2 required custom code: detect changes, close the old record (`valid_to = NOW()`), insert a new record. dbt snapshots do this automatically. You write a SELECT statement, dbt handles the rest.

```sql
-- snapshots/customers_snapshot.sql
{% raw %}
{% snapshot customers_snapshot %}

{{ config(
    target_schema='snapshots',
    unique_key='customer_id',
    strategy='timestamp',
    updated_at='updated_at',
    invalidate_hard_deletes=True
) }}

SELECT
    customer_id,
    email,
    name,
    tier,
    updated_at
FROM {{ source('raw', 'customers') }}

{% endsnapshot %}
{% endraw %}
```

```
Result: snapshots.customers_snapshot
| customer_id | email          | tier   | dbt_valid_from      | dbt_valid_to        | dbt_is_current |
|-------------|----------------|--------|---------------------|---------------------|----------------|
| 1           | old@email.com  | silver | 2025-01-01 00:00:00 | 2025-05-01 00:00:00 | false          |
| 1           | new@email.com  | gold   | 2025-05-01 00:00:00 | null                | true           |
```

```bash
dbt snapshot   # run snapshots
```

> **💡 Interview tip:** "How do you implement SCD Type 2 in dbt?" Answer: dbt snapshots. The `timestamp` strategy detects changes by comparing `updated_at` values. The `check` strategy detects changes by hashing selected columns. The dbt snapshot table automatically adds `dbt_valid_from`, `dbt_valid_to`, and `dbt_is_current` columns.

> **🌍 Real world:** Run `dbt snapshot` before `dbt run` in your daily pipeline, so snapshots capture the current state of source tables before transformations run. If you run snapshots after, you'll miss any changes that happened during the `dbt run`.

---

## 9. Jinja Templating in dbt

Jinja is a Python templating language that dbt uses to make SQL dynamic. The killer use case for DE is environment-specific behavior: in dev, limit queries to 1000 rows to iterate fast; in prod, run on full data. Or: use a parameter to set `start_date` without editing SQL.

```sql
-- Variables
{{ var('start_date', '2025-01-01') }}   -- use with --vars '{"start_date": "2025-05-01"}'

-- Environment variables
{{ env_var('DBT_ENV', 'dev') }}

-- Conditionals
{% raw %}
{% if target.name == 'prod' %}
    LIMIT 1000000
{% else %}
    LIMIT 1000    -- use small data in dev
{% endif %}

-- Loops
{% set metrics = ['revenue', 'quantity', 'discount'] %}
SELECT
{% for metric in metrics %}
    SUM({{ metric }}) AS total_{{ metric }}
    {%- if not loop.last %},{% endif %}
{% endfor %}
FROM fct_orders
{% endraw %}
```

---

## 10. Macros

Macros are reusable pieces of Jinja/SQL — think of them as functions for your SQL code. Instead of copy-pasting the same cents-to-dollars conversion in 15 models, write it once as a macro and call it 15 times.

```sql
-- macros/cents_to_dollars.sql
{% raw %}
{% macro cents_to_dollars(column_name, scale=2) %}
    ROUND({{ column_name }} / 100, {{ scale }})
{% endmacro %}
{% endraw %}

-- Usage in model:
SELECT
    order_id,
    {{ cents_to_dollars('amount_cents') }} AS amount_dollars
FROM raw_orders
```

```sql
-- macros/generate_date_spine.sql
{% raw %}
{% macro date_spine(start_date, end_date) %}
    WITH date_series AS (
        SELECT DATEADD(day, seq, '{{ start_date }}'::DATE) AS date_day
        FROM TABLE(GENERATOR(rowcount => DATEDIFF(day, '{{ start_date }}'::DATE, '{{ end_date }}'::DATE) + 1))
    )
    SELECT * FROM date_series
{% endmacro %}
{% endraw %}
```

---

## 11. Packages

dbt packages are shared libraries of macros, models, and tests. The `dbt_utils` package is nearly universal — it provides utilities like `surrogate_key()` (consistent cross-platform hashing for generating unique IDs), `recency()` testing, date spines, and more.

```yaml
# packages.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
  - package: calogica/dbt_expectations
    version: 0.10.0
  - package: dbt-labs/dbt_date
    version: 0.10.0
```

```bash
dbt deps   # install packages
```

**Useful packages:**
```
dbt_utils:           generic tests, macros, date_spine, surrogate_key
dbt_expectations:    200+ data quality tests (like Great Expectations in YAML)
dbt_date:            date spine, fiscal periods
dbt_meta_testing:    enforce documentation coverage
```

---

## 12. CLI Commands

Understanding the selector syntax (`+`, `@`, folder paths, tags) is important for both development efficiency and CI optimization. Running `+fct_orders` (fct_orders and all upstream dependencies) is how you test a focused part of the DAG without building the whole warehouse.

```bash
dbt run                          # run all models
dbt run --select stg_orders      # run specific model
dbt run --select staging.*       # run all in staging folder
dbt run --select +fct_orders     # run fct_orders and all upstream deps
dbt run --select fct_orders+     # run fct_orders and all downstream
dbt run --select @fct_orders     # full lineage (upstream + self + downstream)
dbt run --exclude stg_payments   # run all except

dbt test                         # run all tests
dbt snapshot                     # run snapshots
dbt seed                         # load CSV seed files

dbt docs generate                # generate documentation site
dbt docs serve                   # open docs in browser (lineage graph!)

dbt compile                      # compile SQL without running
dbt debug                        # test connection

dbt run --full-refresh           # force recreate incremental model from scratch

dbt run --target prod            # run against prod profile
```

> **💡 Interview tip:** `dbt run --full-refresh` on an incremental model drops and recreates the table from scratch, processing all historical data. Know when to use it: (1) after adding new columns, (2) after changing business logic that affects historical correctness, (3) on a schedule (weekly) to catch late-arriving data.

> **🌍 Real world:** In CI, you typically don't run the full dbt project on every PR — that would be expensive and slow. Instead, use the "slim CI" pattern: run only the models that changed and their downstream dependents. This is supported by dbt Cloud's enhanced parsing, or by explicit selector logic in your CI config.

---

## 13. dbt + Airflow Integration

dbt transformations typically run as a step in a larger Airflow DAG — after raw data is loaded by an ingestion job, dbt runs to transform it. The two common approaches are dbt Cloud (managed, with Airflow integration) or dbt Core (self-hosted, run via BashOperator).

```python
from airflow.providers.dbt.cloud.operators.dbt import DbtCloudRunJobOperator

# dbt Cloud
DbtCloudRunJobOperator(
    task_id='run_dbt_transformations',
    job_id=12345,
    dbt_cloud_conn_id='dbt_cloud_default',
    check_interval=60,
    timeout=3600,
)

# dbt Core via BashOperator
from airflow.operators.bash import BashOperator

BashOperator(
    task_id='dbt_run',
    bash_command='cd /opt/dbt && dbt run --profiles-dir . --target prod',
)
```

> **🌍 Real world:** A mature dbt + Airflow integration typically looks like: (1) ingest raw data (Fivetran sync, Glue job, Kafka consumer), (2) `dbt source freshness` to validate raw data arrived, (3) `dbt run` to transform, (4) `dbt test` to validate output, (5) alerting on failures. Orchestrate all of this in Airflow with data-aware task dependencies.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| dbt model | A SELECT statement — dbt handles materialization |
| ref() | Reference another dbt model — creates dependency |
| source() | Reference raw source table in warehouse |
| View | Recreated each run, no storage (default for staging) |
| Table | Dropped and recreated each run |
| Incremental | Only process new/changed records — needs unique_key |
| Snapshot | SCD Type 2 — tracks historical changes automatically |
| is_incremental() | Returns True on incremental runs, False on full refresh |
| Schema tests | YAML: not_null, unique, accepted_values, relationships |
| Custom test | SQL: fails if returns any rows |
| Jinja | Templating: variables, conditionals, loops in SQL |
| dbt docs | Auto-generated lineage graph + documentation |
