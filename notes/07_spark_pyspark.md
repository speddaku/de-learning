# Apache Spark & PySpark — Complete Notes from Scratch

---

## 1. Architecture

### Core Components

The driver/executor relationship is the foundational mental model for everything else in Spark. Think of it like an orchestra: the **Driver is the conductor** — it reads the score (your code), decides the plan of attack, and assigns tasks to musicians. The **Executors are the musicians** — each plays their assigned part independently, on their own node, with their own section of data. The conductor doesn't play an instrument; the musicians don't know the full score. When you call `collect()` and bring all data back to the driver, you're asking every musician to hand their instrument to the conductor — which is why it's dangerous on large datasets.

```
Driver:
- Main program (your Python/Scala code)
- Creates SparkContext/SparkSession
- Builds execution plan (DAG)
- Schedules tasks on executors
- Runs on master node

Executor:
- Worker process on each node
- Runs tasks (units of work)
- Stores data in memory/disk (RDD partitions, cached DataFrames)
- Reports back to driver

Cluster Manager (picks which nodes to run on):
- Standalone — Spark's built-in
- YARN — Hadoop resource manager
- Kubernetes — container orchestration
- AWS Glue uses a managed Spark cluster

SparkSession:
- Entry point (replaces SparkContext, SQLContext, HiveContext)
- spark = SparkSession.builder.appName("app").getOrCreate()
```

> **💡 Interview tip:** "What happens when you call `collect()` on a large DataFrame?" — All data from all executor partitions is serialized, sent over the network to the driver, and materialized in the driver's JVM/Python process. If the data is larger than driver memory, you get an OOM crash. In production, you never `collect()` large DataFrames — you `write()` them to storage and let the executors do the work.

### DAG — Directed Acyclic Graph

Lazy evaluation is one of the most powerful and misunderstood features of Spark. When you write `df.filter(...).groupBy(...).agg(...)`, **none of that code executes**. Spark builds a logical plan — a description of what you want. Only when you trigger an action does Spark compile that plan into a physical execution plan, optimize it (reordering operations, pushing filters down to the source), and execute it.

The practical implication: Spark's Catalyst optimizer can see your entire transformation chain before executing any of it. It can push a filter all the way down to the Parquet reader to skip row groups, reorder joins, and eliminate redundant operations. This optimization is **impossible** in an eager execution model like Pandas, where each operation executes immediately.

```
Each Spark job is compiled into a DAG of stages.

RDD lineage: A → filter → B → map → C → reduceByKey → D
                                                         ↑ action

Stages: separated by shuffle boundaries (wide transformations)
Tasks: each stage split into N tasks (one per partition)

Lazy evaluation:
- Transformations (filter, map, select) are NOT executed immediately
- Only executed when an action is called (count, collect, write)
- Allows Spark to optimize the full plan before execution

Action (triggers execution): collect, count, show, write, take, first
Transformation (builds DAG): filter, map, select, join, groupBy
```

> **🌍 Real world:** A common mistake is calling `df.count()` mid-pipeline to "check progress" or validate intermediate results. Every `count()` is a full execution of everything up to that point — if you call it 5 times in a pipeline, you've potentially run the expensive parts 5 times. Cache the DataFrame first if you need to materialize it, then call `count()` once.

---

## 2. RDDs — Resilient Distributed Datasets

RDDs are Spark's original low-level API. In modern PySpark, you'll rarely write RDD code directly — DataFrames are almost always the right choice because they leverage the Catalyst optimizer. RDDs are useful for non-tabular data, custom serialization, and cases where you need fine-grained control over partitioning.

### Basics
```
- Low-level API (avoid in practice — use DataFrames)
- Immutable distributed collection of objects
- Fault-tolerant: can recompute from lineage on failure
- Distributed across partitions (one per CPU core by default)
```

