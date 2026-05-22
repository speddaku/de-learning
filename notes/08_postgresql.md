# PostgreSQL — Complete Notes from Scratch

---

## 1. Data Types

Choosing the right data type is not just about correctness — it directly affects index performance, storage size, and query speed. An incorrectly typed column (storing money as `FLOAT` instead of `NUMERIC`, or storing timestamps without timezone) creates subtle bugs that surface in production at the worst possible time.

### Numeric

Use the narrowest type that fits your range. `BIGINT` costs 8 bytes vs. `INTEGER`'s 4 bytes — on a billion-row table, that's a 4GB difference in storage and a proportional difference in index size. Use `DECIMAL/NUMERIC` for any money or financial calculation — floating-point types (`REAL`, `DOUBLE PRECISION`) cannot represent many decimal values exactly, which causes rounding errors in financial aggregations.

```sql
SMALLINT        -- 2 bytes, -32768 to 32767
INTEGER (INT)   -- 4 bytes, ~-2B to 2B
BIGINT          -- 8 bytes, ~-9.2 quintillion to 9.2 quintillion
SERIAL          -- auto-increment INTEGER (1, 2, 3...)
BIGSERIAL       -- auto-increment BIGINT
DECIMAL(p,s)    -- exact numeric, p=precision, s=scale (financial data)
NUMERIC(p,s)    -- same as DECIMAL
REAL            -- 4-byte float (approximate)
DOUBLE PRECISION-- 8-byte float (approximate)
```

### Text

In PostgreSQL, `TEXT` and `VARCHAR(n)` have virtually identical performance characteristics — there is no storage or performance benefit to `VARCHAR` over `TEXT` for most use cases. The only reason to use `VARCHAR(n)` is to enforce a maximum length as a data integrity constraint. Using `CHAR(n)` is almost always wrong — it pads shorter strings with spaces, which causes surprising equality comparison behavior.

```sql
CHAR(n)         -- fixed-length, padded with spaces
VARCHAR(n)      -- variable-length, max n chars
TEXT            -- unlimited length (most common choice)
```

### Date/Time

`TIMESTAMPTZ` is almost always the right choice for event timestamps. It stores values as UTC internally and automatically adjusts for the session's timezone on display. `TIMESTAMP` (without timezone) creates a time-zone ambiguity — the same stored value means different things depending on where the application server is running. This is a real source of bugs in distributed systems that span timezones.

```sql
DATE            -- date only (YYYY-MM-DD)
TIME            -- time only (HH:MI:SS)
TIMESTAMP       -- date + time, no timezone
TIMESTAMPTZ     -- date + time + timezone (always stores UTC)
INTERVAL        -- duration (INTERVAL '1 year 2 months')

-- Best practice: always use TIMESTAMPTZ for event times
-- Store everything in UTC, convert at display time
```

> **💡 Interview tip:** "What's the difference between `TIMESTAMP` and `TIMESTAMPTZ` in PostgreSQL?" — `TIMESTAMP` stores a datetime without any timezone context — it's ambiguous. `TIMESTAMPTZ` converts to UTC on insert and converts back to the session's timezone on retrieval. In a globally distributed system, you need `TIMESTAMPTZ` so that "2025-05-21 02:00:00" inserted by a server in Tokyo and retrieved by a server in New York gives you the correct UTC reference point. Always use `TIMESTAMPTZ` for event times.

### Other

`JSONB` vs. `JSON` is a concrete choice that matters. `JSON` stores the raw JSON text — preserving whitespace and key order, but requiring a full parse on every access. `JSONB` stores a binary representation — slightly larger on write, but dramatically faster on read, and most importantly: **indexable**. You cannot create a GIN index on `JSON`. You can on `JSONB`. Always use `JSONB`.

