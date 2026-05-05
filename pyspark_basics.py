# ============================================================
# PySpark Basics — Data Engineering Learning
# ============================================================
# Install: pip3 install pyspark
# Run:     python3 pyspark_basics.py
# ============================================================

from pyspark.sql import SparkSession
from pyspark.sql import Window
from pyspark.sql.functions import (
    col, count, sum, avg, max, min, when, upper,
    # string
    trim, lower, regexp_replace, split, concat_ws, lit,
    # date / time
    current_date, date_add, datediff, to_date, year, month, dayofweek,
    # null handling
    coalesce, isnan, isnull,
    # array / struct
    explode, array, struct,
    # window
    rank, dense_rank, row_number, lag, lead, ntile,
    # misc
    broadcast, udf, monotonically_increasing_id,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType,
    ArrayType, DateType, LongType,
)

# ── 1. Create a Spark Session ─────────────────────────────────
# SparkSession is the entry point to everything in PySpark.
# In a real cluster, this connects to the cluster — locally it runs on your machine.
spark = SparkSession.builder \
    .appName("PySpark Basics") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")  # suppress noisy INFO logs
print("Spark version:", spark.version)


# ── 2. Create a DataFrame from Python data ────────────────────
# A DataFrame is a distributed table — like a pandas DataFrame but runs on a cluster.
data = [
    ("Alice",   "Engineering", 95000, "New York"),
    ("Bob",     "Marketing",   72000, "Chicago"),
    ("Carol",   "Engineering", 105000, "New York"),
    ("David",   "HR",          65000, "Chicago"),
    ("Eve",     "Engineering", 115000, "San Francisco"),
    ("Frank",   "Marketing",   80000, "New York"),
    ("Grace",   "HR",          68000, "San Francisco"),
    ("Henry",   "Engineering", 98000, "Chicago"),
]

schema = StructType([
    StructField("name",       StringType(),  nullable=False),
    StructField("department", StringType(),  nullable=False),
    StructField("salary",     IntegerType(), nullable=False),
    StructField("city",       StringType(),  nullable=False),
])

df = spark.createDataFrame(data, schema=schema)

print("\n=== Raw DataFrame ===")
df.show()
df.printSchema()


# ── 3. Basic transformations ──────────────────────────────────
# select — pick columns (like SQL SELECT)
print("=== Select columns ===")
df.select("name", "salary").show()

# filter — rows matching a condition (like SQL WHERE)
print("=== Engineers only ===")
df.filter(col("department") == "Engineering").show()

# withColumn — add or replace a column
print("=== Add salary_usd_k column ===")
df_with_k = df.withColumn("salary_k", col("salary") / 1000)
df_with_k.show()

# orderBy — sort rows (like SQL ORDER BY)
print("=== Top earners ===")
df.orderBy(col("salary").desc()).show(5)


# ── 4. Aggregations ───────────────────────────────────────────
# groupBy + agg — like SQL GROUP BY
print("=== Department summary ===")
df.groupBy("department").agg(
    count("name").alias("headcount"),
    avg("salary").alias("avg_salary"),
    max("salary").alias("max_salary"),
    min("salary").alias("min_salary"),
).orderBy("avg_salary", ascending=False).show()


# ── 5. Conditional column (like SQL CASE WHEN) ────────────────
print("=== Salary band ===")
df.withColumn(
    "salary_band",
    when(col("salary") >= 100000, "Senior")
    .when(col("salary") >= 80000,  "Mid")
    .otherwise("Junior")
).select("name", "salary", "salary_band").show()


# ── 6. SQL on a DataFrame ─────────────────────────────────────
# Register as a temp view and run plain SQL — great for analysts
df.createOrReplaceTempView("employees")

print("=== SQL: avg salary by city ===")
spark.sql("""
    SELECT city,
           COUNT(*)        AS headcount,
           AVG(salary)     AS avg_salary
    FROM   employees
    GROUP  BY city
    ORDER  BY avg_salary DESC
""").show()


# ── 7. Read & Write CSV ───────────────────────────────────────
# Save to CSV
df.write.mode("overwrite").option("header", True).csv("/tmp/employees_out")
print("Written to /tmp/employees_out/")

# Read it back
df_read = spark.read.option("header", True).option("inferSchema", True).csv("/tmp/employees_out")
print("=== Read back from CSV ===")
df_read.show()


# ── 8. Partitioning — key concept for big data ────────────────
# Partition by department — each partition becomes a separate folder/file on disk.
# In production this dramatically speeds up queries that filter on the partition column.
df.write.mode("overwrite").partitionBy("department").parquet("/tmp/employees_partitioned")
print("Written partitioned parquet to /tmp/employees_partitioned/")

