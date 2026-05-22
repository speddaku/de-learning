# Data Warehousing — Complete Notes from Scratch
## Redshift + Snowflake

---

## 1. Core Concepts

### OLTP vs OLAP

The storage layout choice — row vs columnar — has cascading consequences for every design decision in the warehouse. It's not just an implementation detail; it's the reason the entire set of rules for data warehousing (distribution keys, sort keys, micro-partitions, clustering) exists.

```
OLTP                            OLAP
Row storage                     Columnar storage
Normalised (3NF)               Denormalised (star schema)
High write throughput           High read throughput
Small, frequent transactions    Large, complex queries
PostgreSQL, MySQL               Redshift, Snowflake, BigQuery
```

### Columnar Storage — Why It Matters

Imagine a spreadsheet with 1 million rows and 100 columns. A row-oriented database stores that as 1 million complete rows on disk — to read column 47, it has to read all 100 columns of every row. A columnar database stores it as 100 separate columns on disk — to read column 47, it reads only that column's data. For analytical queries that touch 3–4 columns out of 100, this is a 25x reduction in I/O.

The second advantage is compression: within a column, values are homogeneous (all integers, all dates, all product names from a fixed catalog). Homogeneous data compresses dramatically — run-length encoding, dictionary encoding, and bit-packing are all highly effective. A table that takes 100GB row-oriented might be 10–15GB columnar.

```
Row storage (OLTP):
Row 1: [1, Alice, Engineering, 90000]
Row 2: [2, Bob, Marketing, 75000]
→ Great for reading all columns of one row

Columnar storage (OLAP):
id column:     [1, 2, 3, 4, 5...]
name column:   [Alice, Bob, Charlie...]
salary column: [90000, 75000, 85000...]
→ Great for aggregating one column across many rows
→ Compresses well (similar values together)
→ Only reads needed columns (column pruning)

SELECT AVG(salary) FROM employees
→ Row storage: reads ALL columns for every row
→ Columnar: reads ONLY salary column
```

> **💡 Interview tip:** When asked "why is Redshift/Snowflake fast for analytics?", the complete answer has three layers: (1) columnar storage reduces I/O by only reading needed columns; (2) compression reduces the data volume further; (3) massively parallel processing (MPP) splits the work across many CPU cores simultaneously. Any single-reason answer is incomplete.

---

## 2. Amazon Redshift

### Architecture

Redshift is a shared-nothing MPP (Massively Parallel Processing) database. The leader node is the coordinator — it receives queries, builds a plan, and distributes work. Compute nodes do the actual scanning and processing in parallel. Each compute node is subdivided into "slices" that correspond to CPU cores. When you load data into Redshift, it's partitioned across all slices — the goal is always to keep all slices busy simultaneously.

```
Client
  ↓
Leader Node
- Query parsing and planning
- Distributes work to compute nodes
- Aggregates results
  ↓
Compute Nodes (1 to 128)
- Each node has slices (CPU cores)
- Each slice stores part of the data
- Slices work in parallel
```

### Distribution Styles

Distribution style determines where each row lives in the cluster. This is the most performance-critical design decision in Redshift because it determines whether joining two tables requires shuffling data across the network (expensive) or can happen locally on each node (fast).

The core insight: if two tables are joined frequently on `customer_id`, and both tables distribute by `customer_id`, then every row from table A and its matching row from table B live on the same node. The join happens locally — zero network transfer. This is called "co-location."

```sql
-- KEY distribution — rows with same key go to same node
-- Good for large tables joined on that key (co-location = no shuffle)
CREATE TABLE orders (
    order_id INT,
    customer_id INT,
    amount DECIMAL
) DISTSTYLE KEY DISTKEY(customer_id);

-- ALL distribution — full copy on every node
-- Good for small dimension tables (always co-located with any fact)
CREATE TABLE countries (
    country_code CHAR(2),
    name VARCHAR(100)
) DISTSTYLE ALL;

-- EVEN distribution — round-robin across nodes (default)
-- Good for tables with no clear join key, or when other styles cause skew
CREATE TABLE staging_data (...) DISTSTYLE EVEN;

-- AUTO — Redshift decides (recommended for most cases)
CREATE TABLE transactions (...) DISTSTYLE AUTO;

-- How to choose:
-- Fact table joined to dimension: DISTKEY on join column
-- Small dimension (<1M rows): DISTSTYLE ALL
-- No frequent joins: EVEN or AUTO
-- Watch for skew — if one node gets most rows, performance suffers
```