### Transformations (lazy)
```python
rdd = sc.parallelize([1, 2, 3, 4, 5])
rdd.map(lambda x: x * 2)        # [2, 4, 6, 8, 10]
rdd.filter(lambda x: x > 2)     # [3, 4, 5]
rdd.flatMap(lambda x: [x, x*2]) # [1, 2, 2, 4, 3, 6, ...]
rdd.reduceByKey(lambda a,b: a+b) # for (key, value) RDDs
```

### Actions (trigger execution)
```python
rdd.collect()   # returns all data to driver — careful with large data!
rdd.count()     # number of elements
rdd.take(5)     # first 5 elements
rdd.first()     # first element
rdd.saveAsTextFile("s3://bucket/output/")
```

### RDD vs DataFrame vs Dataset

The key insight: DataFrames give Spark structural information (column names, types). With that structure, the Catalyst optimizer can make intelligent decisions — pushdown predicates to data sources, eliminate unnecessary column reads, choose optimal join strategies. RDDs are opaque Python objects — Spark can't reason about their content and has to treat each element as a black box.

```
RDD:
- No schema
- Python objects (no optimization)
- Low-level control
- Use for: non-tabular data, custom partitioning

DataFrame:
- Schema (column names + types)
- Optimized by Catalyst optimizer
- Python, Scala, Java, R
- Use for: tabular data (SQL-like operations)

Dataset (Scala/Java only):
- Type-safe DataFrame
- Compile-time type checking
- Not available in Python
```

---

## 3. DataFrames

### Creating DataFrames

Always provide an explicit schema when reading data in production. `inferSchema=True` reads the entire file (or a sample) to guess types — it's expensive and error-prone. A column that's `NULL` in all sample rows will be inferred as `StringType` when you might want `IntegerType`. Explicit schemas also serve as documentation and catch upstream type changes early.

```python
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

spark = SparkSession.builder.appName("example").getOrCreate()

# From Python list
data = [("Alice", 30, 90000.0), ("Bob", 25, 75000.0)]
schema = StructType([
    StructField("name", StringType(), True),
    StructField("age", IntegerType(), True),
    StructField("salary", DoubleType(), True)
])
df = spark.createDataFrame(data, schema)

# From CSV
df = spark.read.option("header", "true").option("inferSchema", "true").csv("s3://bucket/data.csv")

# From Parquet
df = spark.read.parquet("s3://bucket/data/")

# From JSON
df = spark.read.json("s3://bucket/data.json")

# Show
df.show()
df.printSchema()
```

### Transformations

DataFrame transformations are the building blocks of every PySpark job. They're all lazy — calling `.filter()` or `.withColumn()` returns a new DataFrame representing the plan, not a new copy of the data. The actual computation happens when you call an action.

```python
from pyspark.sql.functions import col, lit, when, upper, lower, trim, round

# Select columns
df.select("name", "salary")
df.select(col("name"), col("salary") * 1.1)

# Filter
df.filter(col("age") > 25)
df.filter((col("age") > 25) & (col("salary") > 80000))

# Add/modify column
df.withColumn("annual_bonus", col("salary") * 0.1)
df.withColumn("salary", round(col("salary"), 2))
df.withColumn("name_upper", upper(col("name")))

# Drop column
df.drop("age")

# Rename column
df.withColumnRenamed("salary", "annual_salary")

# Conditional (CASE WHEN equivalent)
df.withColumn("category",
    when(col("salary") > 100000, "high")
    .when(col("salary") > 70000, "medium")
    .otherwise("low")
)

# Alias
df.select(col("name").alias("employee_name"))

# Cast
df.withColumn("age", col("age").cast("double"))
```

### Aggregations

`groupBy().agg()` is the workhorse of analytical Spark pipelines. The key optimization: avoid chaining multiple separate `groupBy` operations on the same DataFrame — combine them into a single `agg()` call. Each `groupBy().agg()` is a shuffle (data moves across the network to co-locate matching keys) — doing it once is always better than twice.