# Reading a partitioned dataset — Spark only reads the relevant partition folder
df_eng = spark.read.parquet("/tmp/employees_partitioned/department=Engineering")
print("=== Engineering partition ===")
df_eng.show()


# ── 9. Key differences from pandas ───────────────────────────
print("""
Key PySpark vs pandas differences
──────────────────────────────────
pandas                  PySpark
──────────────────────────────────
df["col"]               col("col") or df["col"]
df[df.x > 5]            df.filter(col("x") > 5)
df.groupby().mean()     df.groupBy().agg(avg(...))
df.merge()              df.join()
runs on 1 machine       runs on a cluster
eager (instant result)  lazy (executes on .show()/.collect())
""")


# ── 10. Joins ─────────────────────────────────────────────────
# Build a small lookup table (department → cost_center)
dept_data = [
    ("Engineering", "CC-100"),
    ("Marketing",   "CC-200"),
    ("HR",          "CC-300"),
]
dept_schema = StructType([
    StructField("department",  StringType(), nullable=False),
    StructField("cost_center", StringType(), nullable=False),
])
df_dept = spark.createDataFrame(dept_data, schema=dept_schema)

# Inner join — only rows that match on both sides
print("=== Inner join: employees + cost_center ===")
df.join(df_dept, on="department", how="inner").show()

# Left join — keep all employees even if dept is missing from lookup
print("=== Left join ===")
df.join(df_dept, on="department", how="left").show()

# Anti join — employees whose department has NO entry in the lookup
print("=== Anti join: employees with unmapped department ===")
df.join(df_dept, on="department", how="left_anti").show()

# Broadcast join — hint Spark to replicate the small table to every executor,
# avoiding a costly shuffle when one side is small (< a few hundred MB).
print("=== Broadcast join ===")
df.join(broadcast(df_dept), on="department").show()


# ── 11. String transformations (ETL cleaning) ─────────────────
messy_data = [
    ("  Alice  ", "eng|python|sql"),
    ("BOB",       "mkt|excel"),
    ("Carol ",    "eng|java|spark"),
]
df_messy = spark.createDataFrame(messy_data, ["name", "skills_raw"])

print("=== String cleaning ===")
df_messy.withColumn("name_clean", trim(lower(col("name")))) \
        .withColumn("name_upper", upper(trim(col("name")))) \
        .withColumn("skills_array", split(col("skills_raw"), "\\|")) \
        .withColumn("skills_csv",   regexp_replace(col("skills_raw"), "\\|", ", ")) \
        .withColumn("label",        concat_ws(" — ", lit("employee"), trim(col("name")))) \
        .show(truncate=False)


# ── 12. Null handling ─────────────────────────────────────────
null_data = [
    ("Alice", 95000,  "New York"),
    ("Bob",   None,   "Chicago"),
    ("Carol", 105000, None),
    ("David", None,   None),
]
df_null = spark.createDataFrame(null_data, ["name", "salary", "city"])

print("=== Rows with any null ===")
df_null.filter(isnull(col("salary")) | isnull(col("city"))).show()

print("=== Drop rows with any null ===")
df_null.dropna().show()

print("=== Fill nulls with defaults ===")
df_null.fillna({"salary": 0, "city": "Unknown"}).show()

# coalesce picks the first non-null value across columns
print("=== coalesce: salary or fallback 50000 ===")
df_null.withColumn("salary_safe", coalesce(col("salary"), lit(50000))).show()


# ── 13. Date & time functions ─────────────────────────────────
events_data = [
    ("Alice", "2024-01-15"),
    ("Bob",   "2024-03-22"),
    ("Carol", "2023-11-01"),
]
df_events = spark.createDataFrame(events_data, ["name", "hire_date_str"])

print("=== Date operations ===")
df_events \
    .withColumn("hire_date",   to_date(col("hire_date_str"), "yyyy-MM-dd")) \
    .withColumn("today",       current_date()) \
    .withColumn("days_tenure", datediff(current_date(), to_date(col("hire_date_str"), "yyyy-MM-dd"))) \
    .withColumn("review_due",  date_add(to_date(col("hire_date_str"), "yyyy-MM-dd"), 90)) \
    .withColumn("hire_year",   year(to_date(col("hire_date_str"), "yyyy-MM-dd"))) \
    .withColumn("hire_month",  month(to_date(col("hire_date_str"), "yyyy-MM-dd"))) \
    .withColumn("day_of_week", dayofweek(to_date(col("hire_date_str"), "yyyy-MM-dd"))) \
    .drop("hire_date_str") \
    .show()


