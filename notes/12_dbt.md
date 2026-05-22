# dbt (Data Build Tool) — Complete Notes from Scratch

---

## Why dbt Changed Data Engineering

Before dbt, the transformation layer in a data warehouse was a graveyard of stored procedures, undocumented SQL scripts, and ad-hoc queries. Changes were made directly in the warehouse UI, nobody knew what depended on what, and there were no tests to catch regressions. dbt brought software engineering practices — version control, testing, documentation, code review — to SQL transformations. For senior DE interviews, dbt fluency is now essentially table stakes.

> **🌍 Real world:** dbt's rise mirrors the shift from ETL to ELT. When compute was expensive, you transformed before loading (ETL). Now that warehouse compute is cheap (Snowflake, BigQuery, Redshift), you load raw data first and transform in-warehouse (ELT). dbt is the tool that made the T in ELT manageable at scale.

---

## 1. What Is dbt

The most important thing to understand is what dbt does NOT do. It does not extract data from source systems. It does not load data into the warehouse. It only transforms data that is already in the warehouse. This clean separation of concerns is what makes dbt powerful — it focuses on doing one thing excellently.

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

> **💡 Interview tip:** "What does dbt do?" A common trap is saying dbt is an ETL tool. It is NOT. It's purely the T in ELT. You still need a separate tool (Fivetran, Airbyte, Kafka, custom scripts) to extract and load raw data into the warehouse. dbt picks up from there, transforming that raw data into analytics-ready models.

---

## 2. Project Structure

dbt's folder structure is opinionated by convention, and the convention reflects a layered data modeling philosophy. Staging models clean raw source data (rename columns, cast types, filter deleted rows). Intermediate models handle complex business logic joins. Mart models are the final, business-ready tables that analysts query. This layering means any transformation is touched in exactly one place.

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

> **🌍 Real world:** The staging → intermediate → marts layer structure is the Kimball-influenced pattern that most dbt shops converge on. Staging models are 1:1 with source tables (one staging model per source table). Marts are organized by business domain (finance, marketing, product). Intermediate models handle anything too complex for staging but not final enough for marts.

---

## 3. Models — SQL SELECT Statements

### Basic Model

dbt's core abstraction is beautiful in its simplicity: you write a SELECT statement, dbt figures out whether to wrap it in `CREATE VIEW AS` or `CREATE TABLE AS` or `MERGE INTO`. You focus on the transformation logic; dbt handles the DDL.

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

`ref()` is the magic that makes dbt more than just a SQL runner. When you write `{{ ref('stg_orders') }}`, dbt knows this model depends on `stg_orders` and will build `stg_orders` first, every time, automatically. It also substitutes the correct schema-qualified table name for the target environment — no hardcoding schema names.

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

> **💡 Interview tip:** "How does dbt determine the order in which to build models?" dbt parses all `ref()` calls in all models to build a Directed Acyclic Graph (DAG) of dependencies. It then performs a topological sort and builds models in dependency order. This means you never need to specify build order — just use `ref()` and dbt figures it out. If you have a circular dependency (`model_a` refs `model_b` which refs `model_a`), dbt will fail with an error because a DAG cannot have cycles.

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
{{ config(
    materialized='incremental',
    unique_key='order_id',           -- merge on this key
    on_schema_change='append_new_columns'
) }}
SELECT ...
{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}