```sql
BOOLEAN         -- TRUE, FALSE, NULL
UUID            -- UUID type (uuid_generate_v4())
JSON            -- text, validates JSON syntax
JSONB           -- binary JSON — indexable, faster queries (prefer JSONB)
ARRAY           -- array of any type (INTEGER[], TEXT[])
BYTEA           -- raw bytes (binary data)
```

---

## 2. Constraints

Constraints are executable documentation — they encode business rules directly in the database schema. A `CHECK (amount > 0)` constraint is more reliable than an application-level validation because it enforces the rule even when data is inserted through a migration script, a different application, or a direct `psql` connection. Treat constraints as the last line of data integrity defense.

```sql
CREATE TABLE orders (
    order_id    SERIAL PRIMARY KEY,           -- unique, not null, auto-increment
    customer_id INTEGER NOT NULL,              -- cannot be null
    email       TEXT UNIQUE,                   -- no duplicates
    amount      DECIMAL(10,2) CHECK (amount > 0),  -- must be positive
    status      TEXT DEFAULT 'pending',        -- default value
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- ON DELETE CASCADE: delete orders when customer deleted
-- ON DELETE SET NULL: set customer_id to NULL when customer deleted
-- ON DELETE RESTRICT: prevent customer deletion if orders exist (default)
```

---

## 3. Indexes

An index is a bet: you're trading write overhead and storage space for read speed. The decision about whether to add an index depends on the selectivity of the filter and the balance of reads vs. writes. PostgreSQL's query planner makes a cost-based decision on whether to use an index — it estimates whether reading the index + fetching heap rows is cheaper than a sequential scan. For low-selectivity filters (returning more than 10-20% of rows), a sequential scan is often **faster** than an index scan because the heap access pattern becomes random I/O rather than sequential I/O.

### B-tree Index (default)

B-tree is the workhorse. It supports equality (`=`), range (`>`, `<`, `BETWEEN`), sorting, and composite key access. The **leading column rule** for composite indexes is critical: a composite index on `(customer_id, created_at)` can satisfy queries on `customer_id` alone, but cannot efficiently satisfy queries on `created_at` alone. The leading column must be present in the WHERE clause for the index to be used.

```sql
-- Most common — for equality and range queries
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date ON orders(created_at);

-- Composite index
CREATE INDEX idx_orders_cust_date ON orders(customer_id, created_at);
-- Useful for: WHERE customer_id = X AND created_at > Y
-- Also useful for: WHERE customer_id = X (leading column)
-- NOT useful for: WHERE created_at > Y (non-leading column alone)

-- Partial index (only index rows matching condition)
CREATE INDEX idx_active_orders ON orders(customer_id)
WHERE status = 'active';
-- Smaller, faster for queries that filter on status = 'active'

-- Expression index
CREATE INDEX idx_email_lower ON users(LOWER(email));
-- Allows: WHERE LOWER(email) = 'alice@example.com' to use index
```

Partial indexes are an underutilized optimization. If 95% of your queries filter on `status = 'active'` and only 5% of rows are active, a partial index covers only those 5% of rows — making it ~20x smaller and faster than a full index on `customer_id`. The planner will automatically use it when the query's WHERE clause is compatible with the partial index condition.

> **💡 Interview tip:** "When would you use a partial index?" — Use a partial index when queries consistently filter on a specific column value AND that value covers a small fraction of the total rows. Classic example: `WHERE deleted_at IS NULL` on a soft-delete table where 99% of rows are deleted — index only the non-deleted rows for massive size reduction. Another example: `WHERE status = 'pending'` on an orders table where only 1% of orders are pending at any time.

### Hash Index
```sql
-- Only for equality (=), not range queries
CREATE INDEX idx_order_hash ON orders USING HASH (order_uuid);
-- Faster than B-tree for pure equality on high-cardinality columns
```

### GIN Index (Generalized Inverted Index)

GIN is the index type for containment queries — "does this JSONB document contain this key/value?" or "does this array contain this element?" GIN is an inverted index: it maps from values to row locations (the reverse of a B-tree which maps from row locations to values). This makes it ideal for full-text search and JSONB containment queries (`@>`).

