# SQL — Complete Notes from Scratch

---

## 1. Basics

SQL execution order is not the same as write order — this trips up a lot of people. You write `SELECT` first, but the engine evaluates `FROM` first, then filters rows (`WHERE`), groups them (`GROUP BY`), filters groups (`HAVING`), then finally projects the columns (`SELECT`). Understanding this order explains why you can't use a `SELECT` alias in a `WHERE` clause.

```sql
-- SELECT
SELECT name, age, salary FROM employees;
SELECT * FROM employees;
SELECT DISTINCT department FROM employees;

-- Aliases
SELECT name AS employee_name, salary * 12 AS annual_salary FROM employees;

-- WHERE
SELECT * FROM employees WHERE department = 'Engineering';
SELECT * FROM employees WHERE salary > 80000 AND age < 40;
SELECT * FROM employees WHERE department IN ('Engineering', 'Data');
SELECT * FROM employees WHERE name LIKE 'S%';    -- starts with S
SELECT * FROM employees WHERE name LIKE '%Kumar'; -- ends with Kumar
SELECT * FROM employees WHERE salary BETWEEN 50000 AND 100000;
SELECT * FROM employees WHERE manager_id IS NULL;
SELECT * FROM employees WHERE manager_id IS NOT NULL;

-- ORDER BY
SELECT * FROM employees ORDER BY salary DESC;
SELECT * FROM employees ORDER BY department ASC, salary DESC;

-- LIMIT / OFFSET
SELECT * FROM employees LIMIT 10;
SELECT * FROM employees LIMIT 10 OFFSET 20;   -- page 3 of 10
```

> **💡 Interview tip:** A classic trick question is "why can't I use my SELECT alias in WHERE?" — because `WHERE` is evaluated before `SELECT` in the logical processing order. You *can* use aliases in `ORDER BY` because that's evaluated last.

---

## 2. Aggregate Functions

Aggregates collapse multiple rows into a single value. The critical mental model: `WHERE` operates on individual rows (before grouping); `HAVING` operates on group summaries (after grouping). Getting this wrong leads to silent incorrect results.

```sql
SELECT COUNT(*) FROM employees;
SELECT COUNT(DISTINCT department) FROM employees;
SELECT SUM(salary) FROM employees;
SELECT AVG(salary) FROM employees;
SELECT MIN(salary), MAX(salary) FROM employees;

-- GROUP BY
SELECT department, COUNT(*) AS headcount, AVG(salary) AS avg_salary
FROM employees
GROUP BY department;

-- HAVING — filter on aggregated results (WHERE filters rows BEFORE grouping)
SELECT department, AVG(salary) AS avg_salary
FROM employees
GROUP BY department
HAVING AVG(salary) > 75000;

-- ORDER of execution:
-- FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT
```

> **💡 Interview tip:** `COUNT(*)` counts all rows including NULLs; `COUNT(column)` counts only non-NULL values in that column. In analytics, these can return very different numbers on sparse columns — a common source of metric discrepancies between teams.

---

## 3. JOINs

Think of a JOIN as a set operation on rows. The join condition defines which rows from each table are considered a "match." LEFT JOIN keeps all left-side rows regardless — unmatched right-side columns become NULL. INNER JOIN discards any row from either side that doesn't find a match. In DE, defaulting to INNER JOIN when you should be using LEFT JOIN is how you silently drop data from your pipeline.

```sql
-- Tables:
-- employees(id, name, dept_id, manager_id)
-- departments(id, name, location)

-- INNER JOIN — only matching rows
SELECT e.name, d.name AS dept
FROM employees e
INNER JOIN departments d ON e.dept_id = d.id;

-- LEFT JOIN — all rows from left, matching from right (NULL if no match)
SELECT e.name, d.name AS dept
FROM employees e
LEFT JOIN departments d ON e.dept_id = d.id;

-- RIGHT JOIN — all rows from right, matching from left
SELECT e.name, d.name AS dept
FROM employees e
RIGHT JOIN departments d ON e.dept_id = d.id;

-- FULL OUTER JOIN — all rows from both
SELECT e.name, d.name AS dept
FROM employees e
FULL OUTER JOIN departments d ON e.dept_id = d.id;

-- CROSS JOIN — cartesian product
SELECT e.name, d.name
FROM employees e
CROSS JOIN departments d;

-- SELF JOIN — join table to itself
SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id;

-- Multiple joins
SELECT e.name, d.name AS dept, l.city
FROM employees e
JOIN departments d ON e.dept_id = d.id
JOIN locations l ON d.location_id = l.id;
```

