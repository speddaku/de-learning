# Data Modeling — Complete Notes from Scratch

---

## 1. Core Concepts

### Entities, Attributes, Relationships

The foundation of any data model is answering: what are the things we care about, what do we know about them, and how do they relate? Getting this right at the start prevents the painful schema migrations that come from "we didn't think about X" six months into production.

- **Entity** — a real-world object (Customer, Order, Product)
- **Attribute** — property of an entity (Customer.name, Customer.email)
- **Relationship** — how entities relate (Customer PLACES Order)

### Keys

```
Primary Key (PK)   — uniquely identifies a row (customer_id)
Foreign Key (FK)   — references PK of another table (order.customer_id → customer.id)
Surrogate Key      — system-generated key (auto-increment ID, UUID) — no business meaning
Natural Key        — real-world identifier (SSN, email, ISBN) — has business meaning
Composite Key      — PK made of multiple columns (order_id + product_id)
```

> **💡 Interview tip:** Surrogate vs natural key is a classic modeling debate. Natural keys look convenient but have a fatal flaw in analytics: they can *change* (a customer changes their email, a product gets a new SKU). In OLTP, that might be manageable with cascading updates. In a data warehouse with billions of fact rows pointing at a dimension, updating the FK across the entire fact table is catastrophic. Surrogate keys insulate the fact table from these changes — that's why every dimension table gets a system-generated `customer_key` separate from the source `customer_id`.

### Cardinality

```
One-to-One (1:1)     — one person has one passport
One-to-Many (1:N)    — one customer has many orders
Many-to-Many (M:N)   — students have many courses, courses have many students
                       → resolved with a junction/bridge table
```

---

## 2. ER Diagrams (Entity-Relationship)

```
[Customer] ---places---> [Order] ---contains---> [Product]
    |                       |
    PK: customer_id         PK: order_id
    name                    customer_id (FK)
    email                   order_date
                            total_amount
```

**Junction table for M:N:**
```
[Student] ---enrolled_in---> [Enrollment] ---for---> [Course]
                                  |
                                student_id (FK)
                                course_id (FK)
                                enrollment_date
                                grade
```

> **🌍 Real world:** In DE, the junction/bridge table in a many-to-many relationship often becomes a fact table in the warehouse model. `Enrollment` above has measures (grade), timestamps, and links to two entities — structurally, it's already thinking like a fact table.

---

## 3. Normalisation

Normalization is about eliminating redundancy and update anomalies. In an OLTP system, if the same piece of data lives in 10 places, you need to update it in 10 places when it changes — and if you miss one, you have inconsistent data. The normal forms are progressive: each higher form eliminates a specific class of redundancy.

### 1NF — First Normal Form
- Each column has atomic (indivisible) values
- No repeating groups
- Each row is unique

```
BAD (not 1NF):
| id | name  | phones              |
|----|-------|---------------------|
| 1  | Suhas | 123-456, 789-012   |  ← multiple values in one cell

GOOD (1NF):
| id | name  | phone   |
|----|-------|---------|
| 1  | Suhas | 123-456 |
| 1  | Suhas | 789-012 |
```

### 2NF — Second Normal Form
- Must be in 1NF
- No partial dependencies (every non-key attribute depends on the WHOLE primary key)
- Applies when PK is composite

```
BAD (not 2NF):
order_items(order_id, product_id, product_name, quantity)
PK = (order_id, product_id)
product_name depends only on product_id — partial dependency!

GOOD (2NF):
order_items(order_id, product_id, quantity)   PK = (order_id, product_id)
products(product_id, product_name)             PK = product_id
```

### 3NF — Third Normal Form
- Must be in 2NF
- No transitive dependencies (non-key attribute depends on another non-key attribute)

```
BAD (not 3NF):
employees(id, dept_id, dept_name)
dept_name depends on dept_id (non-key) — transitive dependency!

GOOD (3NF):
employees(id, dept_id)
departments(dept_id, dept_name)
```

### When to Denormalise

In OLTP, normalization is the right default — it keeps writes fast and data consistent. In OLAP, you deliberately break these rules because the query patterns are completely different. An analyst querying 3 billion rows needs to join `fact_sales → dim_customer → dim_city → dim_country` just to get the customer's country. That's 4 table scans and 3 hash joins on billions of rows.

By denormalizing `dim_customer` to include `city`, `country`, and `region` directly, you eliminate those joins entirely. The data redundancy (storing "Canada" 10 million times in the customer dimension) is a worthwhile tradeoff when it means shaving minutes off every report run.

- In OLAP/analytics databases — fewer joins = faster reads
- Reporting tables, data marts
- Trade-off: read performance vs write complexity + storage