# ── 14. Window functions ──────────────────────────────────────
# Window functions compute over a group without collapsing rows — like SQL OVER().
# Essential for ranking, running totals, and lag/lead comparisons.

w_dept    = Window.partitionBy("department").orderBy(col("salary").desc())
w_dept_all = Window.partitionBy("department")

print("=== Window: rank, dense_rank, row_number, ntile ===")
df.withColumn("rank",        rank()       .over(w_dept)) \
  .withColumn("dense_rank",  dense_rank() .over(w_dept)) \
  .withColumn("row_number",  row_number() .over(w_dept)) \
  .withColumn("quartile",    ntile(4)     .over(w_dept)) \
  .show()

print("=== Window: running total salary per department ===")
w_running = Window.partitionBy("department").orderBy("salary").rowsBetween(Window.unboundedPreceding, Window.currentRow)
df.withColumn("running_salary_total", sum("salary").over(w_running)).show()

print("=== Window: lag / lead — compare to previous/next row ===")
w_ordered = Window.partitionBy("department").orderBy("salary")
df.withColumn("prev_salary", lag("salary",  1).over(w_ordered)) \
  .withColumn("next_salary", lead("salary", 1).over(w_ordered)) \
  .withColumn("diff_from_prev", col("salary") - lag("salary", 1).over(w_ordered)) \
  .show()

# Dedup: keep highest-paid per department (common ETL dedup pattern)
print("=== Dedup: top earner per department ===")
df.withColumn("rn", row_number().over(w_dept)) \
  .filter(col("rn") == 1) \
  .drop("rn") \
  .show()


# ── 15. Explode — flatten arrays / semi-structured data ───────
# In DE you often receive JSON with nested arrays; explode() turns each
# element into its own row so you can query it like a normal column.
skills_data = [
    ("Alice", ["python", "sql", "spark"]),
    ("Bob",   ["excel", "sql"]),
    ("Carol", ["java", "spark", "kafka"]),
]
df_skills = spark.createDataFrame(skills_data, ["name", "skills"])

print("=== Explode array column ===")
df_skills.withColumn("skill", explode(col("skills"))).select("name", "skill").show()

# Reverse: collect individual skills back into an array (GROUP BY + collect_list)
from pyspark.sql.functions import collect_list, collect_set
print("=== collect_list / collect_set ===")
df_skills.withColumn("skill", explode(col("skills"))) \
         .groupBy("name") \
         .agg(
             collect_list("skill").alias("skills_list"),
             collect_set("skill").alias("skills_set"),
         ).show(truncate=False)


# ── 16. UDF — User-Defined Function ──────────────────────────
# Use only when built-in functions can't do the job — UDFs break Spark's
# Catalyst optimizer and are slower than native functions.
def salary_grade(salary):
    if salary is None:
        return "Unknown"
    if salary >= 100000:
        return "L5"
    if salary >= 80000:
        return "L4"
    return "L3"

salary_grade_udf = udf(salary_grade, StringType())

print("=== UDF: salary grade ===")
df.withColumn("grade", salary_grade_udf(col("salary"))).show()


# ── 17. Caching ───────────────────────────────────────────────
# cache() / persist() materializes a DataFrame in memory so repeated
# actions (show, count, joins) don't re-execute the full lineage.
# Always unpersist when done to free executor memory.
df_cached = df.filter(col("department") == "Engineering").cache()
print("=== Cached Engineering DataFrame (count triggers materialization) ===")
print("Row count:", df_cached.count())   # first action — fills the cache
df_cached.show()                          # reads from cache, not disk
df_cached.unpersist()


# ── 18. Repartition vs Coalesce ──────────────────────────────
# repartition(n)  — full shuffle, use to INCREASE or evenly redistribute partitions
# coalesce(n)     — no shuffle, use to DECREASE partitions before writing (avoids tiny files)
print("Default partitions:", df.rdd.getNumPartitions())

df_rep = df.repartition(4)
print("After repartition(4):", df_rep.rdd.getNumPartitions())

df_coal = df_rep.coalesce(2)
print("After coalesce(2):", df_coal.rdd.getNumPartitions())

# Repartition by column — co-locates rows with the same key on the same partition,
# which makes subsequent joins / aggregations on that key shuffle-free.
df_by_dept = df.repartition(4, "department")
print("Repartitioned by department:", df_by_dept.rdd.getNumPartitions())


# ── 19. Surrogate keys & monotonically_increasing_id ─────────
# Generates a unique 64-bit integer per row across all partitions.
# Not sequential — gaps exist between partitions — but guaranteed unique.
print("=== Surrogate keys ===")
df.withColumn("surrogate_key", monotonically_increasing_id()).show()