> **💡 Interview tip:** Distribution skew is the silent killer in Redshift. If you DISTKEY on `country_code` and 80% of your data is from the US, 80% of the work lands on one node while others sit idle. `DISTSTYLE EVEN` avoids skew but sacrifices co-location. The right distribution key has both high cardinality (evenly distributed) and is used in your most common join.

> **🌍 Real world:** The standard pattern: fact table on DISTKEY matching the most common join column (usually `customer_id` or `product_id`). Large dimensions on the same DISTKEY to match the fact. Small dimensions (date, country, status) on DISTSTYLE ALL so they're always co-located with everything. This covers 80% of Redshift modeling decisions.

### Sort Keys

Sort keys define the physical sort order of rows on disk. Think of it like a pre-sorted index on your data files. When you filter with `WHERE sale_date BETWEEN '2025-01-01' AND '2025-12-31'`, Redshift knows which blocks on disk contain rows in that date range — it reads only those blocks and skips the rest (called "zone map filtering"). Without a sort key, it has to read every block.

```sql
-- Compound sort key — sorts by columns in order
-- Good for WHERE and ORDER BY on first column
CREATE TABLE sales (
    sale_date DATE,
    customer_id INT,
    amount DECIMAL
) SORTKEY(sale_date, customer_id);  -- compound

-- Interleaved sort key — equal weight to each column
-- Good when queries filter on different columns
CREATE TABLE events (
    event_date DATE,
    user_id INT,
    event_type VARCHAR
) INTERLEAVED SORTKEY(event_date, user_id, event_type);

-- Tips:
-- First sort key column = most common filter/join column
-- Usually date/timestamp for time-series data
-- Compound: faster for range scans on leading columns
-- Interleaved: more flexible, but slower VACUUM
```

> **💡 Interview tip:** Sort keys only help when you filter on the sort key column. If your sort key is `sale_date` but a query filters only on `customer_id`, Redshift still has to scan the entire table. This is why compound sort key column order matters — it's similar to a composite index: the leftmost column must be in the filter for zone map filtering to kick in.

> **🌍 Real world:** The almost-universal best practice for time-series fact tables: first sort key column = the date/timestamp column. Your most common query pattern will be "give me the last 30 days" — with a date sort key, Redshift scans only 30 days' worth of blocks rather than the entire table history.

### VACUUM and ANALYZE

```sql
-- VACUUM — reclaims space from deleted rows, re-sorts unsorted data
VACUUM table_name;
VACUUM SORT ONLY table_name;   -- only re-sort, don't reclaim space
VACUUM DELETE ONLY table_name; -- only reclaim space, don't sort

-- When to run: after bulk deletes/updates, regularly as maintenance
-- Note: Redshift Auto VACUUM runs automatically

-- ANALYZE — updates table statistics for query planner
ANALYZE table_name;
ANALYZE table_name(column1, column2);

-- Run after bulk loads, large updates
-- Stale statistics → bad query plans
```

> **🌍 Real world:** Redshift's MVCC (multi-version concurrency control) marks deleted rows as invisible rather than immediately removing them — they're "ghost rows" that take up space. `VACUUM DELETE ONLY` removes them. `VACUUM SORT ONLY` re-sorts newly inserted rows that arrived out of sort key order. Without VACUUM, sort key effectiveness degrades as your table grows. Auto VACUUM handles this in the background but may lag behind heavy write workloads.

### COPY Command — Loading Data