```python
from pyspark.sql.functions import count, sum, avg, max, min, countDistinct, collect_list

# GroupBy + aggregate
df.groupBy("department").agg(
    count("*").alias("headcount"),
    avg("salary").alias("avg_salary"),
    max("salary").alias("max_salary"),
    sum("salary").alias("total_salary")
)

# Multiple group-by keys
df.groupBy("department", "year").agg(sum("revenue").alias("total_revenue"))

# Count distinct
df.select(countDistinct("customer_id").alias("unique_customers"))

# Collect values into array
df.groupBy("department").agg(collect_list("name").alias("employees"))
```

### Joins

Joins are the most performance-sensitive DataFrame operation because most join strategies require a **shuffle** — redistributing data across the cluster so matching keys land on the same executor. The shuffle involves serialization, network transfer, and deserialization — all expensive. Understanding when each join type avoids the shuffle (broadcast join) vs. requires it (sort-merge join) is essential for writing performant pipelines.

```python
# Inner join
df_orders.join(df_customers, df_orders.customer_id == df_customers.id, "inner")

# Left join
df_orders.join(df_customers, df_orders.customer_id == df_customers.id, "left")

# Right, full outer
df.join(other, "key", "right")
df.join(other, "key", "full")

# Semi join — keeps rows in left where match exists in right
df_orders.join(df_vip_customers, "customer_id", "left_semi")

# Anti join — keeps rows in left where NO match in right
df_orders.join(df_blacklisted, "customer_id", "left_anti")

# Multiple join conditions
df1.join(df2, (df1.id == df2.id) & (df1.date == df2.date), "inner")

# Avoid column ambiguity after join
df1.join(df2, ["customer_id"])  # use list form — drops duplicate key column
```

> **💡 Interview tip:** "What's the difference between a semi-join and an inner join?" — Semi-join filters the left table to only rows that have a match in the right table, but returns **only left table columns** (no columns from right). Inner join returns combined columns from both tables. Semi-join is more efficient when you only need to check existence (no right-side columns needed) because Spark can short-circuit after finding the first match.

---

## 4. Spark SQL

Spark SQL and the DataFrame API are equivalent — they compile to the same physical execution plan. Use SQL when the logic is complex enough that SQL reads more clearly, or when collaborating with analysts who know SQL. Use the DataFrame API when you're building reusable functions or when the transformation logic is dynamic/programmatic.

```python
# Register as temp view
df.createOrReplaceTempView("sales")

# Run SQL
result = spark.sql("""
    SELECT 
        customer_id,
        DATE_TRUNC('month', sale_date) AS month,
        SUM(amount) AS total
    FROM sales
    WHERE year = 2025
    GROUP BY 1, 2
    ORDER BY 2, 3 DESC
""")

# Global temp view (across sessions)
df.createGlobalTempView("global_sales")
spark.sql("SELECT * FROM global_temp.global_sales")
```

---

## 5. Window Functions

Window functions are how you do "running totals," "rank within group," "previous row's value," and similar calculations in Spark without self-joins. The `Window` spec defines the partition (group), ordering, and frame (which rows to include in each calculation). Think of it like Excel's SUMIF but applied to each row with full awareness of its surrounding context.

Window functions are executed as a single pass over the data per window partition — much more efficient than equivalent self-join approaches. However, they do trigger a shuffle to co-locate all rows for each partition key.

```python
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number, rank, dense_rank, lag, lead, sum as _sum, avg as _avg

# Window spec
window = Window.partitionBy("department").orderBy(col("salary").desc())

# Row number, rank, dense rank
df.withColumn("row_num", row_number().over(window))
df.withColumn("rank", rank().over(window))
df.withColumn("dense_rank", dense_rank().over(window))

# Running total
window_running = Window.partitionBy("customer_id").orderBy("sale_date") \
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
df.withColumn("running_total", _sum("amount").over(window_running))

# Lag and Lead
df.withColumn("prev_sale", lag("amount", 1).over(window))
df.withColumn("next_sale", lead("amount", 1).over(window))

# Window with frame (range)
window_7d = Window.partitionBy("store").orderBy("sale_date") \
    .rangeBetween(-6, 0)  # last 7 days
df.withColumn("rolling_7d_avg", _avg("amount").over(window_7d))
```

