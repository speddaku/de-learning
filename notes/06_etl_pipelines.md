# ETL/ELT Pipelines — Complete Notes from Scratch

---

## 1. ETL vs ELT

The ETL vs. ELT debate sounds academic but it's actually a practical question driven by infrastructure economics. The shift from ETL to ELT happened because the cost of compute inside cloud data warehouses (Snowflake, BigQuery, Redshift) dropped dramatically — running SQL transformations on a scaled-out warehouse became cheaper than maintaining a separate Spark/Python transformation layer. The trade-off flipped.

### ETL — Extract, Transform, Load
```
Source → Extract → Transform (outside DB) → Load → Data Warehouse

Transform happens in a processing layer (Spark, Glue, custom Python)
before data enters the warehouse.

When to use ETL:
- Complex transformations that the warehouse can't handle efficiently
- Source data is messy/unstructured
- Privacy — need to mask/remove PII before loading
- Legacy data warehouses with limited compute
```

### ELT — Extract, Load, Transform

ELT won because it acknowledges a fundamental truth: **you don't always know upfront what transformations you'll need**. Loading raw data first preserves optionality — if your business logic changes or you discover a bug in a transformation, you can re-run it against the raw data. With pure ETL, if the raw data was discarded after loading, a bug in the transform means the data is gone.

```
Source → Extract → Load (raw) → Transform (inside DW) → Data Mart

Data loaded raw into warehouse first, then transformed using SQL/dbt.
Modern warehouses (Snowflake, BigQuery, Redshift) are powerful enough.

When to use ELT:
- Modern cloud data warehouse (Snowflake, BigQuery, Redshift)
- Want raw data preserved for re-processing
- SQL-based transformations (dbt)
- Faster time to data (load first, transform on demand)
```

### Comparison

The ELT downside that's hardest to mitigate in practice is PII in the warehouse. Regulations like GDPR and CCPA require that raw personal data be accessible only to authorized roles and deletable on request. Dumping raw API responses (which often contain PII) directly into Snowflake requires robust column-level access controls and masked views — it's solvable but demands explicit governance from day one.

```
ETL:
+ Data quality enforced before loading
+ Smaller warehouse storage (transformed data only)
- Lose raw data (can't re-transform from scratch)
- More complex pipeline logic

ELT:
+ Raw data preserved (can re-run transformations)
+ Simpler ingestion (just load as-is)
+ Use warehouse compute power
- Storage cost for raw data
- PII in warehouse (compliance risk)
```

> **💡 Interview tip:** "ETL or ELT — which do you prefer and why?" — Don't just say "ELT because it's modern." Frame it around the trade-offs: ELT is the right default for cloud data warehouses because raw data preservation is valuable and warehouse compute is cheap. ETL is still the right call when you need to strip PII before data enters the warehouse, or when the source data is so unstructured that it needs Spark/Python-level preprocessing that SQL can't handle. Show you can reason about both sides.

> **🌍 Real world:** Most mature data platforms end up with a hybrid: use a lightweight Glue/Lambda job to extract and land raw data into S3 (an "EL" step), then use dbt inside Redshift/Snowflake for all SQL-based "T" transformations. This gives you raw data preservation in cheap S3 storage while leveraging warehouse SQL for business logic — the best of both worlds.

---

## 2. Batch vs Stream Processing

The batch vs. stream decision is driven by latency requirements and operational complexity tolerance. Batch is simpler — bounded data, clear start/end, retry is straightforward. Streaming is fundamentally harder because data is infinite, ordering isn't guaranteed, late arrivals are normal, and "exactly once" is hard to achieve. Don't choose streaming unless your use case actually needs sub-minute latency.

### Batch Processing
```
- Processes data in fixed intervals (hourly, daily)
- High throughput, efficient for large volumes
- Higher latency (data not immediately available)
- Tools: Spark, Glue, Hadoop

Use cases:
- Daily sales reports
- Monthly billing
- Historical backfills
- Heavy transformations
```

### Stream Processing

Streaming systems introduce problems that don't exist in batch: out-of-order events (event generated at 11:59pm might arrive in the next minute's window), exactly-once semantics (one message processed exactly once across producer + broker + consumer failures), and watermarking (deciding when to close a time window even if late data might still arrive). These are hard problems — stream processing engineers earn their salaries.