---

## 4. Dimensional Modeling (Data Warehousing)

### OLTP vs OLAP

The reason these two worlds use different schemas isn't philosophical — it's physical. OLTP systems optimize for small, fast, transactional writes. Every normalization rule you follow reduces write amplification. OLAP systems optimize for reading and aggregating millions to billions of rows. Every join you add to a query on billions of rows is a potential minute of wall-clock time.

```
OLTP (Online Transaction Processing)    OLAP (Online Analytical Processing)
- Normalised (3NF)                      - Denormalised (star/snowflake)
- Many small transactions               - Few complex queries
- Row-level operations                  - Aggregate, scan, join
- Current data                          - Historical data
- PostgreSQL, MySQL                     - Redshift, Snowflake, BigQuery
```

### Facts and Dimensions

The fact table is the center of gravity. It's where the events live — every sale, every click, every payment. Fact tables are wide (many FK columns to dimensions) and deep (billions of rows). Dimension tables are the context — they answer "who, what, when, where" about each fact. They're wide (many descriptive attributes) but relatively shallow.

**Fact Table**
- Stores measurable, quantitative data (events/transactions)
- Contains: foreign keys to dimensions + measures (metrics)
- Very large — millions/billions of rows
- Examples: sales_fact, page_view_fact, payment_fact

**Dimension Table**
- Stores descriptive/context data
- Contains: attributes about facts
- Relatively small — thousands/millions of rows
- Examples: customer_dim, product_dim, date_dim, store_dim

```
Fact table example:
sales_fact:
  date_key (FK → date_dim)
  customer_key (FK → customer_dim)
  product_key (FK → product_dim)
  store_key (FK → store_dim)
  quantity_sold    ← measure
  revenue          ← measure
  discount_amount  ← measure

Dimension table example:
customer_dim:
  customer_key (PK — surrogate)
  customer_id (natural key)
  name
  email
  city
  country
  age_group
```

### Grain

The grain is the single most important concept in dimensional modeling — and the most common interview trap. The grain defines exactly what one row in the fact table represents. Get this wrong and every metric derived from the table will be either double-counted or under-counted.

Interviewers test this by describing a business scenario and asking "what's the grain?" The wrong answer is vague: "transactions." The right answer is precise: "one row per line item per sales order" or "one row per customer per day per product category."

- The grain of a fact table = the level of detail of each row
- "One row per transaction", "one row per day per customer", etc.
- Must define grain BEFORE designing the fact table
- Example: "one row per line item on each sales order"

> **💡 Interview tip:** The grain also constrains which measures are valid. If your grain is "one row per order header" you cannot store individual line item prices — that would be at a different grain. Mixing grains in one fact table is a design error that causes incorrect aggregations. "Always declare the grain explicitly" is the Kimball rule that prevents 80% of dimensional modeling bugs.

### Measures

Not all measures behave the same under aggregation — and treating a semi-additive or non-additive measure as fully additive gives you wrong numbers that look right until someone checks them carefully.

- **Additive** — can SUM across all dimensions (revenue, quantity)
- **Semi-additive** — can SUM across some dimensions (bank balance → sum across accounts, not time)
- **Non-additive** — cannot SUM (ratios, percentages, averages)