> **💡 Interview tip:** "What's the difference between `rank()` and `dense_rank()`?" — With ties, `rank()` leaves gaps (1, 2, 2, 4) while `dense_rank()` doesn't (1, 2, 2, 3). `row_number()` always produces unique sequential numbers even for ties — the tiebreaker is non-deterministic unless you include a tiebreaker column in the `orderBy`. This distinction matters in "top N per group" queries where tie handling affects result correctness.

---

## 6. String, Date, Null Functions

Spark's built-in functions are the correct tool for transformations on DataFrames. They operate natively on JVM types (columnar, vectorized where possible) and are optimized by Catalyst. The alternative — Python UDFs — serialize each row from JVM to Python, transform it, and serialize back. For large DataFrames, this overhead is significant and measurable.

```python
from pyspark.sql.functions import (
    substring, concat, concat_ws, split, regexp_replace, regexp_extract,
    to_date, to_timestamp, date_format, datediff, months_between,
    year, month, dayofweek,
    coalesce, isnan, isnull, when
)

# String
df.withColumn("first3", substring("name", 1, 3))
df.withColumn("full_name", concat("first", lit(" "), "last"))
df.withColumn("full_name", concat_ws(" ", "first", "last"))
df.withColumn("parts", split("email", "@"))
df.withColumn("clean", regexp_replace("phone", "[^0-9]", ""))
df.withColumn("domain", regexp_extract("email", "@(.+)", 1))

# Date
df.withColumn("dt", to_date("date_str", "yyyy-MM-dd"))
df.withColumn("ts", to_timestamp("ts_str", "yyyy-MM-dd HH:mm:ss"))
df.withColumn("formatted", date_format("dt", "MM/dd/yyyy"))
df.withColumn("days_diff", datediff("end_date", "start_date"))
df.withColumn("yr", year("dt"))
df.withColumn("mo", month("dt"))

# Null handling
df.withColumn("val", coalesce("col1", "col2", lit(0)))  # first non-null
df.filter(col("name").isNull())
df.filter(col("name").isNotNull())
df.na.drop()              # drop rows with any null
df.na.drop(subset=["id"]) # drop rows where id is null
df.na.fill(0)             # fill all nulls with 0
df.na.fill({"age": 0, "name": "Unknown"})
```

---

## 7. UDFs — User Defined Functions

UDFs are the escape hatch when built-in Spark functions can't express your logic. But they come with a real performance cost that's important to understand before reaching for them. A regular Python UDF breaks the JVM-native execution path: Spark must serialize each row from JVM to the Python process, run your Python function, and deserialize the result back to JVM. On a large DataFrame, this per-row overhead adds up fast.

```python
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType, IntegerType

# Define Python function
def classify_salary(salary):
    if salary is None:
        return "unknown"
    if salary > 100000:
        return "high"
    elif salary > 70000:
        return "medium"
    return "low"

# Register as UDF
classify_udf = udf(classify_salary, StringType())

# Use in DataFrame
df.withColumn("salary_band", classify_udf(col("salary")))

# Decorator syntax
@udf(returnType=StringType())
def format_name(first, last):
    return f"{last.upper()}, {first.title()}" if first and last else None

df.withColumn("formatted", format_name("first_name", "last_name"))

# WARNING: UDFs are slow — they serialize/deserialize Python objects
# Prefer built-in Spark functions when possible
# For better performance: pandas UDFs (vectorized)
```

> **💡 Interview tip:** "Why are Python UDFs slow in PySpark and how do you fix it?" — Regular UDFs are slow because of row-by-row serialization between JVM and Python. Pandas UDFs (vectorized UDFs) are ~10-100x faster because data is batched as Arrow-columnar format and passed as Pandas Series — far less overhead. Best fix is to replace UDFs with built-in Spark SQL functions. If you truly need custom logic, use a Pandas UDF. If you need truly complex logic that can't be vectorized, accept the UDF cost or rewrite in Scala.

