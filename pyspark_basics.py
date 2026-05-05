# ============================================================
# PySpark Basics — Data Engineering Learning
# ============================================================
# Install: pip3 install pyspark
# Run:     python3 pyspark_basics.py
# ============================================================

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum, avg, max, min, when, upper
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

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

spark.stop()