> **🌍 Real world:** FULL OUTER JOIN is the right tool for reconciliation queries — "show me records that exist in source but not target, and records that exist in target but not source." Filter on `WHERE source.id IS NULL OR target.id IS NULL` to isolate the mismatches.

---

## 4. Subqueries

A correlated subquery re-executes for every row in the outer query — conceptually O(n) database round trips. For large tables this is catastrophically slow. The fix is almost always a JOIN or a window function. Knowing *why* correlated subqueries are slow and how to rewrite them is a senior-level SQL skill.

```sql
-- Subquery in WHERE
SELECT name FROM employees
WHERE salary > (SELECT AVG(salary) FROM employees);

-- Subquery in FROM (derived table)
SELECT dept, avg_sal
FROM (
    SELECT department AS dept, AVG(salary) AS avg_sal
    FROM employees
    GROUP BY department
) t
WHERE avg_sal > 70000;

-- Subquery with IN
SELECT name FROM employees
WHERE dept_id IN (SELECT id FROM departments WHERE location = 'Vancouver');

-- Correlated subquery — references outer query
SELECT name, salary
FROM employees e
WHERE salary > (
    SELECT AVG(salary)
    FROM employees
    WHERE department = e.department  -- references outer e
);

-- EXISTS
SELECT name FROM departments d
WHERE EXISTS (
    SELECT 1 FROM employees e WHERE e.dept_id = d.id
);
```

> **💡 Interview tip:** `EXISTS` vs `IN` for large subquery results — `EXISTS` short-circuits as soon as it finds a match (more efficient when the subquery would return many rows). `IN` materializes the entire subquery result. For small, bounded result sets the difference is negligible; for large ones, `EXISTS` wins.

---

## 5. CTEs — Common Table Expressions

CTEs are named intermediate result sets that you define before the main query. Think of them as temporary views that exist only for the duration of that one query. The readability advantage over nested subqueries is dramatic — you read a CTE top-to-bottom like a story, rather than inside-out like nested subqueries force you to.

A nested subquery with 4 levels of nesting makes the reviewer parse it from innermost to outermost — mentally unrolling a stack. A CTE with 4 named steps reads left-to-right like a pipeline.

```sql
-- Basic CTE — cleaner than subqueries, same performance
WITH dept_avg AS (
    SELECT department, AVG(salary) AS avg_salary
    FROM employees
    GROUP BY department
)
SELECT e.name, e.salary, d.avg_salary
FROM employees e
JOIN dept_avg d ON e.department = d.department
WHERE e.salary > d.avg_salary;

-- Multiple CTEs
WITH
high_earners AS (
    SELECT * FROM employees WHERE salary > 100000
),
senior AS (
    SELECT * FROM employees WHERE years_exp > 7
)
SELECT h.name FROM high_earners h
JOIN senior s ON h.id = s.id;

-- Recursive CTE — for hierarchical data (org charts, trees)
WITH RECURSIVE org_chart AS (
    -- Anchor: start with CEO (no manager)
    SELECT id, name, manager_id, 1 AS level
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive: join each employee to their manager
    SELECT e.id, e.name, e.manager_id, oc.level + 1
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.id
)
SELECT * FROM org_chart ORDER BY level;

-- CTE vs Subquery:
-- CTE: more readable, reusable in same query, can be recursive
-- Subquery: inline, can be correlated
-- Performance: usually similar, optimizer treats them the same
```

> **💡 Interview tip:** Modern query optimizers (PostgreSQL, Snowflake, BigQuery) treat CTEs as "inline views" by default — they're not materialized. PostgreSQL added `WITH ... AS MATERIALIZED` in v12 when you *want* to force materialization (useful when you reference a CTE multiple times and want the result computed once). Knowing this distinction separates "I use CTEs for readability" from "I understand what the optimizer actually does."