### Pandas UDFs (Vectorized)

Pandas UDFs use Apache Arrow for zero-copy data transfer between JVM and Python, operating on entire column batches (Pandas Series) rather than individual rows. The speedup is dramatic for numeric and string operations because you're leveraging optimized Pandas/NumPy operations on the entire column at once rather than Python function calls per row.

```python
from pyspark.sql.functions import pandas_udf
import pandas as pd

@pandas_udf(returnType="double")
def calculate_tax(salary: pd.Series) -> pd.Series:
    return salary * 0.3

df.withColumn("tax", calculate_tax(col("salary")))
# Much faster than regular UDF — operates on Pandas Series in batches
```

---

## 8. Reading and Writing

Controlling the number of output files is critical for downstream query performance. `repartition(N)` before write gives you N files — balance between file size and parallelism. For Athena and Redshift Spectrum, files between 128MB and 1GB are ideal. Smaller files cause excessive list/open overhead; larger files reduce parallelism in downstream reads.

```python
# Read Parquet
df = spark.read.parquet("s3://bucket/data/year=2025/")

# Read with schema
df = spark.read.schema(schema).parquet("s3://bucket/")

# Write Parquet (partitioned)
df.write \
  .mode("overwrite") \           # overwrite | append | ignore | error
  .partitionBy("year", "month") \
  .parquet("s3://bucket/output/")

# Write CSV
df.write.mode("overwrite").option("header", "true").csv("s3://bucket/out.csv")

# Write with repartitioning (control number of output files)
df.repartition(10).write.mode("overwrite").parquet("s3://bucket/")
# or
df.coalesce(1).write.mode("overwrite").csv("s3://bucket/")  # single file

# Read from Glue Catalog (in Glue jobs)
df = glueContext.create_dynamic_frame.from_catalog(
    database="my_db", table_name="sales"
).toDF()
```

> **🌍 Real world:** Writing with `partitionBy` on a high-cardinality column (like `user_id`) is a common mistake that creates millions of tiny files — one per unique value per task. Always validate that your partition column has a manageable cardinality (date, region, status — not user_id or order_id). A table with 10M users partitioned by user_id creates 10M files per daily load.

---

## 9. Performance Optimisation

### Partitions

Spark processes data in parallel across partitions — one task per partition per stage. Too few partitions means underutilized CPU (many cores sit idle). Too many means excessive scheduling overhead and tiny tasks. The sweet spot for most production jobs is partitions between 128MB and 512MB each. `spark.sql.shuffle.partitions` defaults to 200 — designed for large clusters. On a 10-node Glue job processing 10GB of data, 200 shuffle partitions means 200 50MB tasks, which is fine. For a 1GB dataset, drop it to 20-50.

```python
# Check number of partitions
df.rdd.getNumPartitions()

# Repartition — full shuffle, evenly distributes data
df.repartition(200)                          # by count
df.repartition(200, col("customer_id"))      # by column (hash partition)
df.repartition(col("date"))                  # partition by column

# Coalesce — no shuffle, combines existing partitions (reduce only)
df.coalesce(10)   # from 200 → 10 partitions (safe, fast)

# When to use:
# repartition: increase partitions, better balance, after filter
# coalesce: decrease partitions before writing (avoid small files)

# Default parallelism: spark.default.parallelism = 2 × num CPU cores
# Default shuffle partitions: spark.sql.shuffle.partitions = 200 (tune this!)
spark.conf.set("spark.sql.shuffle.partitions", "50")  # for smaller datasets
```

> **💡 Interview tip:** "What's the difference between `repartition()` and `coalesce()`?" — `repartition()` performs a full shuffle to redistribute data evenly across N partitions — use it when you need to increase partitions or re-balance skewed data. `coalesce()` merges existing partitions without shuffling by having tasks read from multiple partitions locally — use it to reduce the partition count before writing (fewer output files). The caveat: coalescing too aggressively concentrates data onto fewer executors and can create data skew downstream.