```sql
-- For full-text search, arrays, JSONB
CREATE INDEX idx_tags_gin ON products USING GIN (tags);  -- tags is ARRAY
CREATE INDEX idx_meta_gin ON events USING GIN (metadata jsonb_ops);  -- JSONB

-- Allows fast: WHERE tags @> ARRAY['electronics'] (contains)
-- Allows fast: WHERE metadata @> '{"type": "click"}'
```

### GiST Index
```sql
-- For geometric data, full-text search (alternative to GIN)
-- Also for range types
CREATE INDEX idx_location ON stores USING GIST (location);
```

### Index Tips
```
- Too many indexes → slow INSERT/UPDATE/DELETE (must update all indexes)
- Index columns used in WHERE, JOIN ON, ORDER BY
- Index high-cardinality columns (not boolean columns)
- Use EXPLAIN ANALYZE to verify index is being used
- Partial indexes: smaller, faster for filtered queries
```

> **🌍 Real world:** Index bloat is a real production problem. Each UPDATE that changes an indexed column creates a new index entry (the old one is marked dead, just like table rows under MVCC). On a high-write table, indexes can grow significantly between autovacuum runs. Monitor index size with `pg_indexes_size()` and check bloat with `pgstattuple`. Rebuilding with `REINDEX CONCURRENTLY` (PostgreSQL 12+) reclaims bloated index space without blocking reads.

---

## 4. EXPLAIN and EXPLAIN ANALYZE

`EXPLAIN` is PostgreSQL's query debugger. Without understanding how to read it, you're optimizing blind. The critical distinction: `EXPLAIN` (without `ANALYZE`) shows the **estimated** plan without executing the query. `EXPLAIN ANALYZE` actually **executes** the query and shows both estimated and actual numbers — you can see exactly where the planner's estimates diverged from reality.

The `cost` numbers in `EXPLAIN` output are in **arbitrary planner units, not milliseconds**. A cost of `1000` doesn't mean 1 second — it means the planner estimates this node is 1000 cost units of work. The units are arbitrary and consistent only within a single plan comparison. When you see `cost=0.00..8.27 rows=1`, the `0.00` is the startup cost (time before first row) and `8.27` is the total estimated cost.

```sql
-- EXPLAIN: shows plan without executing
EXPLAIN SELECT * FROM orders WHERE customer_id = 123;

-- EXPLAIN ANALYZE: executes AND shows actual timing
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 123;

-- Verbose output (most useful)
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT o.*, c.email
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.created_at > '2025-01-01';
```

### Reading the Plan

The plan is a tree — read it from inside out (most indented = first executed). When you see `Seq Scan` on a large table with a selective filter, that's the most common signal that a missing or unused index is the problem. When you see `rows=100000` estimated vs. `actual rows=3`, the planner has wildly stale statistics — run `ANALYZE tablename` to update them.

```
Seq Scan  — full table scan (no index used)
Index Scan — uses index to find rows, then fetches from heap
Index Only Scan — all needed data in index (no heap fetch)
Bitmap Heap Scan — efficient for range queries returning many rows
Hash Join — hash one table, probe with other (for large joins)
Merge Join — sort both sides, merge (for sorted data or indexed columns)
Nested Loop — for each row in outer, scan inner (good for small tables)

Key numbers:
cost=0.00..125.50  — startup cost .. total cost (in arbitrary units)
rows=100           — estimated rows
actual time=0.015..1.234  — actual ms
actual rows=95     — actual rows returned
```