The `COPY` command is the only efficient way to bulk load data into Redshift. The reason is architectural: `COPY` reads from S3 in parallel across all slices simultaneously — each slice reads a different file. A single `INSERT INTO` or multi-row insert goes through the leader node, bypassing the parallelism entirely.

```sql
-- Most efficient way to load into Redshift
COPY sales
FROM 's3://my-bucket/sales/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
FORMAT AS PARQUET;

-- CSV
COPY employees
FROM 's3://my-bucket/employees.csv'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
FORMAT AS CSV
IGNOREHEADER 1
DELIMITER ','
DATEFORMAT 'YYYY-MM-DD';

-- COPY is parallel — loads from multiple files simultaneously
-- Split files to match number of slices for max performance

-- UNLOAD — export from Redshift to S3
UNLOAD ('SELECT * FROM sales WHERE year = 2025')
TO 's3://my-bucket/sales-2025/'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
FORMAT AS PARQUET
PARALLEL ON;
```

> **💡 Interview tip:** Optimal file count for COPY: split your input files into a multiple of the number of Redshift slices (e.g., if you have 8 slices, use 8, 16, or 32 files). Each slice picks up files to process — if you have 100 slices and 3 files, 97 slices sit idle while 3 work. File count is a tuning lever that can 10x COPY performance.

### Redshift Spectrum

```sql
-- Query data directly in S3 without loading into Redshift
-- External tables defined in Glue Data Catalog

-- Create external schema
CREATE EXTERNAL SCHEMA spectrum
FROM DATA CATALOG
DATABASE 'my_glue_db'
IAM_ROLE 'arn:aws:iam::123456789:role/RedshiftRole'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

-- Create external table
CREATE EXTERNAL TABLE spectrum.sales (
    sale_date DATE,
    customer_id INT,
    amount DECIMAL(10,2)
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://my-bucket/sales/';

-- Query like regular table (but data stays in S3)
SELECT * FROM spectrum.sales WHERE sale_date > '2025-01-01';

-- Join with Redshift internal table
SELECT r.customer_name, s.amount
FROM redshift_internal.customers r
JOIN spectrum.sales s ON r.id = s.customer_id;
```

### WLM — Workload Management

```sql
-- Define queues for different workload types
-- Example: short queries don't get stuck behind long ones

-- Query groups (assigned to WLM queues):
SET query_group TO 'short_queries';
SELECT COUNT(*) FROM sales;

-- WLM config (in console/parameter group):
-- Queue 1: BI dashboard queries — 2 concurrent, 30% memory
-- Queue 2: ETL jobs — 5 concurrent, 50% memory
-- Queue 3: Default — remaining
```

> **🌍 Real world:** Without WLM tuning, a single heavy ETL query can starve all concurrent BI dashboard queries — analysts see their dashboards time out while a 20-minute batch job runs. WLM queues with separate memory and concurrency allocations for interactive vs batch workloads is standard production configuration.

---

## 3. Snowflake

### Architecture — 3 Layers

Snowflake's architectural breakthrough was separating storage from compute completely. In traditional data warehouses (including early Redshift), storage and compute are coupled — more compute means more storage and vice versa. You can't scale one without scaling the other. Snowflake stores data in cloud object storage (S3/GCS/Azure Blob) and computes in independent virtual warehouses. This has profound practical implications.

```
Cloud Services Layer (Brain)
- Authentication & authorization
- Query parsing, optimization, metadata
- Transaction management
- Always on, shared

Virtual Warehouses (Compute)
- Clusters of compute nodes
- Each warehouse is isolated
- Scale up: bigger nodes
- Scale out: more clusters (multi-cluster)
- Pay only when running

Storage Layer
- Columnar, compressed files
- Stored in cloud object storage (S3/Azure Blob/GCS)
- Centralized — shared across all warehouses
- Automatically managed, no vacuuming needed
```