### Broadcast Joins

Broadcast join is the single most impactful performance optimization for fact-dimension joins. The concept: instead of shuffling both the large fact table and the small dimension table across the network (sort-merge join), send a full copy of the small table to every executor. Each executor can then perform the join locally, in memory, without any network communication. Zero shuffle.

For a join between a 500GB fact table and a 10MB dimension table, a sort-merge join shuffles and sorts 500GB. A broadcast join sends 10MB to each executor and processes 500GB locally. The difference is enormous.

```python
from pyspark.sql.functions import broadcast

# Large table join small table → broadcast the small one
# Sends full small table to each executor → no shuffle needed

# Explicit broadcast hint
df_large.join(broadcast(df_small), "customer_id")

# Auto-broadcast threshold (if table < threshold, auto-broadcast)
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "100MB")

# When to use:
# One table is small (< 100-200MB)
# Eliminates shuffle for the join (big performance win)
```

### Join Strategies

Understanding join strategy selection — and knowing when to override it — separates senior Spark engineers from those who just write code and hope it's fast.

```
Broadcast join:  small table → broadcast to all nodes, no shuffle
                 Best for: fact + small dimension

Sort-merge join: both tables sorted and merged
                 Default for large-large joins
                 Requires shuffle

Shuffle hash:    build hash map of smaller side, probe with larger
                 Memory-intensive
                 Used when one side is medium-sized
```

> **🌍 Real world:** AQE (Adaptive Query Execution) can dynamically switch from sort-merge to broadcast join at runtime if it discovers one side is smaller than expected. This is why enabling AQE is a free performance win for most jobs — Spark's compile-time estimates of table sizes are often wrong (especially after filters), but AQE measures the actual sizes and re-optimizes.

### Caching and Persistence

Cache only when a DataFrame is used more than once in the same job. Caching a DataFrame that's only used once wastes memory and can cause other DataFrames to spill to disk. The rule: if you're going to compute the same expensive transformation (complex join + aggregation) more than once, cache it between those uses and unpersist it when done.

Think of it like saving a complex spreadsheet formula result to a cell — you only bother saving it if you're going to reference it multiple times. Computing it fresh each time is wasteful; saving it when you'll only reference it once wastes cell space.

```python
from pyspark.storagelevel import StorageLevel

# Cache in memory (deserialized)
df.cache()   # = df.persist(StorageLevel.MEMORY_AND_DISK)

# Explicit storage levels
df.persist(StorageLevel.MEMORY_ONLY)        # evict if not enough memory
df.persist(StorageLevel.MEMORY_AND_DISK)    # spill to disk
df.persist(StorageLevel.DISK_ONLY)          # disk only
df.persist(StorageLevel.MEMORY_ONLY_2)      # 2 replicas in memory

# Unpersist when done
df.unpersist()

# When to cache:
# - DataFrame used multiple times in the same job
# - Expensive to recompute (complex joins, aggregations)
# - Iterative algorithms
# DON'T cache if used only once — wastes memory
```

> **💡 Interview tip:** "When would you cache a DataFrame and when wouldn't you?" — Cache when: (1) a DataFrame is used in 2+ actions in the same job, (2) it's expensive to recompute (multi-table join, complex aggregation), and (3) it fits (or nearly fits) in available executor memory. Don't cache when: (1) it's used only once, (2) it's too large for memory and disk spill would slow things down, (3) the computation is cheap (simple filter/select). Forgetting to `unpersist()` is a real memory leak in long-running Spark applications.

### Data Skew

Data skew is the silent performance killer in production Spark pipelines. When one key appears disproportionately often (imagine a retailer where one mega-customer has 30% of all orders), all rows for that key must land on one executor partition. That executor runs 10x longer than the others while every other executor sits idle waiting for it. Your job's completion time is determined by the slowest task.

The salting technique artificially distributes a skewed key across multiple partitions by appending a random number (the "salt"). You then explode the small/dimension table to have one row per possible salt value, creating matching salted keys. The skewed key is now split across N partitions — each runs in 1/N the time.