> **💡 Interview tip:** "You have a slow query. Walk me through your debugging process." — Step 1: `EXPLAIN (ANALYZE, BUFFERS)` on the query. Step 2: Look for Seq Scans on large tables with selective filters — likely missing index. Step 3: Compare estimated rows vs. actual rows — large discrepancy means stale statistics, run `ANALYZE`. Step 4: Look at join strategies — a Nested Loop joining two large tables signals the planner made a wrong estimate; a Hash Join is usually better. Step 5: Check BUFFERS output for cache hit ratio — if most reads are disk (not buffer cache), caching or index improvements help most.

> **🌍 Real world:** `BUFFERS` output is underused. It shows how many 8KB blocks were read from cache (`shared hit`) vs. from disk (`shared read`). A query with `shared hit=50000 shared read=5` is running almost entirely from cache (fast). A query with `shared hit=100 shared read=50000` is reading primarily from disk (slow, and a candidate for better indexing or query rewriting to reduce scanned data).

---

## 5. VACUUM and Autovacuum

### Why VACUUM is Needed

MVCC (Multi-Version Concurrency Control) is PostgreSQL's solution to the reader-writer concurrency problem: readers never block writers and writers never block readers, because they work on different versions of each row. The mechanism: when you `UPDATE` a row, PostgreSQL doesn't modify the row in place. It marks the old row as "dead" (not visible to transactions started after the update) and writes a new row version. When you `DELETE`, the row is marked dead but not physically removed.

Think of it like a whiteboard where you never erase — instead of erasing and rewriting, you write a new version next to the old one and put a sticker on the old one saying "ignore this after 3pm." Over time, the whiteboard fills up with dead, stickered notes. VACUUM is the janitor who comes through and clears the stickered notes so the space can be reused.

Dead rows accumulate between VACUUM runs, causing **table bloat** — the table's physical size on disk grows larger than the live data justifies. This bloat means sequential scans read more 8KB pages than necessary, slowing down every query that does a full table scan or a large range scan.

```
PostgreSQL uses MVCC (Multi-Version Concurrency Control):
- UPDATE: new row version inserted, old marked as dead
- DELETE: row marked as dead, not physically removed
- Dead rows accumulate → table bloat → slower queries

VACUUM:
- Marks dead rows as reusable space (doesn't shrink file)
- Updates visibility map (used by Index Only Scans)
- Prevents transaction ID wraparound

VACUUM FULL:
- Rewrites entire table (compacts file)
- Exclusive lock (blocks all access)
- Use only when table is very bloated
- Run during maintenance window

ANALYZE:
- Updates statistics used by query planner
- Stale statistics → bad query plans

VACUUM ANALYZE:
- Does both
```

> **💡 Interview tip:** "What is MVCC in PostgreSQL and why does it require VACUUM?" — MVCC provides non-blocking concurrent access by keeping multiple versions of rows. Readers see a consistent snapshot based on their transaction start time; writers create new versions without modifying old ones. This means old, no-longer-visible row versions accumulate on disk. VACUUM reclaims that space by marking dead rows as reusable. Without regular VACUUM, tables bloat, sequential scans get slower, and — most critically — the transaction ID counter can wrap around (a 32-bit counter), causing data corruption. Autovacuum prevents this, but knowing how to tune it for high-write tables is a senior-level skill.

### Autovacuum

Autovacuum runs VACUUM automatically when a table's dead tuple count exceeds a threshold. The default `autovacuum_vacuum_scale_factor = 0.2` means vacuum fires when 20% of rows are dead. For a table with 10 million rows, that's 2 million dead rows before autovacuum acts — which is a lot of bloat on a high-write table. For large tables, tune these parameters per-table to be more aggressive.