> **💡 Interview tip:** "Why is separated storage/compute a game changer?" Three concrete answers: (1) Multiple teams can query the same data simultaneously with isolated compute — the analytics team's heavy query doesn't slow down the data science team's workload. (2) You can spin up a 2XL warehouse for a one-time large backfill, then shut it down — you only pay for the minutes it ran. (3) There's no VACUUM because Snowflake manages the physical storage automatically — a significant operational burden Redshift administrators know all too well.

### Virtual Warehouses

A virtual warehouse is an independently-sized cluster of compute nodes. The key concept: multiple warehouses all read from the same centralized storage layer. The `XS → XL` size scale roughly doubles the compute at each step. Scaling up increases memory and CPU per query (useful for complex, memory-intensive queries). Multi-cluster scaling adds more copies of the warehouse in parallel (useful for handling many concurrent users).

```sql
-- Create virtual warehouse
CREATE WAREHOUSE analytics_wh
  WAREHOUSE_SIZE = 'MEDIUM'   -- XS, S, M, L, XL, 2XL, 4XL
  AUTO_SUSPEND = 300           -- pause after 5 mins idle
  AUTO_RESUME = TRUE;          -- auto-start on query

-- Scale up for complex queries
ALTER WAREHOUSE analytics_wh SET WAREHOUSE_SIZE = 'LARGE';

-- Multi-cluster for concurrency
CREATE WAREHOUSE high_concurrency_wh
  WAREHOUSE_SIZE = 'MEDIUM'
  MIN_CLUSTER_COUNT = 1
  MAX_CLUSTER_COUNT = 5        -- scale out automatically
  SCALING_POLICY = 'STANDARD';

-- Use different warehouses for different teams
USE WAREHOUSE etl_wh;           -- ETL team
USE WAREHOUSE analytics_wh;     -- analysts
USE WAREHOUSE reporting_wh;     -- dashboards

-- Key insight: storage and compute are SEPARATE
-- Multiple warehouses can read same data simultaneously
-- Pay per second of compute (when running)
```

> **🌍 Real world:** The per-second billing model changes cost architecture significantly. A traditional DW has fixed compute cost 24/7. With Snowflake, ETL warehouses can auto-suspend between scheduled jobs and only cost money while actually running. A warehouse that runs 2 hours per day costs roughly 1/12th of an always-on equivalent. This also means development and testing warehouses are essentially free if developers suspend them when not in use.

### Clustering Keys

Snowflake stores data in "micro-partitions" — immutable columnar files of roughly 50–500MB each. The system automatically creates metadata about the min/max values of each column within each micro-partition. When you query with `WHERE sale_date = '2025-03-15'`, Snowflake uses this metadata to identify which micro-partitions *could* contain rows with that date and skips the rest — this is "micro-partition pruning."

Clustering keys guide how rows are physically arranged across micro-partitions. Without clustering, rows from every date are spread across all micro-partitions; a date filter provides little pruning benefit. With clustering on `sale_date`, rows from similar dates are in the same micro-partitions — a date filter can prune 99%+ of micro-partitions.

```sql
-- Like sort keys in Redshift, but automatic re-clustering
-- Snowflake stores data in micro-partitions (~50-500MB each)

CREATE TABLE sales (
    sale_date DATE,
    customer_id INT,
    amount DECIMAL
)
CLUSTER BY (sale_date);   -- micro-partitions sorted by date

-- Automatic clustering — Snowflake maintains clustering in background
ALTER TABLE sales CLUSTER BY (sale_date, customer_id);

-- When to use:
-- Very large tables (TB+)
-- Frequent filters on specific columns
-- Without clustering: full scan of all micro-partitions
-- With clustering: Snowflake prunes irrelevant micro-partitions

-- Check clustering health
SELECT SYSTEM$CLUSTERING_INFORMATION('sales', '(sale_date)');
```

> **💡 Interview tip:** Clustering keys in Snowflake are different from sort keys in Redshift in an important way: Snowflake handles re-clustering automatically in the background (for a fee) as new data arrives. In Redshift, sort key effectiveness degrades with inserts and requires manual VACUUM to restore. The operational simplicity of Snowflake's automatic clustering is a genuine advantage, especially for append-heavy tables.