# ── 20. Set operations, dedup, and sampling ───────────────────
print("=== Union / distinct / dropDuplicates ===")
more_data = [
    ("Isaac", "Engineering", 92000, "Boston"),
    ("Jack",  "Engineering", 92000, "Boston"),
]
df_more = spark.createDataFrame(more_data, schema=schema)

unioned = df.unionByName(df_more)
unioned.show()

print("=== Distinct rows ===")
unioned.select("department").distinct().show()

print("=== Drop duplicate names ===")
unioned.dropDuplicates(["name"]).show()

print("=== Sample 50% of data ===")
unioned.sample(fraction=0.5, seed=42).show()


# ── 21. RDD basics ───────────────────────────────────────────
# RDDs are the lower-level Spark API. DataFrames are built on top of them.
rdd = spark.sparkContext.parallelize([1, 2, 3, 4, 5, 6])
print("=== RDD map/filter/reduce ===")
print("Squares > 10:", rdd.map(lambda x: x * x).filter(lambda x: x > 10).collect())

pairs = spark.sparkContext.parallelize([("a", 1), ("b", 2), ("a", 3)])
print("=== RDD reduceByKey ===")
print(pairs.reduceByKey(lambda x, y: x + y).collect())


# ── 22. JSON read/write and data source formats ──────────────
print("=== Read JSON from strings ===")
json_data = [
    '{"name":"Ivy","department":"Finance","salary":90000,"city":"Boston"}',
    '{"name":"Jack","department":"HR","salary":72000,"city":"Chicago"}',
]
df_json = spark.read.json(spark.sparkContext.parallelize(json_data))
df_json.show()

json_out = "/tmp/employees_json_out"
df_json.write.mode("overwrite").json(json_out)
print(f"Written JSON to {json_out}/")

read_back_json = spark.read.json(json_out)
print("=== Read back JSON ===")
read_back_json.show()


# ── 23. Broadcast variables and accumulators ────────────────
print("=== Broadcast variable example ===")
lookup = {"Engineering": 1.1, "Marketing": 1.0, "HR": 0.9}
lookup_broadcast = spark.sparkContext.broadcast(lookup)

df.withColumn(
    "dept_multiplier",
    lit(lookup_broadcast.value.get("department", 1.0))
).show()

print("=== Accumulator example ===")
acc = spark.sparkContext.longAccumulator("salaryAbove100k")

def count_high_salary(row):
    if row.salary >= 100000:
        acc.add(1)
    return row

# Use a simple RDD action to illustrate accumulator updates.
df.rdd.map(count_high_salary).count()
print("High salary rows count:", acc.value)


# ── 24. Query plan and optimization hints ─────────────────────
print("=== Explain plan ===")
df.explain(True)

print("=== Coalesce vs repartition hint ===")
print("repartition() partitions:", df.repartition(4).rdd.getNumPartitions())
print("coalesce() partitions:", df.repartition(4).coalesce(2).rdd.getNumPartitions())

spark.conf.set("spark.sql.shuffle.partitions", "2")
print("spark.sql.shuffle.partitions set to", spark.conf.get("spark.sql.shuffle.partitions"))


# ── 25. Spark catalog and temp views ─────────────────────────
print("=== Spark catalog tables ===")
print([t.name for t in spark.catalog.listTables()])

print("=== Describe DataFrame ===")
df.describe().show()


# ── 26. Quick reference cheat-sheet ──────────────────────────
print("""
DE PySpark cheat-sheet
══════════════════════════════════════════════════════════════════
Pattern                          When to use
──────────────────────────────────────────────────────────────────
broadcast(small_df)              Join where one side fits in memory
cache() / unpersist()            Reuse a DataFrame in multiple actions
repartition(n, "col")            Before a heavy join/agg on a key
coalesce(n)                      Reduce file count before writing
row_number().over(window)        Dedup: keep 1 row per group
lag/lead                         Compare row to previous/next (SCD, deltas)
explode()                        Flatten arrays from JSON/semi-structured
fillna / coalesce(col, lit(x))   Null-safe ETL defaults
to_date / datediff               Event time, tenure, SLA calculations
udf()                            Last resort — prefer built-in functions
explain(True)                    Inspect Spark's physical plan
longAccumulator                  Track counters during RDD actions
broadcast(var)                   Share driver values across executors
spark.sql.shuffle.partitions     Tune shuffle parallelism
══════════════════════════════════════════════════════════════════
""")

spark.stop()