```sql
-- PostgreSQL runs autovacuum automatically
-- Check autovacuum settings:
SHOW autovacuum_vacuum_scale_factor;   -- 0.2 = vacuum when 20% rows are dead
SHOW autovacuum_vacuum_threshold;      -- 50 = also need 50 dead rows minimum

-- Per-table settings for large tables:
ALTER TABLE large_events
SET (autovacuum_vacuum_scale_factor = 0.01,  -- vacuum at 1% dead rows
     autovacuum_vacuum_cost_delay = 2);       -- more aggressive

-- Check table bloat:
SELECT relname, n_dead_tup, n_live_tup, last_vacuum, last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

> **🌍 Real world:** High-frequency UPDATE workloads (like a status column on an orders table that updates millions of times per day) can overwhelm autovacuum. You'll see the table's `n_dead_tup` grow faster than autovacuum can clear it. Signs of insufficient autovacuum: query slowdown over time, table size growing without data growth, high sequential scan times. Fix by reducing `autovacuum_vacuum_scale_factor` to 0.01 for the table or increasing `autovacuum_max_workers`.

---

## 6. Table Partitioning

PostgreSQL declarative partitioning (added in version 10, significantly improved in 11+) allows you to split a large table into smaller physical sub-tables while presenting a unified logical table to queries. The planner can prune irrelevant partitions entirely — a query with `WHERE event_ts >= '2025-01-01' AND event_ts < '2025-02-01'` on a monthly-partitioned table only scans the January partition, skipping all others.

This is the PostgreSQL equivalent of S3 partition pruning — same principle, applied at the database level for OLTP/OLAP queries on time-series data.

```sql
-- Range partitioning (most common for time-series)
CREATE TABLE events (
    event_id    BIGINT,
    event_ts    TIMESTAMPTZ NOT NULL,
    user_id     INTEGER,
    event_type  TEXT
) PARTITION BY RANGE (event_ts);

-- Create partitions
CREATE TABLE events_2025_01 PARTITION OF events
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE events_2025_02 PARTITION OF events
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Default partition (catch-all)
CREATE TABLE events_default PARTITION OF events DEFAULT;

-- Indexes on parent apply to all partitions
CREATE INDEX ON events(user_id, event_ts);

-- Query automatically uses partition pruning:
SELECT * FROM events WHERE event_ts >= '2025-01-01' AND event_ts < '2025-02-01';
-- Only scans events_2025_01 partition
```

```sql
-- List partitioning
CREATE TABLE orders (
    order_id  BIGINT,
    region    TEXT NOT NULL,
    amount    DECIMAL
) PARTITION BY LIST (region);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US', 'CA');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('UK', 'DE', 'FR');

-- Hash partitioning (spread evenly)
CREATE TABLE logs (
    log_id    BIGINT,
    user_id   INTEGER
) PARTITION BY HASH (user_id);

CREATE TABLE logs_0 PARTITION OF logs FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE logs_1 PARTITION OF logs FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE logs_2 PARTITION OF logs FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE logs_3 PARTITION OF logs FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

> **💡 Interview tip:** "What are the benefits and trade-offs of table partitioning in PostgreSQL?" — Benefits: (1) partition pruning makes queries that filter on the partition key dramatically faster, (2) you can drop an entire month's data with `DROP TABLE events_2024_01` — instant, vs. a slow DELETE + VACUUM, (3) autovacuum runs per-partition, making maintenance more efficient on each smaller sub-table. Trade-offs: (1) cross-partition queries (no partition filter) are as slow as before, (2) foreign keys to/from partitioned tables have restrictions, (3) partition management (creating monthly partitions in advance) requires automation.

---

## 7. Stored Procedures and Functions

### Functions
```sql
-- SQL function (simple, inline)
CREATE OR REPLACE FUNCTION get_customer_orders(cust_id INTEGER)
RETURNS TABLE(order_id INT, amount DECIMAL) AS $$
    SELECT order_id, amount FROM orders WHERE customer_id = cust_id;
$$ LANGUAGE sql;

-- PL/pgSQL function (procedural logic)
CREATE OR REPLACE FUNCTION calculate_discount(price DECIMAL, tier TEXT)
RETURNS DECIMAL AS $$
DECLARE
    discount_pct DECIMAL;
BEGIN
    IF tier = 'gold' THEN
        discount_pct := 0.20;
    ELSIF tier = 'silver' THEN
        discount_pct := 0.10;
    ELSE
        discount_pct := 0.05;
    END IF;
    
    RETURN price * (1 - discount_pct);
END;
$$ LANGUAGE plpgsql;

-- Call function
SELECT calculate_discount(100.00, 'gold');  -- returns 80.00
```