> **🌍 Real world:** Recursive CTEs are the standard SQL approach for walking org hierarchies, bill-of-materials explosions, and graph traversals. In DE, you'll use them when denormalizing hierarchical category trees from an OLTP source into a flat `category_path` column for a dimension table.

---

## 6. Window Functions

The mental model for window functions: imagine each row in your result set looking through a "window" at a subset of surrounding rows. Unlike `GROUP BY`, which collapses the group into a single output row, the window function computes a value for each row while keeping all rows visible.

Think of it like a spreadsheet: `GROUP BY` is pivot table summarization; window functions are Excel formulas that reference other cells in the same sheet without collapsing the data.

The `PARTITION BY` clause is the "group by" within the window — it resets the window for each partition. `ORDER BY` within the window defines the sort order for functions like `LAG`, `LEAD`, and running totals. The `ROWS/RANGE` frame clause defines exactly how many rows each row can "see."

```sql
-- Window functions compute over a "window" of rows related to current row
-- Unlike GROUP BY, they don't collapse rows

-- Syntax: FUNCTION() OVER (PARTITION BY ... ORDER BY ... ROWS/RANGE ...)

-- ROW_NUMBER — unique sequential number
SELECT name, salary, department,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS row_num
FROM employees;

-- RANK — same rank for ties, gaps after ties (1,1,3)
SELECT name, salary,
    RANK() OVER (ORDER BY salary DESC) AS rank
FROM employees;

-- DENSE_RANK — same rank for ties, no gaps (1,1,2)
SELECT name, salary,
    DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rank
FROM employees;

-- NTILE — divide into N buckets
SELECT name, salary,
    NTILE(4) OVER (ORDER BY salary DESC) AS quartile
FROM employees;

-- LAG — access previous row's value
SELECT name, salary, date,
    LAG(salary, 1, 0) OVER (PARTITION BY department ORDER BY date) AS prev_salary,
    salary - LAG(salary, 1, 0) OVER (PARTITION BY department ORDER BY date) AS salary_change
FROM salaries;

-- LEAD — access next row's value
SELECT name, salary,
    LEAD(salary) OVER (ORDER BY hire_date) AS next_hire_salary
FROM employees;

-- FIRST_VALUE / LAST_VALUE
SELECT name, salary,
    FIRST_VALUE(salary) OVER (PARTITION BY dept ORDER BY salary DESC) AS dept_max_salary
FROM employees;

-- SUM / AVG / COUNT as window function (running totals)
SELECT date, amount,
    SUM(amount) OVER (ORDER BY date) AS running_total,
    AVG(amount) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS 7_day_avg
FROM transactions;

-- Frame clauses:
-- ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW  → running total
-- ROWS BETWEEN 6 PRECEDING AND CURRENT ROW          → rolling 7-row window
-- ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING → whole partition

-- Top N per group using ROW_NUMBER
SELECT * FROM (
    SELECT name, department, salary,
        ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rn
    FROM employees
) t
WHERE rn <= 3;   -- top 3 earners per department
```

> **💡 Interview tip:** `ROW_NUMBER` vs `RANK` vs `DENSE_RANK` is a guaranteed interview question. The practical DE use case for `ROW_NUMBER` is deduplication — when you have duplicate records and want to keep only the latest one: `ROW_NUMBER() OVER (PARTITION BY natural_key ORDER BY updated_at DESC) = 1`. `RANK` and `DENSE_RANK` are better for leaderboards where ties share a position.

> **💡 Interview tip:** The "Top N per group" pattern (using `ROW_NUMBER` in a subquery/CTE, then filtering `WHERE rn <= N`) is the canonical SQL interview problem. Know it cold. The common mistake is trying to use `LIMIT` inside a window function — you can't. The filter must happen in an outer query.

> **🌍 Real world:** Running totals (`SUM() OVER (ORDER BY date)`) and period-over-period comparisons (`LAG()`) are the two most-used window function patterns in business analytics dashboards. If your BI tool can't compute these efficiently in SQL, you end up doing it in the visualization layer — a sign of a poorly designed data model.

---

## 7. String Functions