-- Ephemeral: not materialized — injected as CTE into downstream models
{{ config(materialized='ephemeral') }}
SELECT ...
```

### dbt_project.yml — Global Materialisation Config

Set materialization defaults at the folder level so individual models don't need config blocks. Staging = views (cheap, always fresh from source). Intermediate = ephemeral (no storage needed, just reusable SQL). Marts = tables (fast for analysts to query).

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

Sources are how dbt knows about raw data that wasn't built by dbt itself. Declaring sources in YAML does two things: (1) it gives you `source()` function references with proper schema resolution, and (2) it enables `dbt source freshness` to check when the raw data was last updated. If Fivetran hasn't synced in 24 hours, `dbt source freshness` will warn or error before you waste time running transformations on stale data.

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

dbt tests are the mechanism that lets you catch data regressions before they reach production. The workflow is: tests run in CI on every PR. A failing test blocks the PR merge. No bad data reaches the production dbt run. This is the data engineering equivalent of unit tests blocking a broken code merge.

### Schema Tests (YAML)

The four built-in tests cover the most common assertions. The `relationships` test is particularly powerful — it's a foreign key check that ensures referential integrity between your dbt models.

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

Custom SQL tests let you encode any business rule that doesn't fit the four built-in tests. The contract is simple: write a query that returns rows when the rule is VIOLATED. dbt runs the query and fails the test if any rows are returned.

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

> **💡 Interview tip:** "How do you prevent data quality regressions in dbt?" Full answer: (1) dbt schema tests (not_null, unique, accepted_values, relationships) catch structural problems, (2) custom SQL tests catch business-rule violations, (3) tests run in CI on every PR so regressions are caught before merge, (4) `dbt source freshness` catches stale upstream data before wasting compute on a full run, (5) `dbt_expectations` package provides 200+ additional test types similar to Great Expectations.

---

## 7. Incremental Models — Deep Dive

Incremental models are the most important materialization to deeply understand. The premise: if your `fct_events` table has 10 billion rows and you add 5 million new rows per day, rebuilding the entire table daily is extremely expensive. Incremental models solve this by only processing new or changed rows and merging them into the existing table.

The key concepts to understand:
- `unique_key` — the column dbt uses to identify whether a row is new (insert) or existing (update)
- `is_incremental()` — a Jinja function that returns `True` during incremental runs and `False` during full refreshes, used to filter the source data
- `{{ this }}` — a special reference to the *current state of the model's table* in the warehouse, used to find the high-water mark

```sql
-- models/marts/fct_events.sql
{{ config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',    -- merge | append | delete+insert
    on_schema_change='append_new_columns',
    partition_by={
        "field": "event_date",
        "data_type": "date",
        "granularity": "day"
    }  -- BigQuery / Snowflake
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
    -- Only process new events since last run
    WHERE event_ts > (
        SELECT COALESCE(MAX(event_ts), '1900-01-01'::TIMESTAMP)
        FROM {{ this }}
    )
{% endif %}
```

**Incremental strategies:**
```
append:         insert new rows only (no dedup, no updates)
merge:          UPSERT on unique_key (handles updates)
delete+insert:  delete matching rows, re-insert (partition refresh)
```

> **💡 Interview tip:** This is one of the most common dbt deep-dive interview questions. Key points: (1) `is_incremental()` is `False` on the first run (when the table doesn't exist yet) and on `--full-refresh`, so the WHERE filter is omitted and all data is loaded — this is intentional and correct; (2) the `merge` strategy requires a `unique_key` so dbt knows whether to insert or update; (3) use `--full-refresh` periodically (weekly, monthly) to reprocess the full history and correct any late-arriving data that the incremental filter would have missed.

> **🌍 Real world:** A subtle incremental model gotcha: if your source data can arrive *late* (events from yesterday appearing today), your high-water mark approach (`WHERE event_ts > MAX(event_ts)`) will miss them. Solutions: use a lookback window (`WHERE event_ts > MAX(event_ts) - INTERVAL '3 days'`) to reprocess recent days, or use `delete+insert` strategy on date partitions to fully refresh recent partitions.

---

## 8. Snapshots — SCD Type 2

SCD Type 2 (Slowly Changing Dimensions) is the pattern of tracking historical changes to dimension records: when a customer changes their email address, you want to keep both the old and new email with validity timestamps so you can correctly attribute historical orders to the right email address.

Before dbt, implementing SCD Type 2 required custom code: detect changes, close the old record (`valid_to = NOW()`), insert a new record. dbt snapshots do this automatically. You write a SELECT statement returning the current state; dbt handles detecting changes and maintaining the history table.

```sql
-- snapshots/customers_snapshot.sql
{% snapshot customers_snapshot %}

{{ config(
    target_schema='snapshots',
    unique_key='customer_id',
    strategy='timestamp',            -- timestamp | check
    updated_at='updated_at',         -- for timestamp strategy
    -- check_cols=['email', 'tier'], -- for check strategy (compares columns)
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

> **💡 Interview tip:** "How do you implement SCD Type 2 in dbt?" Answer: dbt snapshots. The `timestamp` strategy detects changes by comparing `updated_at` values. The `check` strategy detects changes by comparing specific column values (useful when source data doesn't have a reliable `updated_at`). dbt automatically adds `dbt_valid_from`, `dbt_valid_to`, and `dbt_scd_id` columns. To query "what was this customer's tier at a specific date", filter `WHERE dbt_valid_from <= target_date AND (dbt_valid_to > target_date OR dbt_valid_to IS NULL)`.

> **🌍 Real world:** Run `dbt snapshot` before `dbt run` in your daily pipeline, so snapshots capture the current state of source tables before transformations run. If you run snapshots after, you might miss a day's worth of changes if a record was created and updated within the same day.

---

## 9. Jinja Templating in dbt

Jinja is a Python templating language that dbt uses to make SQL dynamic. The killer use case for DE is environment-specific behavior: in dev, limit queries to 1000 rows to iterate fast; in prod, process everything. This pattern alone saves enormous development time.

```sql
-- Variables
{{ var('start_date', '2025-01-01') }}   -- use with --vars '{"start_date": "2025-05-01"}'

-- Environment variables
{{ env_var('DBT_ENV', 'dev') }}

-- Conditionals
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
```

---

## 10. Macros

Macros are reusable pieces of Jinja/SQL — think of them as functions for your SQL code. Instead of copy-pasting the same cents-to-dollars conversion in 15 models, write it once as a macro and call it everywhere. When the logic changes, change it in one place.

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name, scale=2) %}
    ROUND({{ column_name }} / 100, {{ scale }})
{% endmacro %}

-- Usage in model:
SELECT
    order_id,
    {{ cents_to_dollars('amount_cents') }} AS amount_dollars
FROM raw_orders
```

```sql
-- macros/generate_date_spine.sql
{% macro date_spine(start_date, end_date) %}
    WITH date_series AS (
        SELECT DATEADD(day, seq, '{{ start_date }}'::DATE) AS date_day
        FROM TABLE(GENERATOR(rowcount => DATEDIFF(day, '{{ start_date }}'::DATE, '{{ end_date }}'::DATE) + 1))
    )
    SELECT * FROM date_series
{% endmacro %}
```

---

## 11. Packages

dbt packages are shared libraries of macros, models, and tests. The `dbt_utils` package is nearly universal — it provides utilities like `surrogate_key()` (consistent cross-platform hashing for surrogate PKs), `date_spine` (generate a calendar table), and generic tests. `dbt_expectations` brings Great Expectations-style testing into native dbt YAML.

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

Understanding the selector syntax (`+`, `@`, folder paths, tags) is important for both development efficiency and CI optimization. Running `+fct_orders` (fct_orders and all upstream dependencies) is how you re-run a full lineage after changing a staging model.

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

> **💡 Interview tip:** `dbt run --full-refresh` on an incremental model drops and recreates the table from scratch, processing all historical data. Know when to use it: (1) after adding new columns to an incremental model (schema change), (2) after fixing a bug in the transformation logic that affected historical data, (3) on a scheduled basis (e.g., weekly) to correct late-arriving data the incremental filter missed.

> **🌍 Real world:** In CI, you typically don't run the full dbt project on every PR — that would be expensive and slow. Instead, use the "slim CI" pattern: run only the models that changed and their downstream dependents. `dbt run --select state:modified+` (using dbt's state comparison against the production manifest) runs only what changed. This makes CI fast and cheap.

---

## 13. dbt + Airflow Integration

dbt transformations typically run as a step in a larger Airflow DAG — after raw data is loaded by an ingestion job, dbt runs to transform it. The two common approaches are dbt Cloud (managed, with an API) or dbt Core running via BashOperator.

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

> **🌍 Real world:** A mature dbt + Airflow integration typically looks like: (1) ingest raw data (Fivetran sync, Glue job, Kafka consumer), (2) `dbt source freshness` to validate raw data arrived, (3) `dbt run` to transform, (4) `dbt test` to validate output, (5) notify downstream consumers (Slack message, Tableau datasource refresh). Steps 2-4 are the dbt-specific piece; Airflow orchestrates the full pipeline including the non-dbt steps.

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