### Stored Procedures (PostgreSQL 11+)

The key distinction between procedures and functions in PostgreSQL: procedures can manage their own transactions (`COMMIT`/`ROLLBACK`), functions cannot. Functions always run within the caller's transaction. Use procedures for long-running batch operations that need to commit work periodically (to avoid holding a transaction open for hours) or for ETL steps that need transactional control.

```sql
-- Procedures can commit/rollback transactions (functions cannot)
CREATE OR REPLACE PROCEDURE process_daily_sales(p_date DATE)
LANGUAGE plpgsql AS $$
DECLARE
    row_count INTEGER;
BEGIN
    -- Aggregate daily sales
    INSERT INTO daily_sales_summary (date, total_revenue, order_count)
    SELECT 
        p_date,
        SUM(amount),
        COUNT(*)
    FROM orders
    WHERE DATE(created_at) = p_date
    ON CONFLICT (date) DO UPDATE SET
        total_revenue = EXCLUDED.total_revenue,
        order_count = EXCLUDED.order_count;
    
    GET DIAGNOSTICS row_count = ROW_COUNT;
    RAISE NOTICE 'Processed % rows for %', row_count, p_date;
    
    COMMIT;
EXCEPTION WHEN OTHERS THEN
    ROLLBACK;
    RAISE;
END;
$$;

-- Call procedure
CALL process_daily_sales('2025-05-21');
```

---

## 8. Triggers

Triggers are powerful but add hidden complexity. Every trigger fires on every qualifying DML operation, adding latency to writes. They're invisible from application code — a developer debugging a slow INSERT might not realize it's firing a trigger that inserts into an audit table. Use triggers judiciously, document them well, and prefer application-level audit logging for new systems. That said, for ensuring audit trail completeness across all access paths (including direct SQL clients and migration scripts), triggers are unbeatable.

```sql
-- Audit trigger — track changes to sensitive table
CREATE TABLE customers_audit (
    audit_id    SERIAL PRIMARY KEY,
    operation   TEXT,
    old_email   TEXT,
    new_email   TEXT,
    changed_at  TIMESTAMPTZ DEFAULT NOW(),
    changed_by  TEXT DEFAULT CURRENT_USER
);

CREATE OR REPLACE FUNCTION audit_customer_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        INSERT INTO customers_audit (operation, old_email, new_email)
        VALUES ('UPDATE', OLD.email, NEW.email);
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO customers_audit (operation, old_email)
        VALUES ('DELETE', OLD.email);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER customer_audit_trigger
AFTER UPDATE OR DELETE ON customers
FOR EACH ROW EXECUTE FUNCTION audit_customer_changes();
```

---

## 9. CTEs — Including Recursive

CTEs (Common Table Expressions) are named subqueries that improve readability by breaking complex queries into named, composable steps. In PostgreSQL, CTEs with the keyword `MATERIALIZED` create a fence around the subquery — the planner materializes the result before the outer query runs. The default behavior (PostgreSQL 12+) is that non-recursive CTEs are inlined into the main query, allowing the planner to optimize across the CTE boundary.

Recursive CTEs are the standard tool for traversing hierarchies (org charts, product categories, geographic regions) and generating sequences in SQL without procedural loops.