```
Problem: one partition has much more data than others (e.g. one customer
has 50% of all orders) → one task takes 10x longer than others → whole job waits

Detecting skew:
- Spark UI: one task in a stage takes much longer than others
- df.groupBy("key").count().orderBy(desc("count")).show()

Solutions:
1. Salting (add random prefix to skewed key):
   from pyspark.sql.functions import concat, lit, ceil, rand
   
   # Add salt to fact table
   df_orders = df_orders.withColumn(
       "salted_key",
       concat(col("customer_id"), lit("_"), (rand() * 10).cast("int"))
   )
   
   # Explode small table with matching salts
   df_cust = df_customers.withColumn("salt", explode(array([lit(i) for i in range(10)])))
   df_cust = df_cust.withColumn("salted_key", concat(col("customer_id"), lit("_"), col("salt")))
   
   # Join on salted key
   df_orders.join(df_cust, "salted_key")

2. Skew hint (Spark 3.0+):
   df.join(df2.hint("skew", "customer_id"), "customer_id")

3. AQE (Adaptive Query Execution, Spark 3.0+):
   spark.conf.set("spark.sql.adaptive.enabled", "true")
   spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
   # AQE detects and splits skewed partitions automatically
```

> **💡 Interview tip:** "You have a Spark job where one stage takes 10x longer than expected. How do you diagnose and fix it?" — Open the Spark UI, go to the Stages tab, look at the task duration distribution. If most tasks complete in 10 seconds but 1-2 take 100+ seconds, you have skew. Confirm with `df.groupBy("join_key").count().orderBy(desc("count")).show()`. Then apply salting or enable AQE's skew join handling. Also check for NULL key values — NULLs in a join key all go to the same partition and are a common skew culprit.

> **🌍 Real world:** Skew is especially common in B2B datasets where one customer dwarfs all others. In a SaaS analytics platform, the largest enterprise customer might generate 1000x more events than the median customer. Always check your data distribution before writing joins against high-skew tables — it will save you from mysterious slow jobs in production.

### Predicate Pushdown and Column Pruning

These two optimizations happen automatically when using DataFrames with Parquet/ORC — they're Catalyst's gift to you. The key is to write code that allows them to happen: don't wrap column names in Python functions or apply transformations before filters that prevent the optimizer from pushing them down.

```
Predicate pushdown:
- Push WHERE filters down to the data source
- Parquet row group statistics used to skip groups
- Don't read data that doesn't match filter

Column pruning:
- Only read columns that are actually used
- Columnar formats (Parquet/ORC) support this natively
- SELECT a, b FROM ... → only reads columns a and b from Parquet

Both happen automatically when using DataFrames with Parquet/ORC.
Verify with: df.explain(True)  # shows physical plan
```

### Adaptive Query Execution (AQE)

AQE is Spark's self-healing optimization mechanism, introduced in Spark 3.0. Think of it like GPS re-routing: static query planning is like planning a route before you leave (based on estimated traffic). AQE is like GPS that monitors actual traffic and re-routes mid-journey. When Spark's initial estimates of partition sizes or data distributions are wrong (which is often), AQE re-optimizes the physical plan using actual runtime statistics rather than stale catalog estimates.

Three AQE features matter most: (1) dynamic coalescing of shuffle partitions eliminates the problem of too many tiny post-shuffle partitions, (2) dynamic join strategy switching can convert a sort-merge join to a broadcast join if one side turns out to be smaller than estimated, (3) skew join handling automatically splits large skewed partitions into smaller ones.

Enable it. It's free performance.

```python
# Spark 3.0+ — re-optimizes query at runtime based on actual data stats
spark.conf.set("spark.sql.adaptive.enabled", "true")

# Features:
# - Dynamically coalesces shuffle partitions (avoids too many small partitions)
# - Dynamically switches join strategies (if runtime stats differ from estimates)
# - Handles skew joins automatically
```