### Zero-Copy Cloning

Zero-copy cloning is one of Snowflake's most practically useful features. The implementation uses copy-on-write semantics: the clone initially points to all the same micro-partitions as the original. No data is copied. When either the original or the clone modifies data, only the changed micro-partitions are diverged — the unmodified ones are still shared.

The result: cloning a 10TB production database to create a dev environment is instant and costs nothing in storage — until you actually start modifying data in the clone.

```sql
-- Create instant copy of table/schema/database — no data copied!
-- Underlying data shared until changes made (copy-on-write)

CREATE TABLE sales_backup CLONE sales;
CREATE SCHEMA dev CLONE prod;
CREATE DATABASE dev_db CLONE prod_db;

-- Use cases:
-- Test environment from production (instant, no storage cost)
-- Backup before destructive operation
-- Developer sandboxes
```

> **🌍 Real world:** Zero-copy clone changes the economics of test environments. Previously, spinning up a prod-sized dev environment meant copying terabytes of data — a multi-hour operation costing significant storage. With Snowflake, every developer can have their own sandbox clone of production, created in seconds, at no initial storage cost. This enables "experiment freely, break nothing" development workflows. CI/CD pipelines that test dbt models against production-scale data become practical.

> **💡 Interview tip:** Zero-copy clone combined with Time Travel is how you implement safe schema migrations: clone the table, run the migration on the clone, validate, then swap. If something goes wrong, the original is untouched and the clone is just dropped.

### Time Travel

```sql
-- Access historical data — default retention 1-90 days

-- Query data as of specific time
SELECT * FROM sales AT (TIMESTAMP => '2026-05-01 00:00:00'::TIMESTAMP);

-- Query data before specific statement
SELECT * FROM sales BEFORE (STATEMENT => '8e5d0ca9-005e-44e-8071-5c33abce45ec');

-- Restore dropped table
UNDROP TABLE sales;

-- Clone from historical point
CREATE TABLE sales_restored CLONE sales AT (TIMESTAMP => '2026-05-01 00:00:00'::TIMESTAMP);

-- Retention period
ALTER TABLE sales SET DATA_RETENTION_TIME_IN_DAYS = 30;
```

> **🌍 Real world:** Time Travel is your first line of defense when a bad pipeline run corrupts a table. Instead of restoring from a backup (which may be hours old and requires a separate restore process), you query the table as it was before the bad run: `SELECT * FROM sales BEFORE (STATEMENT => '<bad_statement_id>')`. Combine with zero-copy clone to restore the table in seconds.

### Snowpipe — Continuous Ingestion

```sql
-- Automatically ingests new files from S3 as they arrive
-- Uses SQS notifications from S3

CREATE PIPE sales_pipe
AUTO_INGEST = TRUE
AS
COPY INTO raw.sales
FROM @my_s3_stage/sales/
FILE_FORMAT = (TYPE = 'PARQUET');

-- After creating pipe, get SQS ARN and add to S3 event notification
-- New files → S3 event → SQS → Snowpipe → loads data

-- Check pipe status
SELECT SYSTEM$PIPE_STATUS('sales_pipe');
```

### Stages — Loading Data

```sql
-- External stage (S3)
CREATE STAGE my_s3_stage
URL = 's3://my-bucket/data/'
CREDENTIALS = (
    AWS_KEY_ID = '...'
    AWS_SECRET_KEY = '...'
);

-- Or with IAM integration
CREATE STORAGE INTEGRATION s3_int
TYPE = EXTERNAL_STAGE
STORAGE_PROVIDER = 'S3'
ENABLED = TRUE
STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789:role/SnowflakeRole'
STORAGE_ALLOWED_LOCATIONS = ('s3://my-bucket/');

-- COPY into table
COPY INTO sales
FROM @my_s3_stage/sales/
FILE_FORMAT = (TYPE = PARQUET);

-- List stage contents
LIST @my_s3_stage;
```

### Snowflake vs Redshift