```sql
-- Recursive CTE (hierarchies, graphs, paths)
-- Example: org chart — find all reports under a manager

WITH RECURSIVE org_tree AS (
    -- Base case: start with the root manager
    SELECT id, name, manager_id, 1 AS level
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    -- Recursive case: find all direct reports
    SELECT e.id, e.name, e.manager_id, ot.level + 1
    FROM employees e
    INNER JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree ORDER BY level;

-- Recursive CTE for consecutive date ranges
WITH RECURSIVE date_series AS (
    SELECT '2025-01-01'::DATE AS d
    UNION ALL
    SELECT d + INTERVAL '1 day' FROM date_series WHERE d < '2025-12-31'
)
SELECT d FROM date_series;
```

> **💡 Interview tip:** "How do you traverse a hierarchy in SQL?" — Recursive CTE. The pattern is always the same: base case (the root/starting nodes) `UNION ALL` recursive case (join back to the CTE itself to find the next level). Know how to add a `level` counter and a cycle detection guard (for graphs that might have cycles, add `WHERE NOT id = ANY(path_array)`).

---

## 10. JSON and JSONB

JSONB enables a powerful hybrid approach: relational structure where you have stable, queryable fields, and JSONB for the flexible, schema-free payload. This is common in event tracking systems where event metadata varies wildly by event type, or in product catalogs where different product categories have different attributes. The GIN index on JSONB makes containment queries fast — comparable to querying indexed relational columns.

```sql
-- JSONB: binary JSON — supports indexes, faster queries
-- JSON: text JSON — preserves whitespace/key order (rarely needed)

CREATE TABLE events (
    id       SERIAL PRIMARY KEY,
    metadata JSONB
);

INSERT INTO events (metadata) VALUES
('{"type": "click", "button": "buy", "user_id": 123, "tags": ["promo", "mobile"]}');

-- Access fields
SELECT metadata->>'type' FROM events;          -- text result
SELECT metadata->'user_id' FROM events;        -- JSON result
SELECT metadata#>>'{button}' FROM events;      -- nested path text

-- Filter
SELECT * FROM events WHERE metadata->>'type' = 'click';
SELECT * FROM events WHERE metadata @> '{"type": "click"}';  -- contains

-- Array element
SELECT metadata->'tags'->0 FROM events;        -- first tag
SELECT * FROM events WHERE metadata->'tags' ? 'promo';  -- tag exists

-- Update JSONB field
UPDATE events SET metadata = metadata || '{"status": "processed"}';
UPDATE events SET metadata = metadata - 'status';  -- remove key

-- Index on JSONB
CREATE INDEX idx_events_meta ON events USING GIN (metadata);
-- Enables fast: WHERE metadata @> '{"type": "click"}'

-- Index on specific field
CREATE INDEX idx_events_type ON events ((metadata->>'type'));
```

> **💡 Interview tip:** "When would you use JSONB in a relational database instead of proper normalized columns?" — JSONB is appropriate when the set of fields is dynamic and unpredictable (event properties that vary by event type), when schema flexibility is more valuable than query optimization (early-stage products with evolving data models), or when you're migrating from a document store and want a hybrid approach. It's the wrong choice for frequently queried, stable fields — those should be proper columns with proper indexes for full query planner optimization.