```sql
UPPER('hello')          -- 'HELLO'
LOWER('HELLO')          -- 'hello'
LENGTH('hello')         -- 5
TRIM('  hello  ')       -- 'hello'
LTRIM('  hello')        -- 'hello'
RTRIM('hello  ')        -- 'hello'
SUBSTRING('hello', 2, 3)   -- 'ell' (start at 2, length 3)
LEFT('hello', 3)        -- 'hel'
RIGHT('hello', 3)       -- 'llo'
REPLACE('hello', 'l', 'r')  -- 'herro'
CONCAT('Hello', ' ', 'World')  -- 'Hello World'
CONCAT_WS(', ', 'a', 'b', 'c') -- 'a, b, c' (with separator)
LIKE 'S%'               -- starts with S
ILIKE 'S%'              -- case-insensitive (PostgreSQL)
POSITION('ell' IN 'hello')  -- 2
SPLIT_PART('a,b,c', ',', 2) -- 'b' (PostgreSQL)
REGEXP_REPLACE(col, '[0-9]', '', 'g')  -- remove all digits
```

> **💡 Interview tip:** Wrapping a column in a function (`UPPER(name) = 'SUHAS'`) prevents the query planner from using an index on `name`. If you need case-insensitive lookups frequently, create a functional index: `CREATE INDEX idx_name_lower ON employees(LOWER(name))`.

---

## 8. Date & Time Functions

```sql
-- Current
CURRENT_DATE            -- 2026-05-21
CURRENT_TIMESTAMP       -- 2026-05-21 10:30:00
NOW()                   -- same as CURRENT_TIMESTAMP

-- Extract parts
EXTRACT(YEAR FROM hire_date)
EXTRACT(MONTH FROM hire_date)
EXTRACT(DAY FROM hire_date)
EXTRACT(DOW FROM hire_date)   -- 0=Sunday, 6=Saturday
DATE_PART('hour', timestamp_col)

-- Arithmetic
hire_date + INTERVAL '30 days'
hire_date - INTERVAL '1 year'
AGE(CURRENT_DATE, hire_date)   -- interval between dates
DATE_TRUNC('month', timestamp_col)  -- truncate to month start
DATE_TRUNC('week', timestamp_col)

-- Formatting
TO_CHAR(hire_date, 'YYYY-MM-DD')
TO_CHAR(salary, '$999,999.00')
TO_DATE('2026-05-21', 'YYYY-MM-DD')
TO_TIMESTAMP('2026-05-21 10:30', 'YYYY-MM-DD HH24:MI')
```

> **🌍 Real world:** `DATE_TRUNC` is essential for time-series aggregations — truncating timestamps to the hour/day/week boundary so you can `GROUP BY` them consistently. Without it, every unique millisecond timestamp becomes its own group. In Redshift, prefer `DATE_TRUNC` over `EXTRACT(YEAR ...) || '-' || EXTRACT(MONTH ...)` string concatenation — the former enables partition pruning.

---

## 9. NULL Handling

NULL is not a value — it's the absence of a value. Any arithmetic or comparison involving NULL returns NULL, not an error and not `false`. This has a critical consequence for aggregations: `AVG(salary)` silently ignores NULL salaries and computes the average only over non-NULL rows, which may not be what you intend.

`COALESCE` and `NULLIF` are the two workhorses for NULL defense. Think of `COALESCE` as "give me the first non-null option." Think of `NULLIF` as "turn this specific value into NULL" — most commonly used to prevent division-by-zero.

```sql
-- NULL is unknown — not 0, not empty string
-- Any comparison with NULL returns NULL (not true/false)
-- NULL = NULL → NULL (not true!)

SELECT * FROM employees WHERE commission IS NULL;
SELECT * FROM employees WHERE commission IS NOT NULL;

-- COALESCE — return first non-null value
SELECT name, COALESCE(commission, 0) AS commission FROM employees;
SELECT COALESCE(col1, col2, col3, 'default') FROM t;

-- NULLIF — return NULL if two values are equal
SELECT NULLIF(divisor, 0)   -- prevents division by zero
SELECT 100 / NULLIF(divisor, 0) FROM t;

-- NVL (Oracle), IFNULL (MySQL) — same as COALESCE with 2 args

-- NULL in aggregates
-- COUNT(*) counts all rows including NULLs
-- COUNT(col) counts only non-NULL values
-- SUM, AVG ignore NULLs
```