| Feature | Snowflake | Redshift |
|---------|-----------|---------|
| Architecture | Separated storage/compute | Coupled (RA3 nodes separate) |
| Scaling | Instant, per-second billing | Manual resize, hourly billing |
| Concurrency | Multi-cluster, auto-scale | WLM queues |
| Maintenance | Zero — no vacuum, auto-optimize | VACUUM + ANALYZE required |
| Data sharing | Native, real-time | Limited (Redshift data sharing) |
| Pricing model | Per second, by warehouse size | Per hour, by node type |
| Semi-structured | VARIANT type, native JSON | Requires flattening |
| Best for | Variable workloads, many concurrent users | Consistent workloads, AWS-native |

> **💡 Interview tip:** The Snowflake vs Redshift question is really about workload patterns. Redshift is a better fit when: workloads are consistent and predictable (always-on compute is cheaper), the org is deeply AWS-native (IAM integration, Glue catalog, Lambda), and the team wants to manage distribution and sort key tuning. Snowflake wins when: workloads are bursty (idle time = no cost), you need zero operational overhead, many teams need isolated compute on shared data, or you need features like zero-copy clone and Time Travel out of the box.

---

## 4. Query Optimisation — Both Platforms

The theme across both platforms is the same: help the engine minimize the amount of data it has to read and move. Columnar storage already reduces I/O — your job as a DE is to not undermine it with patterns that force full scans.

```sql
-- 1. Use columnar-friendly queries — avoid SELECT *
SELECT customer_id, SUM(amount)  -- good
FROM sales GROUP BY customer_id;

SELECT *  -- bad — reads all columns
FROM sales WHERE customer_id = 123;

-- 2. Filter early — reduce data scanned
-- Good: filter on partition/sort/cluster key
WHERE sale_date BETWEEN '2025-01-01' AND '2025-12-31'

-- 3. Avoid functions on filter columns (disables pruning)
-- Bad:
WHERE YEAR(sale_date) = 2025
-- Good:
WHERE sale_date >= '2025-01-01' AND sale_date < '2026-01-01'

-- 4. Join order — filter smaller result before joining
WITH filtered_sales AS (
    SELECT * FROM sales WHERE year = 2025
)
SELECT c.name, SUM(s.amount)
FROM customers c
JOIN filtered_sales s ON c.id = s.customer_id
GROUP BY c.name;

-- 5. Use materialized views for expensive aggregations
CREATE MATERIALIZED VIEW daily_sales_mv AS
SELECT sale_date, SUM(amount) AS total
FROM sales GROUP BY sale_date;
```

> **💡 Interview tip:** `WHERE YEAR(sale_date) = 2025` is the classic anti-pattern. Wrapping the column in a function prevents both zone map pruning (Redshift) and micro-partition pruning (Snowflake) — the engine can no longer determine which partitions are relevant based on the raw column values. Always use range predicates on the raw column: `WHERE sale_date >= '2025-01-01' AND sale_date < '2026-01-01'`.

> **🌍 Real world:** Materialized views are underused. For dashboards that run the same expensive aggregation (e.g., daily GMV by region by category) on every page load, a materialized view that pre-computes the result eliminates the repeated scan cost. In Snowflake, materialized views can be set to auto-refresh; in Redshift, they can be configured to auto-refresh on base table changes. The right use case: high-frequency reads, low write frequency, stable query shape.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Redshift DISTKEY | Co-locate joined tables on same node |
| Redshift DISTSTYLE ALL | Full copy on every node — small dims |
| Redshift SORTKEY | Physical order — faster range scans |
| Redshift VACUUM | Reclaim deleted space, re-sort |
| Snowflake separation | Storage and compute are independent |
| Snowflake warehouse | Isolated compute cluster, pay per second |
| Snowflake clustering | Micro-partition pruning for large tables |
| Zero-copy clone | Instant copy, no storage cost until change |
| Time travel | Query/restore historical data |
| Snowpipe | Auto-ingest from S3 on file arrival |
| Redshift Spectrum | Query S3 data from Redshift without loading |