> **💡 Interview tip:** "What is AQE and why would you enable it?" — AQE re-optimizes query execution plans at runtime using actual shuffle partition sizes, rather than relying on statistics estimated at planning time. In practice it (1) reduces the number of shuffle partitions dynamically when post-shuffle data is small, (2) converts sort-merge joins to broadcast joins if a side shrinks due to filters, and (3) splits skewed partitions. The only reason NOT to enable it is if you're on Spark < 3.0.

---

## 10. Spark UI

The Spark UI is your primary debugging tool for performance problems. Every Spark job emits rich telemetry — learning to read it is what separates engineers who say "the job is slow" from engineers who say "stage 3, task 47 is skewed — the `customer_id` join key on partition 12 has 2 million rows vs. 50K average."

```
Access: http://driver:4040 (local) or cluster's Spark UI

Key tabs:
Jobs     — top-level actions and their completion status
Stages   — stages within each job, task-level metrics
Tasks    — per-task breakdown (duration, shuffle read/write, gc time)
Storage  — cached DataFrames and memory usage
SQL      — query execution plans and metrics
Executors — per-executor memory, CPU, task counts

What to look for:
- Long tasks → data skew
- Large shuffle read/write → too many wide transformations
- Spills to disk → not enough memory (reduce partitions or add memory)
- GC time > 20% of task time → memory pressure
- Many small files → increase partition size before reading
```

> **🌍 Real world:** In production Spark on Glue/EMR, you won't have real-time Spark UI access. Instead, use CloudWatch metrics (Glue job metrics) and the Glue job run logs. For post-mortem analysis, enable Spark history server on EMR, which persists event logs to S3 and lets you view the Spark UI after job completion. This is essential for debugging jobs that ran overnight and are no longer active.

---

## 11. PySpark with AWS Glue

Glue's PySpark API adds a thin layer of managed transforms on top of standard PySpark. The key value-add is `resolveChoice()` and `relationalize()` for schema normalization, and the managed write path to S3 with automatic partition registration in the Glue Catalog.

```python
# Glue-specific patterns
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.transforms import ApplyMapping, ResolveChoice, DropNullFields

# resolveChoice — handle type conflicts in source data
# "make_struct": keep both types as struct
# "cast:string": cast everything to string
# "project:string": keep only string version
resolved = ResolveChoice.apply(
    frame=datasource,
    choice="make_cols",
    transformation_ctx="resolved"
)

# applyMapping — rename, reorder, cast columns
mapped = ApplyMapping.apply(
    frame=datasource,
    mappings=[
        ("old_name", "string", "new_name", "string"),
        ("amount_str", "string", "amount", "double"),
    ]
)

# relationalize — flatten nested/array structures
flattened = datasource.relationalize("root", "/tmp/")

# DropNullFields — remove fields where all values are null
clean = DropNullFields.apply(frame=datasource)

# Working with S3 paths in Glue
glueContext.write_dynamic_frame.from_options(
    frame=output_df,
    connection_type="s3",
    connection_options={
        "path": "s3://bucket/output/",
        "partitionKeys": ["year", "month", "day"]
    },
    format="glueparquet",
    format_options={"compression": "snappy"}
)
```

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Driver | Orchestrates job — builds DAG, schedules tasks |
| Executor | Does the actual work — runs tasks on partitions |
| Lazy evaluation | Transformations build a plan, actions execute it |
| Shuffle | Redistribute data across partitions — expensive! |
| Broadcast join | Send small table to all nodes — eliminates shuffle |
| Repartition | Full shuffle — use to increase/rebalance partitions |
| Coalesce | No shuffle — use to reduce partitions before write |
| Cache | Store DataFrame in memory for reuse in same job |
| Data skew | One partition much larger — use salting or AQE |
| UDF | Custom function — slow (Python overhead), prefer built-ins |
| Pandas UDF | Vectorized UDF — much faster than regular UDF |
| AQE | Auto-optimizes at runtime (Spark 3.0+) — enable it |
| Predicate pushdown | Filter at source — skip row groups in Parquet |