```
- Processes data as it arrives (milliseconds to seconds)
- Low latency, real-time
- More complex (ordering, exactly-once, state management)
- Tools: Kafka Streams, Spark Structured Streaming, Flink, Kinesis

Use cases:
- Real-time dashboards
- Fraud detection
- Clickstream analysis
- IoT sensor data
```

### Micro-batch

Micro-batching (Spark Structured Streaming's default model) is the pragmatic middle ground: you get most of the benefit of streaming with a simpler programming model. Instead of processing one event at a time, you process small batches every few seconds. Latency is seconds-to-minutes rather than milliseconds, but the model behaves much more like familiar batch code.

```
- Small batches processed every few seconds/minutes
- Compromise between batch and streaming
- Easier than true streaming
- Spark Structured Streaming supports this
```

---

## 3. Full Load vs Incremental Load

The choice between full and incremental loading is primarily about scale and source system constraints. Full loads are straightforward and always correct — they're just expensive at scale. Incremental loads are efficient but introduce complexity: you need a reliable way to identify what's changed, and different methods have different blind spots.

### Full Load
```
- Truncate and reload entire dataset
- Simple to implement
- Expensive for large datasets

When to use:
- Small dimension tables
- Initial historical backfill
- When source doesn't track changes
- Monthly complete refresh

TRUNCATE TABLE customers;
COPY customers FROM 's3://...';
```

### Incremental Load — Append Only

Append-only loads work for immutable event data — each row is written once and never changes. This is the simplest incremental pattern and the easiest to make idempotent. Use the watermark approach with care: if your source system processes events in batches, `created_at` might not be monotonically increasing in order of processing, and you can miss records near the boundary.

```
- Load only new records (insert, never update)
- Use for immutable events (logs, transactions)
- Track by: created_at timestamp, auto-increment ID, file date

SELECT * FROM source_events
WHERE created_at > (SELECT MAX(created_at) FROM target_events);
```

### Incremental Load — Upsert (Merge)

The delete-insert pattern on Redshift and the MERGE statement on Snowflake both achieve the same result — idempotently apply new and changed records — but through different mechanisms. Redshift doesn't support MERGE natively (as of this writing), so the staging-table approach is the standard workaround. On Snowflake and BigQuery, native MERGE is cleaner and atomic.

```sql
-- Load new and updated records
-- Use for mutable entities (customers, orders with status changes)

-- Redshift:
BEGIN;
CREATE TEMP TABLE staging_customers (LIKE customers);
COPY staging_customers FROM 's3://...' USING ROLE '...';

DELETE FROM customers
WHERE customer_id IN (SELECT customer_id FROM staging_customers);

INSERT INTO customers SELECT * FROM staging_customers;
COMMIT;

-- Snowflake MERGE:
MERGE INTO customers AS target
USING staging_customers AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN UPDATE SET
    target.email = src.email,
    target.updated_at = src.updated_at
WHEN NOT MATCHED THEN INSERT (customer_id, email, updated_at)
    VALUES (src.customer_id, src.email, src.updated_at);
```

### Change Data Capture (CDC)

CDC is the most sophisticated and complete approach to incremental loading — it captures every change at the database transaction log level, including DELETEs that timestamp-based approaches completely miss. This is a critical point: if a customer is deleted in your source CRM and you're doing timestamp-based incremental loads, that deletion is **invisible** to your pipeline. The customer lives forever in your data warehouse. CDC captures the DELETE event and you can apply it downstream.

Log-based CDC (Debezium reading PostgreSQL WAL, or AWS DMS reading MySQL binlog) is the gold standard: it's near real-time, has minimal impact on the source database, and captures everything.

```
Captures row-level changes from source DB transaction log.

Methods:
1. Timestamp-based: WHERE updated_at > last_run_time (simple but misses deletes)
2. Log-based CDC: reads database WAL/binlog (Debezium, AWS DMS)
3. Trigger-based: DB triggers write changes to audit table

Log-based CDC:
- Captures INSERT, UPDATE, DELETE
- Near-real-time
- No load on source DB
- Debezium → Kafka → target
```

> **💡 Interview tip:** "What are the limitations of timestamp-based incremental loading?" — This is a classic interview question. The answer: (1) It silently misses DELETE operations — deleted rows never have an updated_at change. (2) If `updated_at` isn't indexed, the query is a full scan. (3) If the source system clock drifts or if there are batch updates with identical timestamps at the window boundary, you can miss records. CDC (log-based) solves all three problems but adds operational complexity (need Debezium or DMS running). The trade-off depends on whether your use case requires DELETE visibility.

> **🌍 Real world:** A real production issue: a customer requests GDPR deletion from your CRM. Your CRM deletes the row. Your timestamp-based pipeline never picks up the deletion. Two years later, you're still holding PII that was supposed to be deleted. This is why CDC matters beyond just "getting deletes" — it's a compliance requirement in many data teams.

---

## 4. Idempotency

Idempotency is the most important property of production data pipelines. Pipelines fail — network timeouts, service throttling, out-of-memory errors, code bugs. When they fail, you need to re-run them. An idempotent pipeline can be re-run any number of times and always produces the same correct result. A non-idempotent pipeline produces duplicate data on re-run, which can silently corrupt your metrics and reports.

### Why It Matters

The analogy is a light switch vs. a "press to add 1" button. A light switch is idempotent — pressing it twice brings you back to the original state. A "press to add 1" button is not — pressing it twice gives you a different result. Your pipelines should be light switches.

```
Pipelines fail and get re-run. Idempotent pipelines produce the same
result whether run once or multiple times.

Non-idempotent (dangerous):
INSERT INTO sales SELECT * FROM raw_sales WHERE date = '2025-05-21';
→ Running twice = duplicate rows

Idempotent (safe):
DELETE FROM sales WHERE date = '2025-05-21';
INSERT INTO sales SELECT * FROM raw_sales WHERE date = '2025-05-21';
→ Always exactly one copy
```

### Making Pipelines Idempotent

The partition-delete-and-reinsert approach is the standard in Spark/S3 pipelines: write with `mode("overwrite")` on a specific partition column, and the partition is atomically replaced each run. The MERGE/UPSERT approach is the standard in SQL-based pipelines. Choose based on your storage layer.

```
1. Partition-based: overwrite specific partition (date partition)
   - Delete partition → reload
   
2. MERGE/UPSERT: match on natural key, update or insert

3. Unique constraints: DB enforces no duplicates
   INSERT ... ON CONFLICT (id) DO UPDATE SET ...

4. Deduplication step: deduplicate before writing
   df = df.dropDuplicates(["event_id"])

5. File naming: include run_id in output path
   s3://bucket/output/run_id=abc123/
   → Separate each run, manually promote correct one
```

> **💡 Interview tip:** "How do you make a Spark pipeline idempotent?" — The canonical answer is partition overwrite: write to S3 with `.mode("overwrite").partitionBy("date")` and use `spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")`. Dynamic partition overwrite only replaces the partitions present in the current DataFrame, leaving other partitions untouched. Without the dynamic setting, `overwrite` replaces the entire table. Know the difference.

> **🌍 Real world:** Idempotency failures are insidious because they only manifest when pipelines re-run — which is exactly when you're already stressed about the failure. The best time to think about idempotency is when writing the pipeline, not when debugging a duplicate-data incident at 2am.

---

## 5. Delivery Semantics

Delivery semantics describe the guarantee a messaging system makes about how many times a message will be processed. They're arranged in a tradeoff between simplicity and correctness. At-least-once is the default for most production systems because it's achievable without distributed transactions, and you can handle the resulting duplicates at the consumer side with deduplication.

```
At-most-once:
- Message processed 0 or 1 times
- Possible data loss (fire and forget)
- Use for: non-critical logging, metrics

At-least-once:
- Message processed 1 or more times (possible duplicates)
- No data loss, but need dedup on consumer side
- Use for: most streaming pipelines

Exactly-once:
- Message processed exactly once
- Hardest to implement
- Requires idempotent producers + transactional consumers
- Kafka + idempotent producers + transactions
- Use for: financial transactions, billing
```

> **💡 Interview tip:** "What is exactly-once semantics and when do you need it?" — Exactly-once requires all three layers to cooperate: idempotent producer (Kafka's `enable.idempotence=true`), transactional broker, and transactional consumer. It has real throughput overhead. The practical advice: design your consumer to be idempotent (deduplicate by message ID), and you can safely use at-least-once delivery everywhere. You only need native exactly-once when deduplication at the consumer is impractical (e.g., the downstream is a third-party payment API).

---

## 6. File Formats

File format choice directly impacts pipeline performance and cost. The format determines how data is physically laid out on disk — row-by-row vs. column-by-column — which determines which queries are fast and which are slow. For analytics (read specific columns across many rows), columnar formats win decisively. For streaming (write and read individual records), row-based formats win.

### CSV
```
Pros:
- Human-readable, universally supported
- Easy to inspect with any text editor

Cons:
- No schema enforcement
- Large file size (no compression built-in)
- Slow to parse (row-by-row)
- Type ambiguity (is "123" a string or int?)

Use when: simple data exchange, small files, external systems that require CSV
```

### JSON
```
Pros:
- Flexible schema (nested structures, arrays)
- Self-describing
- Universal language support

Cons:
- Large file size
- Slow to parse
- No columnar access

Use when: nested/semi-structured data, API responses, log files
```

### Parquet

Parquet is the de facto standard for analytics workloads on S3. The columnar layout means a `SELECT user_id, amount FROM events` query only reads those two column chunks — the remaining 95% of the file is never touched. This column pruning, combined with Snappy compression, typically delivers 5-10x smaller files and 10-100x faster analytical queries compared to equivalent CSV data.

Understanding Parquet's internal structure is important for advanced optimization. Row groups are the horizontal unit of data (default 128MB) — this is also the unit at which statistics (min/max per column) are tracked for predicate pushdown. When you filter `WHERE amount > 1000` and Parquet knows a row group has max(amount)=500, it skips that entire row group without reading any data from it.

```
Pros:
- Columnar storage → fast analytical queries
- Built-in compression (Snappy, ZSTD, Gzip, LZ4)
- Schema embedded in file
- Column pruning (only reads needed columns)
- Row group filtering (min/max stats for skipping)
- Excellent for Spark, Athena, Redshift Spectrum, BigQuery

Structure:
- Row groups (128MB default) — horizontal partitioning
- Column chunks — all values for a column within a row group
- Pages — smallest unit (typically 1MB)
- Footer — schema + metadata + column stats

Cons:
- Not human-readable
- Complex to write without Spark/Pandas
- Hard to append individual rows (batch-oriented)

Use when: analytics workloads, S3 data lake, Spark pipelines
```

> **💡 Interview tip:** "Why is 128MB the default Parquet row group size?" — It matches HDFS block size and S3 multipart upload thresholds. A row group that's too small loses the min/max filtering benefit (more metadata overhead). A row group that's too large means you can't skip large chunks of data on a selective filter. 128MB is the sweet spot between selectivity and metadata overhead for most analytical workloads. Increase it to 256MB for very selective filter patterns.

> **🌍 Real world:** One of the most common performance problems in production Spark/Athena jobs is small files. If your Spark job writes 10,000 files of 1MB each instead of 100 files of 100MB each, every subsequent query on that data has to open 10,000 files — and S3 list/open operations aren't free. Compact small files as part of your pipeline's output stage using `coalesce()` or `repartition()` before writing.

### ORC
```
Similar to Parquet (columnar, compressed)
Additional features:
- ACID support (used in Hive)
- Better for Hive/HBase workloads
- Built-in indexes (bloom filters, min/max)
- ZLIB compression default

Use when: Hive ecosystem, AWS Glue, need ACID on data lake
```

### Avro

Avro is the right format for streaming because it's row-oriented — individual records can be serialized and deserialized independently, which is how Kafka works (one message = one record). Its killer feature for long-running systems is schema evolution with backward/forward compatibility — you can add a new field with a default value and old consumers (without the new field in their schema) still work correctly.

```
Row-based, not columnar
Pros:
- Schema evolution (add/remove fields with default values)
- Compact binary serialization
- Self-describing (schema in file)
- Great for streaming (Kafka)
- Fast to serialize/deserialize individual records

Schema example:
{
  "type": "record",
  "name": "User",
  "fields": [
    {"name": "id", "type": "int"},
    {"name": "email", "type": "string"},
    {"name": "age", "type": ["null", "int"], "default": null}
  ]
}

Use when: Kafka messages, row-by-row writes, schema evolution needed
```

### Format Comparison
```
Format    | Storage | Query Speed | Schema | Streaming | ACID
----------|---------|-------------|--------|-----------|-----
CSV       | Large   | Slow        | No     | OK        | No
JSON      | Large   | Slow        | No     | OK        | No
Parquet   | Small   | Fast        | Yes    | Hard      | No
ORC       | Small   | Fast        | Yes    | Hard      | Yes
Avro      | Medium  | Medium      | Yes    | Excellent | No

Rule of thumb:
- Streaming: Avro
- Analytics/queries: Parquet
- Hive/Glue with ACID: ORC
```

---

## 7. Pipeline Design Patterns

### Landing → Raw → Curated → Consumption

The medallion architecture (Bronze/Silver/Gold) or Landing/Raw/Curated pattern is the dominant data lake design pattern. Each layer has a distinct contract: Landing is immutable raw data (your insurance policy), Raw is clean and governed (your source of truth), Curated is business-ready (your efficiency layer). The separation means a bug in Raw-to-Curated transformations doesn't require re-extracting from source systems — you re-run from Landing.

```
Landing (Bronze):
- Exact copy of source data, no transformation
- Append-only, immutable
- Keep forever (audit trail, re-processing)
- s3://bucket/landing/source_name/YYYY/MM/DD/

Raw (Silver):
- Cleaned, deduplicated, standardized
- Schema enforced, types corrected
- Data quality checks applied
- s3://bucket/raw/entity_name/

Curated (Gold):
- Business-ready aggregations
- Star schema, wide tables
- Optimized for reporting tools
- s3://bucket/curated/domain/

Consumption:
- Specific report/dashboard tables
- Often materialized views
- Snowflake, Redshift tables
```

> **🌍 Real world:** The "keep Landing forever" rule gets challenged by storage cost reviews. The right answer is that Landing data is your audit trail and re-processing capability — its value is proportional to the cost of re-extracting from source systems. For sources that don't support historical re-extraction (real-time APIs, transactional DBs without full history), Landing data is irreplaceable and worth the storage cost. For sources with full history (cold storage backups, immutable event streams), Landing can have a shorter retention.

### Handling Late-Arriving Data

Late-arriving data is not an edge case — it's a normal operational reality. Mobile apps buffer events offline and send them in batches hours later. Distributed systems have clock skew. Upstream pipelines have their own delays. Any production pipeline that doesn't explicitly handle late data will silently produce incorrect historical aggregations.

The watermark approach in Spark Structured Streaming is elegant: declare how late data can arrive (e.g., "up to 2 hours late") and Spark holds windows open for that duration before closing them. For batch pipelines, the standard approach is to keep date partitions "open" for 24-48 hours and use a MERGE/upsert pattern so late-arriving records land in the correct partition.

```
Problem: event generated at 11:58pm processed at 12:05am (next day's batch)

Solutions:
1. Processing time windows: ignore — accept data in next batch
2. Event time windows: reprocess the window when late data arrives
3. Watermarks (streaming): wait N minutes for late data before closing window
4. Partial updates: keep fact table partition open for 24 hours

Spark Structured Streaming watermark:
df.withWatermark("event_time", "2 hours")
  .groupBy(window("event_time", "1 hour"))
  .count()
```

> **💡 Interview tip:** "How do you handle late-arriving data in your pipelines?" — In batch: use a MERGE-based approach so re-running a partition naturally handles late arrivals without creating duplicates. In streaming: use watermarks. The follow-up is usually "what's your SLA for late data?" — because the watermark delay is a direct trade-off between latency (lower = fresher data) and completeness (higher = more late data captured). There's no universally correct answer; it depends on the business requirement.

### Schema Evolution

Schema evolution is one of the highest-risk events in a data pipeline's lifecycle. Adding a column is usually safe but can still break downstream consumers that use `SELECT *`. Removing or renaming a column is always a breaking change somewhere downstream.

```
Adding columns: usually safe (add NULL for old records)
Removing columns: dangerous — breaks downstream consumers
Renaming: breaking change — alias old name

Strategies:
1. Schema registry (Kafka + Avro): enforce compatibility
2. Parquet schema merge: Spark can merge compatible schemas
   spark.read.option("mergeSchema", "true").parquet("path")
3. Additive-only: only ever add columns, never remove
4. Versioned schemas: v1, v2, v3 paths
```

### Checkpointing and Restartability

A pipeline that can't be restarted safely from mid-point is an operational liability. When a Glue job fails after processing 8 hours of data in a 24-hour backfill, you want it to resume from hour 8 — not restart from the beginning. Checkpointing patterns externalize this "progress state" to a durable location (S3, DynamoDB) so the pipeline can query it on startup and skip already-processed work.

```
Problem: pipeline fails halfway through — need to resume without re-processing

Solutions:
1. Job bookmarks (Glue): tracks processed S3 objects/JDBC offsets
2. Watermark files: write "last_processed_date.txt" to S3
3. Checkpoint table in DB: track processed batches
4. Partition-based: process one partition at a time, mark done

Example watermark:
# Read last watermark
last_run = s3.get_object(Bucket='b', Key='watermarks/sales.txt')['Body'].read()

# Process only new data
df = spark.read.parquet('s3://...').filter(col('date') > last_run)

# Update watermark after success
s3.put_object(Bucket='b', Key='watermarks/sales.txt', Body=today_str)
```

> **🌍 Real world:** The watermark update must happen **after** the pipeline successfully completes — never before. If you update the watermark first and then the pipeline fails, you've permanently lost that window of data with no way to recover it. The sequence is always: process → verify → update watermark.

---

## 8. Data Quality Validation

Data quality validation is not optional in production — it's the safety net that prevents bad data from propagating downstream into dashboards, ML models, and business decisions. The best time to catch a data quality issue is at pipeline ingestion, not when a business analyst notices the numbers look wrong three weeks later.

### Checks to Implement

Think of data quality checks as a contract between your pipeline and its consumers. Each check encodes an assumption about the data — and when that assumption breaks, you want an immediate, explicit failure rather than silent corruption.

```
Completeness:  row count > 0, no nulls in required columns
Accuracy:      values in expected range (age 0-120, price > 0)
Consistency:   FK integrity, totals match between tables
Timeliness:    data freshness (max(event_date) within 24 hours)
Uniqueness:    no duplicate primary keys
Validity:      email format, phone format, enum values

-- SQL examples:
-- Row count check
SELECT COUNT(*) FROM daily_sales WHERE date = '2025-05-21';  -- must be > 0

-- Null check
SELECT COUNT(*) FROM orders WHERE customer_id IS NULL;  -- must be 0

-- Range check
SELECT COUNT(*) FROM products WHERE price < 0;  -- must be 0

-- Freshness check
SELECT MAX(event_ts) FROM events;  -- must be within last 2 hours

-- Referential integrity
SELECT COUNT(*) FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id
WHERE c.id IS NULL;  -- must be 0
```

> **💡 Interview tip:** "How do you implement data quality in your pipelines?" — At minimum: row count thresholds (zero rows is almost always a bug), null checks on key columns, and freshness checks. More mature teams add anomaly detection: "today's row count is more than 3 standard deviations from the 30-day average" — this catches upstream issues that produce valid-looking data at the wrong volume. Tools like Great Expectations, dbt tests, and AWS Glue Data Quality automate this at scale.

### Dead Letter Queues

Dead letter queues prevent a single bad record from blocking an entire pipeline. Instead of the pipeline crashing on record 47,832 (out of 100,000), failed records are routed to a DLQ, the pipeline continues processing the remaining 52,168, and the DLQ contents are handled separately — either fixed and replayed or escalated for manual review.

```
Failed records go to DLQ instead of blocking the pipeline.
Process DLQ separately: alert, manual fix, replay.

Lambda + SQS:
- Failed Lambda invocations → DLQ after MaxReceiveCount retries
- Monitor DLQ depth with CloudWatch alarm
- Process DLQ records: fix data, re-queue to main queue
```

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| ETL | Transform before loading — complex transforms, privacy |
| ELT | Load raw first, transform in DW — modern approach |
| Full load | Truncate + reload — simple, expensive at scale |
| Incremental | Load new/changed only — needs change tracking |
| CDC | Capture changes from DB log — Debezium → Kafka |
| Idempotent | Safe to re-run — partition delete+insert or MERGE |
| At-least-once | Possible duplicates — need dedup |
| Exactly-once | Hardest, Kafka transactions |
| Parquet | Columnar, compressed — standard for analytics |
| Avro | Row-based, schema evolution — Kafka standard |
| Late data | Watermarks in streaming, reprocess partition in batch |
| Checkpointing | Track progress — resume without re-processing |