> **💡 Interview tip:** `NULLIF` prevents division-by-zero elegantly: `SUM(revenue) / NULLIF(SUM(orders), 0)`. If `SUM(orders)` is 0, `NULLIF` converts it to NULL, making the whole division NULL instead of throwing a divide-by-zero error. This is cleaner than wrapping in a CASE statement and comes up in every analytics engineering interview.

> **💡 Interview tip:** `NULL = NULL` evaluates to NULL (not TRUE) — this is why joining on nullable columns can silently drop rows. Two records where both have `NULL` in the join column will NOT match. If you need NULL = NULL matching, use `IS NOT DISTINCT FROM` (PostgreSQL) or `<=>` (MySQL).

---

## 10. CASE Statements

```sql
-- Simple CASE
SELECT name, salary,
    CASE salary
        WHEN < 50000 THEN 'Low'
        WHEN < 100000 THEN 'Medium'
        ELSE 'High'
    END AS salary_band
FROM employees;

-- Searched CASE (more flexible)
SELECT name, salary,
    CASE
        WHEN salary < 50000 THEN 'Low'
        WHEN salary < 100000 THEN 'Medium'
        ELSE 'High'
    END AS salary_band
FROM employees;

-- CASE in aggregate
SELECT
    department,
    COUNT(CASE WHEN salary > 100000 THEN 1 END) AS high_earners,
    COUNT(CASE WHEN salary <= 100000 THEN 1 END) AS others
FROM employees
GROUP BY department;

-- CASE for pivot
SELECT
    department,
    SUM(CASE WHEN EXTRACT(YEAR FROM hire_date) = 2023 THEN 1 ELSE 0 END) AS hired_2023,
    SUM(CASE WHEN EXTRACT(YEAR FROM hire_date) = 2024 THEN 1 ELSE 0 END) AS hired_2024
FROM employees
GROUP BY department;
```

> **🌍 Real world:** The `CASE` inside `SUM`/`COUNT` pattern is how you do conditional aggregation — essentially a SQL pivot. It's the standard way to transform row-oriented data into column-oriented report format without leaving SQL. More portable than `PIVOT` syntax (which varies by database).

---

## 11. Query Optimisation

Reading an `EXPLAIN` plan is like reading a recipe for how the database will execute your query. The two most important signals: **Seq Scan** means the database is reading every single row in the table (full table scan) — on a 100M row table, this is your bottleneck. **Index Scan** means the database is using an index to jump directly to relevant rows — fast.

The cost number in parentheses is the planner's estimate in arbitrary units (not milliseconds). The important thing is the *relative* cost — a node with cost `10000` compared to one with cost `10` is a 1000x difference worth investigating.

```sql
-- EXPLAIN — show query plan without executing
EXPLAIN SELECT * FROM employees WHERE department = 'Engineering';

-- EXPLAIN ANALYZE — execute and show actual timing
EXPLAIN ANALYZE SELECT * FROM employees WHERE department = 'Engineering';

-- What to look for in EXPLAIN:
-- Seq Scan → full table scan (bad on large tables)
-- Index Scan → using index (good)
-- Nested Loop vs Hash Join vs Merge Join
-- Cost estimates and actual rows

-- Indexes
CREATE INDEX idx_employees_dept ON employees(department);
CREATE INDEX idx_employees_dept_salary ON employees(department, salary);  -- composite
CREATE UNIQUE INDEX idx_employees_email ON employees(email);

-- When indexes help:
-- WHERE clauses on indexed columns
-- JOIN conditions
-- ORDER BY on indexed columns

-- When indexes hurt:
-- INSERT/UPDATE/DELETE (index must be maintained)
-- Full table scans (small tables, high selectivity writes)

-- Index tips:
-- Composite index order matters — (dept, salary) helps WHERE dept=X or WHERE dept=X AND salary>Y
-- NOT LIKE '%abc' — can't use index (leading wildcard)
-- Functions on indexed column disable index: WHERE UPPER(name) = 'SUHAS' → no index
-- Better: WHERE name = LOWER('SUHAS') or use function-based index

-- Query writing tips:
-- Avoid SELECT * — specify columns
-- Filter early — push WHERE clauses down
-- Avoid DISTINCT when possible
-- Use EXISTS instead of IN for large subqueries
-- Partition pruning — filter on partition column
```