> **💡 Interview tip:** Account balance is the canonical semi-additive example. `SUM(balance)` across all accounts at a point in time = total deposits (meaningful). `SUM(balance)` across time = meaningless (you'd be summing Monday's balance, Tuesday's balance, etc.). The right query for balance over time uses `LAST_VALUE` or a snapshot at a specific date, not a SUM.

---

## 5. Star Schema

The star schema gets its name from the visual — a central fact table with dimension tables radiating outward like points on a star. The key design principle is that dimensions are **flat and wide**: instead of normalizing `dim_customer` into separate `city`, `state`, and `country` tables, you collapse all that context into one wide `dim_customer` row. This is intentional — it eliminates joins at query time.

```
                [date_dim]
                     |
[store_dim] -- [sales_fact] -- [product_dim]
                     |
               [customer_dim]
```

- Central fact table surrounded by denormalised dimension tables
- Dimensions are NOT further normalised (flat/wide)
- **Pros:** Simple queries, fewer joins, fast performance
- **Cons:** Data redundancy in dimensions

```sql
-- Example star schema query
SELECT
    d.year,
    d.quarter,
    c.country,
    p.category,
    SUM(f.revenue) AS total_revenue
FROM sales_fact f
JOIN date_dim d ON f.date_key = d.date_key
JOIN customer_dim c ON f.customer_key = c.customer_key
JOIN product_dim p ON f.product_key = p.product_key
WHERE d.year = 2025
GROUP BY d.year, d.quarter, c.country, p.category;
```

> **🌍 Real world:** BI tools like Tableau, Power BI, and Looker are built around the star schema mental model. When they auto-detect relationships, they expect a star — one central table joined to descriptive tables on surrogate keys. A heavily normalized snowflake schema forces these tools to generate multi-hop join chains that are slower and harder for analysts to navigate. Star schema is the practical answer to "what schema should I build for self-service analytics?"

---

## 6. Snowflake Schema

In a snowflake schema, dimensions are normalized — instead of one wide `dim_customer` with city/state/country attributes, you have `dim_customer` pointing to `dim_city` pointing to `dim_country`. This reduces storage (you're not storing "United States" in every customer row) but adds joins to every query.

```
[date_dim]
    |
[quarter_dim] -- [date_dim]
[store_dim] -- [sales_fact] -- [product_dim] -- [category_dim]
                     |
               [customer_dim] -- [city_dim] -- [country_dim]
```

- Dimensions are normalised into multiple related tables
- **Pros:** Less storage, cleaner/more normalised
- **Cons:** More joins, more complex queries, slower performance

**Star vs Snowflake — when to use:**
- Star: most analytics use cases — simpler, faster, BI tools prefer it
- Snowflake: when dimension tables are very large, storage matters, strict governance

> **💡 Interview tip:** "Star vs snowflake" is a stock interview question. The complete answer: star schema wins for query performance and BI tool compatibility. Snowflake schema wins when dimension tables themselves have millions of rows and you need to avoid storing redundant attribute data. In practice, the storage savings of snowflake rarely justify the query complexity — most experienced DEs default to star unless there's a specific reason not to.

---

## 7. Slowly Changing Dimensions (SCD)

SCDs solve a fundamental problem: the real world changes, but analytics needs to be able to answer "what was true at the time of this event?" A customer who moved from Toronto to Vancouver in 2024 — did their pre-2024 orders come from Toronto or Vancouver? The answer depends entirely on which SCD type you've implemented.

### Type 1 — Overwrite (No History)
```sql
UPDATE customer_dim SET email = 'new@email.com' WHERE customer_key = 123;
-- Old email is lost forever
-- Use when: history doesn't matter (typo corrections)
```

### Type 2 — Add New Row (Full History)

Type 2 is the most common and most powerful SCD type. When an attribute changes, you expire the old row and insert a new one. Every fact table row that happened while the old row was active will join to the old row (via the surrogate key FK), correctly reflecting the world as it was at that time.

```sql
-- Most common SCD type
customer_dim:
| cust_key | cust_id | name  | email           | eff_date   | exp_date   | is_current |
|----------|---------|-------|-----------------|------------|------------|------------|
| 1        | C001    | Suhas | old@email.com   | 2020-01-01 | 2025-05-20 | FALSE      |
| 2        | C001    | Suhas | new@email.com   | 2025-05-21 | 9999-12-31 | TRUE       |

-- Implementation:
-- 1. Detect change (compare source to current dim row)
-- 2. Expire old row (set exp_date, is_current=FALSE)
-- 3. Insert new row with new values
```

> **💡 Interview tip:** Why does SCD Type 2 use a surrogate key? Because the fact table's FK points to a specific version of the dimension, not the logical entity. If `sales_fact.customer_key = 1`, it means "the version of customer C001 that was active during the 2020–2025 period." If we used the natural key `C001`, we couldn't distinguish which version of the customer was active at sale time. The surrogate key is what makes the "point-in-time" join possible.

### Type 3 — Add Column (One Previous Value)
```sql
customer_dim:
| cust_key | name  | current_email  | prev_email    |
|----------|-------|----------------|---------------|
| 1        | Suhas | new@email.com  | old@email.com |

-- Only keeps one historical value
-- Use when: you only need to know the previous state
```

### Type 4 — History Table
```
customer_dim (current) + customer_history (all changes)
```

### Type 6 — Hybrid (1+2+3)
```
Combines Type 1 (overwrite) + Type 2 (new rows) + Type 3 (prev column)
```

---

## 8. Date Dimension

The date dimension is arguably the most important dimension in any data warehouse — it joins to almost every fact table and enables every kind of time-based analysis. The reason you pre-populate it with attributes like `is_weekend`, `is_holiday`, `fiscal_quarter` is so analysts don't have to derive these in every query — the derivation happens once, at dimension build time, not at every report render.

```sql
CREATE TABLE date_dim (
    date_key        INTEGER PRIMARY KEY,    -- 20260521
    full_date       DATE,                   -- 2026-05-21
    day_of_week     INTEGER,                -- 3 (Wednesday)
    day_name        VARCHAR(10),            -- 'Wednesday'
    day_of_month    INTEGER,                -- 21
    day_of_year     INTEGER,                -- 141
    week_of_year    INTEGER,                -- 21
    month_number    INTEGER,                -- 5
    month_name      VARCHAR(10),            -- 'May'
    quarter         INTEGER,                -- 2
    quarter_name    VARCHAR(6),             -- 'Q2'
    year            INTEGER,                -- 2026
    is_weekend      BOOLEAN,                -- FALSE
    is_holiday      BOOLEAN,                -- FALSE
    fiscal_year     INTEGER,                -- depends on company
    fiscal_quarter  INTEGER
);
```

> **🌍 Real world:** Populate 10+ years of date dimension rows at warehouse creation — it's a trivially small table (3,650 rows per decade). The `is_holiday` column requires a list of company-specific holidays, which becomes a recurring maintenance task but pays dividends every time someone asks "compare revenue on business days only."

---

## 9. Medallion Architecture (Modern Data Lakes)

The medallion architecture is the modern DE answer to "how do I build a data lake that's actually usable?" It solves the classic data lake problem: raw data gets dumped in, nothing is trusted, and everyone builds their own cleaning logic independently. Medallion enforces three quality tiers with clear contracts at each layer boundary.

Think of it like a water purification system: Bronze is the raw intake (untreated), Silver is filtered and safe to drink, Gold is the bottled water ready for distribution.

```
Raw Data Sources
      ↓
[Bronze Layer] — Raw, as-is ingestion
    - Exact copy of source data
    - No transformations
    - Append only
    - Stores everything: CSV, JSON, Parquet
      ↓
[Silver Layer] — Cleaned, conformed
    - Deduplication
    - Data quality checks
    - Schema standardisation
    - Joins across sources
      ↓
[Gold Layer] — Business-ready aggregates
    - Dimensional models (star schema)
    - Business metrics
    - Reporting tables
    - Feature tables for ML
```

> **💡 Interview tip:** The Bronze layer's defining property is immutability and fidelity — it's an exact replica of the source. This means if a transformation bug corrupts Silver data, you can always reprocess from Bronze. The "append only" rule means you never delete from Bronze; you just reprocess downstream layers. This is the architecture-level equivalent of immutable data in functional programming.

> **🌍 Real world:** In Databricks/Delta Lake, Medallion maps directly to database schemas: `bronze.orders`, `silver.orders_clean`, `gold.daily_order_summary`. The layering also maps to data contract ownership — the ingestion team owns Bronze, the data engineering team owns Silver, and the analytics team owns Gold. Each layer has different SLAs, quality checks, and access controls.

---

## 10. Data Vault

Used for enterprise data warehouses with complex source systems:

- **Hub** — core business entities (customer, product, order)
- **Link** — relationships between hubs
- **Satellite** — attributes and context for hubs/links

```
Hub_Customer:    customer_hash_key, load_date, source, customer_id
Hub_Product:     product_hash_key, load_date, source, product_id
Link_Purchase:   link_hash_key, customer_hash_key, product_hash_key, load_date, source
Sat_Customer:    customer_hash_key, load_date, name, email, phone
```

**Data Vault vs Star Schema:**
- Data Vault: flexible, audit-friendly, handles schema changes well, complex
- Star Schema: simpler, faster queries, better for BI tools

> **🌍 Real world:** Data Vault is designed for organizations that need a complete, auditable history of every change from every source system — financial services, healthcare, government. The `load_date` and `source` columns on every table are first-class citizens, not afterthoughts. The trade-off is query complexity: a simple analytical query that's 4 table joins in star schema might be 12+ joins in Data Vault. Most teams add a star-schema presentation layer on top of Data Vault for analyst consumption.

---

## Key Summary

| Concept | One-liner |
|---------|-----------|
| Fact table | Measures/events — large, FK to dims |
| Dimension table | Context/attributes — smaller, descriptive |
| Star schema | Flat dims around fact — simple, fast |
| Snowflake schema | Normalised dims — more joins, less storage |
| SCD Type 1 | Overwrite — no history |
| SCD Type 2 | New row — full history, most common |
| SCD Type 3 | New column — one prev value |
| Grain | Level of detail per fact row — define first! |
| Additive measure | Can SUM across all dims (revenue) |
| Semi-additive | Can SUM across some dims (balance) |
| Medallion | Bronze(raw) → Silver(clean) → Gold(ready) |