> **🌍 Real world:** A common pattern in analytics pipelines is storing raw event JSON in a JSONB column in a staging table, then using `jsonb_to_recordset()` or `json_populate_record()` to extract known fields into proper typed columns for the production table. This gives you flexibility at ingestion (don't need to know all fields upfront) with proper columnar performance at query time.

---

## 11. Full-Text Search

PostgreSQL's built-in full-text search is a viable alternative to Elasticsearch for moderate-scale search requirements. The key components: `tsvector` is the pre-processed, normalized token representation of a document (lowercase, stemmed, stopwords removed); `tsquery` is the search expression. The `@@` operator checks if a document matches a query.

```sql
-- tsvector — processed document
-- tsquery — search query

-- Basic search
SELECT * FROM articles
WHERE to_tsvector('english', content) @@ to_tsquery('english', 'data & engineering');

-- Ranking
SELECT title, ts_rank(to_tsvector('english', content), query) AS rank
FROM articles, to_tsquery('english', 'spark | kafka') query
WHERE to_tsvector('english', content) @@ query
ORDER BY rank DESC;

-- Index for performance
ALTER TABLE articles ADD COLUMN fts_content TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX idx_fts ON articles USING GIN (fts_content);
```

---

## 12. Extensions

PostgreSQL's extension ecosystem is one of its strongest competitive advantages. `pg_stat_statements` is the single most valuable extension for database administrators and data engineers — it tracks every query executed, its frequency, and cumulative execution time. This is how you find "what are the top 10 most expensive queries on this database?" without having to monitor in real-time.

```sql
-- List available extensions
SELECT name FROM pg_available_extensions;

-- Install extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- uuid-ossp: generate UUIDs
SELECT uuid_generate_v4();

-- pg_stat_statements: track query stats
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- pgcrypto: hashing, encryption
SELECT crypt('my_password', gen_salt('bf')) AS hashed;  -- bcrypt

-- pgvector: vector similarity search (AI/ML use cases)
CREATE EXTENSION vector;
CREATE TABLE embeddings (id SERIAL, embedding vector(1536));
SELECT * FROM embeddings ORDER BY embedding <-> '[0.1, 0.2, ...]' LIMIT 5;
-- <-> = L2 distance, <#> = inner product, <=> = cosine distance
```

> **🌍 Real world:** Install `pg_stat_statements` on every production PostgreSQL instance immediately. Set `pg_stat_statements.track = all` to capture statements inside functions. Then periodically run the top-10-by-total_exec_time query — it reliably surfaces the queries worth optimizing. A query with `mean_exec_time = 500ms` but `calls = 1` is irrelevant. A query with `mean_exec_time = 10ms` but `calls = 1,000,000` is costing you 2.8 hours of CPU per day. This is exactly the query worth optimizing.

---

## 13. Replication

Physical replication copies the entire database cluster byte-for-byte — it's simple, low-overhead, and appropriate for read replicas and high-availability standby setups. Logical replication is more selective — you can replicate specific tables to different databases, different PostgreSQL versions, or even non-PostgreSQL targets. For CDC pipelines that need to stream changes out of PostgreSQL, logical replication slots are the foundation.

```sql
-- Physical replication: exact byte copy of entire cluster
-- Logical replication: replicates specific tables by SQL operations

-- Check replication status
SELECT * FROM pg_stat_replication;  -- on primary

-- Logical replication (replicate specific tables):
-- On primary: create publication
CREATE PUBLICATION my_pub FOR TABLE orders, customers;

-- On replica: create subscription
CREATE SUBSCRIPTION my_sub
CONNECTION 'host=primary_host user=repl password=xxx dbname=mydb'
PUBLICATION my_pub;
```

> **💡 Interview tip:** "How does Debezium capture changes from PostgreSQL for CDC?" — Debezium reads from PostgreSQL's logical replication slot, which exposes the WAL (Write-Ahead Log) as a stream of decoded change events. The replication slot persists its position in the WAL, so Debezium can resume after a restart without losing changes. The operational gotcha: replication slots hold WAL indefinitely if the consumer falls behind — this can cause disk exhaustion on the primary. Monitor replication lag and disk usage on any PostgreSQL instance running a logical replication slot.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| TIMESTAMPTZ | Always use for timestamps — stores UTC |
| JSONB | Binary JSON — indexable, prefer over JSON |
| SERIAL | Auto-increment (use GENERATED ALWAYS for new code) |
| B-tree | Default index — equality + range queries |
| GIN | JSONB, arrays, full-text search |
| Partial index | Index subset of rows — smaller, faster |
| VACUUM | Reclaim dead row space from MVCC |
| EXPLAIN ANALYZE | Diagnose slow queries — read actual times |
| Range partition | Partition by date — prune old partitions |
| Recursive CTE | Hierarchies and graphs |
| pg_stat_statements | Find slow/frequent queries — install this |