> **💡 Interview tip:** The three join algorithms in `EXPLAIN` output mean different things for performance: **Nested Loop** is efficient for small tables or when one side is highly filtered; **Hash Join** is used when both sides are large and unsorted — it builds a hash table in memory; **Merge Join** is efficient when both sides are already sorted on the join key. Seeing a Hash Join on a frequently-run query is a signal to investigate whether indexes or pre-sorting could flip it to Merge Join.

> **🌍 Real world:** In Redshift/Snowflake, `EXPLAIN` tells you about data distribution too. Seeing a `DS_DIST_ALL_INNER` node means one entire table is being broadcast to every compute node — expensive for large tables. That's a signal you've picked the wrong distribution key.

---

## 12. Normalisation

```sql
-- 1NF (First Normal Form)
-- - No repeating groups
-- - Each column is atomic (single value)
-- BAD:  employee(id, name, skills="Python,SQL,Spark")
-- GOOD: employee(id, name) + employee_skills(emp_id, skill)

-- 2NF (Second Normal Form)
-- - In 1NF
-- - No partial dependencies (non-key column depends on whole PK)
-- Applies when PK is composite
-- BAD:  order_items(order_id, product_id, product_name, qty)
--       product_name depends only on product_id, not full PK
-- GOOD: order_items(order_id, product_id, qty) + products(product_id, name)

-- 3NF (Third Normal Form)
-- - In 2NF
-- - No transitive dependencies (non-key depends on another non-key)
-- BAD:  employees(id, dept_id, dept_name)
--       dept_name depends on dept_id (non-key)
-- GOOD: employees(id, dept_id) + departments(id, name)

-- BCNF (Boyce-Codd Normal Form)
-- Stricter version of 3NF

-- Denormalisation — intentional violation of normalisation
-- Used in analytics/data warehouses for read performance
-- Trade-off: faster reads, slower writes, data redundancy
```

> **💡 Interview tip:** Interviewers sometimes ask "why do you denormalize in a data warehouse?" The precise answer: OLTP workloads do point lookups and small writes — normalization reduces write amplification and ensures consistency. OLAP workloads scan billions of rows and join large tables — each additional join multiplies query cost. Denormalization trades write complexity for read speed, which is the right tradeoff when reads happen a billion times per day and writes happen once per hour.

---

## 13. Transactions & ACID

ACID isn't just theoretical — it directly affects how you design idempotent pipelines. Atomicity means you can wrap a multi-step ETL operation in a transaction and either commit all of it or none of it, which is how you avoid partial loads corrupting a target table.

Isolation levels are the practical knob. Most databases default to `READ COMMITTED`, which prevents dirty reads but allows non-repeatable reads (the same row can look different if another transaction commits between your two reads). For analytics queries that don't write, this is usually fine. For financial reconciliation or audit pipelines, you may need `REPEATABLE READ` or `SERIALIZABLE`.

```sql
-- ACID Properties:
-- Atomicity   — all or nothing (whole transaction commits or rolls back)
-- Consistency — database moves from valid state to valid state
-- Isolation   — concurrent transactions don't interfere
-- Durability  — committed data survives failures

BEGIN;
    UPDATE accounts SET balance = balance - 100 WHERE id = 1;
    UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- If error occurs:
ROLLBACK;

-- Savepoints
BEGIN;
    INSERT INTO orders VALUES (1, 'item1');
    SAVEPOINT sp1;
    INSERT INTO orders VALUES (2, 'item2');
    ROLLBACK TO sp1;   -- undo from savepoint
COMMIT;

-- Isolation levels (strictest to most lenient):
-- SERIALIZABLE     — full isolation, no anomalies, slowest
-- REPEATABLE READ  — prevents dirty reads + non-repeatable reads
-- READ COMMITTED   — prevents dirty reads (PostgreSQL default)
-- READ UNCOMMITTED — dirty reads possible (rarely used)

SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

> **💡 Interview tip:** "What's a dirty read?" — reading uncommitted data from another transaction. With `READ UNCOMMITTED`, transaction A can read a value that transaction B has modified but not yet committed — if B rolls back, A has read data that never existed. `READ COMMITTED` prevents this. Almost no production system uses `READ UNCOMMITTED` because the data integrity risk is too high.

> **🌍 Real world:** In practice, most ETL pipelines achieve ACID-like guarantees through table-level locking patterns: write to a staging table, then `INSERT INTO final SELECT FROM staging` in a single transaction. This avoids the complexity of row-level transaction isolation while still giving you atomic swap semantics.

---

## 14. Stored Procedures & Functions (PostgreSQL)

```sql
-- Function — returns a value
CREATE OR REPLACE FUNCTION get_employee_count(dept TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    emp_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO emp_count
    FROM employees
    WHERE department = dept;
    RETURN emp_count;
END;
$$;

SELECT get_employee_count('Engineering');

-- Stored Procedure — no return value (PostgreSQL 11+)
CREATE OR REPLACE PROCEDURE update_salaries(raise_pct NUMERIC)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE employees
    SET salary = salary * (1 + raise_pct / 100);
    COMMIT;
END;
$$;

CALL update_salaries(10);

-- Trigger
CREATE OR REPLACE FUNCTION log_salary_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO salary_audit(emp_id, old_salary, new_salary, changed_at)
    VALUES (OLD.id, OLD.salary, NEW.salary, NOW());
    RETURN NEW;
END;
$$;

CREATE TRIGGER salary_change_trigger
AFTER UPDATE OF salary ON employees
FOR EACH ROW EXECUTE FUNCTION log_salary_change();
```

> **🌍 Real world:** In modern DE stacks, stored procedures are often replaced by dbt models or Python-based orchestration for the same logic — easier to version control, test, and review in pull requests. But stored procedures still have a place for database-side triggers (audit logging, enforcing constraints) where you want the logic to fire regardless of which application is writing to the table.

---

## 15. SCD — Slowly Changing Dimensions

```sql
-- Type 1: Overwrite — no history kept
UPDATE dim_customer
SET email = 'new@email.com'
WHERE customer_id = 123;

-- Type 2: Add new row — full history kept
-- Columns: surrogate_key, natural_key, attributes..., 
--          effective_date, expiry_date, is_current

-- New row when attribute changes:
INSERT INTO dim_customer (natural_key, name, email, effective_date, expiry_date, is_current)
SELECT 123, 'Suhas', 'new@email.com', CURRENT_DATE, '9999-12-31', TRUE;

-- Expire old row:
UPDATE dim_customer
SET expiry_date = CURRENT_DATE - 1, is_current = FALSE
WHERE natural_key = 123 AND is_current = TRUE;

-- Query current state:
SELECT * FROM dim_customer WHERE is_current = TRUE;

-- Query as of a date:
SELECT * FROM dim_customer 
WHERE natural_key = 123 
AND effective_date <= '2025-01-01' 
AND expiry_date >= '2025-01-01';

-- Type 3: Add column — only previous value kept
ALTER TABLE dim_customer ADD COLUMN prev_email VARCHAR;
UPDATE dim_customer
SET prev_email = email, email = 'new@email.com'
WHERE customer_id = 123;
```

> **💡 Interview tip:** SCD Type 2 queries often fail subtly when joining fact tables to dimension tables without considering the time dimension. A sales fact from 2022 joined to `dim_customer WHERE is_current = TRUE` gives you the *current* customer attributes, not the attributes *at the time of the sale*. The correct join is `ON f.customer_key = d.customer_key AND f.sale_date BETWEEN d.effective_date AND d.expiry_date`. This "as-of" join is a canonical DE interview problem.

---

## Key SQL Concepts Summary

| Concept | Key Point |
|---------|-----------|
| WHERE vs HAVING | WHERE filters rows, HAVING filters groups |
| JOIN types | INNER=match only, LEFT=all left+match, FULL=all rows |
| CTE vs Subquery | CTE=readable/reusable, Subquery=inline/correlated |
| Window vs GROUP BY | Window keeps rows, GROUP BY collapses rows |
| ROW_NUMBER vs RANK | ROW_NUMBER=unique, RANK=gaps after ties |
| NULL comparisons | Use IS NULL not = NULL |
| Index on function | UPPER(col) disables index — use computed index |
| SCD Type 2 | Add row, expire old, track with dates |
| Execution order | FROM→WHERE→GROUP BY→HAVING→SELECT→ORDER BY→LIMIT |
