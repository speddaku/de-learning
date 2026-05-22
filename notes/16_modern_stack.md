# Modern Data Stack & Emerging Technologies — Complete Notes from Scratch

---

## 1. Delta Lake

### What It Is

The fundamental problem Delta Lake solves is that S3 is a glorified file system — it has no concept of transactions, consistency, or atomicity. If your Spark job writes 100 Parquet files and crashes after 50, you now have a half-written table with no way to know which files are valid. If two jobs write simultaneously, you get file overlap. If you need to delete a row (for GDPR compliance), you have to rewrite the entire Parquet file. Delta Lake adds a transactional layer on top of S3 Parquet files using a `_delta_log` directory that records every change as a JSON transaction entry — turning a "bag of files" into an ACID-compliant table.

Think of Delta Lake like Git for your data files: every change is a commit recorded in the transaction log, you can see the full history, roll back to any version, and multiple writers are coordinated via optimistic concurrency control.

```
Delta Lake: open-source storage layer on top of Parquet files in S3/ADLS/GCS
- Adds ACID transactions to data lakes
- Enables: upserts, deletes, schema enforcement, time travel
- Full compatibility with Spark, Databricks, Athena (read), Hive

Problem it solves:
- Plain S3 + Parquet: no ACID → partial writes, no updates, no rollback
- Delta Lake: transactional _delta_log directory tracks all changes

Delta table structure:
s3://bucket/my_table/
  _delta_log/
    00000000000000000000.json   ← transaction 0 (create table)
    00000000000000000001.json   ← transaction 1 (insert)
    00000000000000000002.json   ← transaction 2 (update)
  part-00000.parquet
  part-00001.parquet
```

> **💡 Interview tip:** "How does Delta Lake time travel work?" — every transaction writes a new JSON entry to `_delta_log` listing which Parquet files were added and which were removed. To query version N, Delta reads the log up to entry N and builds the list of valid files at that point. The actual Parquet files are never deleted until `VACUUM` removes them. This is why you can query "the table as it was last Tuesday" without any special backup infrastructure.

> **🌍 Real world:** The `_delta_log` directory is the single most important thing to understand about Delta Lake. It's what enables ACID (the log is the transaction record), time travel (log is the version history), schema enforcement (schema is recorded in log metadata), and efficient streaming reads (Spark Streaming reads only new log entries since its last checkpoint). If you understand the transaction log, you understand Delta Lake.

### Core Operations

Delta Lake's MERGE operation is the workhorse of modern data warehouse patterns — it's how you implement SCD Type 1 upserts, apply CDC changes from Debezium/Kafka, and handle late-arriving data corrections. Unlike a full overwrite, MERGE only touches the rows that actually changed.

```python
from delta.tables import DeltaTable
from pyspark.sql.functions import col

# Create/write Delta table
df.write.format("delta").mode("overwrite").save("s3://bucket/sales/")

# Or with partitioning
df.write \
  .format("delta") \
  .mode("overwrite") \
  .partitionBy("year", "month") \
  .save("s3://bucket/sales/")

# Read
df = spark.read.format("delta").load("s3://bucket/sales/")

# Upsert (MERGE) — SCD Type 1
delta_table = DeltaTable.forPath(spark, "s3://bucket/sales/")

delta_table.alias("target").merge(
    updates_df.alias("source"),
    "target.order_id = source.order_id"
).whenMatchedUpdateAll() \
 .whenNotMatchedInsertAll() \
 .execute()

# Delete
delta_table.delete(col("status") == "cancelled")

# Update
delta_table.update(
    condition=col("status") == "pending",
    set={"status": lit("confirmed"), "updated_at": lit("2025-05-21")}
)
```

> **🌍 Real world:** The MERGE pattern is central to CDC pipelines. A Debezium connector streams row-level changes (insert/update/delete) from Postgres to Kafka. A Spark Structured Streaming job reads these change events and applies them as a MERGE to the Delta table — producing a real-time replica of the source database in the data lake. This is the "streaming lakehouse" pattern used by companies like Uber and LinkedIn.

### Time Travel

Time travel is Delta Lake's "undo" button and audit capability. You can query any historical version of a table, restore it, or compare the current state to a previous state. This is invaluable for debugging "why did this metric change?" and for GDPR compliance ("show me what data we had about this user on this date").

```python
# Query historical version
df = spark.read.format("delta").option("versionAsOf", 5).load("s3://bucket/sales/")
df = spark.read.format("delta").option("timestampAsOf", "2025-05-01").load("s3://bucket/sales/")

# Restore to previous version
delta_table.restoreToVersion(5)
delta_table.restoreToTimestamp("2025-05-01 00:00:00")

# View history
delta_table.history().show(truncate=False)

# Vacuum — delete old files not referenced by recent versions
delta_table.vacuum(retentionHours=168)  # default 7 days
```

> **💡 Interview tip:** `VACUUM` is a gotcha — it permanently deletes old Parquet files that are no longer referenced by recent transactions, which truncates your time travel history. The default retention is 7 days. If you `VACUUM` with a shorter retention (or the non-recommended `VACUUM table RETAIN 0 HOURS`), you lose the ability to time-travel beyond that point. Never vacuum below 7 days unless you're certain you don't need older history.

### Schema Evolution

One of the most painful problems in traditional data lakes is schema changes: a source system adds a column and your downstream Parquet files suddenly have a mismatch. Delta Lake's `mergeSchema` option automatically handles additive changes (new columns) so new data integrates without manual schema migration.

```python
# Auto merge schema on write
df.write \
  .format("delta") \
  .option("mergeSchema", "true") \  # add new columns automatically
  .mode("append") \
  .save("s3://bucket/sales/")

# Override schema (breaking change)
df.write \
  .format("delta") \
  .option("overwriteSchema", "true") \
  .mode("overwrite") \
  .save("s3://bucket/sales/")
```

### Optimize and Z-Order

Z-ORDER is Delta Lake's equivalent of Snowflake's clustering keys — it physically co-locates rows with similar values for specific columns within the same Parquet files. When you query `WHERE customer_id = 'C001'`, instead of scanning all files, Delta's data skipping statistics tell Spark which files could possibly contain that customer ID, and with Z-ORDER applied, far fewer files need to be scanned.

Without Z-ORDER, related data (all rows for one customer) might be scattered randomly across hundreds of files. With Z-ORDER on `customer_id`, those rows are concentrated in fewer files — meaning a per-customer query reads 5 files instead of 500.

```python
# Optimize — compact small files into larger ones
delta_table.optimize().executeCompaction()

# Z-Order — co-locate related data (improves query performance)
# Like clustering keys in Snowflake
delta_table.optimize().executeZOrderBy("customer_id", "sale_date")

# Auto Optimize (Databricks)
spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")
```

> **💡 Interview tip:** "What is Z-ORDER and when would you use it?" — Z-ORDER reorders rows in Parquet files using a space-filling curve (Z-curve) so that rows with similar values for the specified columns are physically adjacent in the file. This improves data skipping: Delta records the min/max of each column per file; if your query filter is outside a file's min/max range, that file is skipped entirely. Z-ORDER is most effective on high-cardinality columns you frequently filter on (customer_id, order_id, event_date). It's not a free lunch — OPTIMIZE + ZORDER is expensive to run and needs to be scheduled.

---

## 2. Apache Iceberg

### What It Is

Iceberg emerged from Netflix's need to manage petabyte-scale tables with multiple query engines — Spark for heavy transformations, Trino/Presto for interactive queries, Flink for streaming writes. The problem with Delta Lake at that time was tight Databricks/Spark coupling. Iceberg was designed from the start as an open standard — any engine can read and write Iceberg tables using the open spec, with no vendor lock-in.

```
Apache Iceberg: open table format for huge analytic datasets
- Similar to Delta Lake (ACID, time travel, schema evolution)
- Better partition evolution (change partitioning without full rewrite)
- Better hidden partitioning (no need to specify partition in query)
- Supported by: Spark, Flink, Trino, Athena, Hive, Snowflake

Table format structure:
s3://bucket/warehouse/catalog/database/table/
  metadata/
    v1.metadata.json   ← table metadata (schema, partitions, snapshots)
    v2.metadata.json
    snap-xxxx.avro     ← snapshot manifest lists
  data/
    *.parquet          ← actual data files
```

### Hidden Partitioning

Traditional Hive-style partitioning requires query writers to know the partition scheme and explicitly filter on the partition column. If a table is partitioned by `dt=2025-05-21`, a query filtering on a timestamp column won't get partition pruning unless the SQL explicitly includes `dt = '2025-05-21'`. Iceberg's hidden partitioning decouples the physical partition layout from the logical query — you define transform-based partitions (partition by DAY of `event_ts`), and any query filtering on `event_ts` automatically benefits from partition pruning without knowing about the partitioning scheme.

This means you can change the partition scheme (e.g., switch from daily to monthly partitions) without rewriting existing data or breaking existing queries.

```python
# Iceberg feature: partition by transform (not raw column value)
# Query doesn't need to know about partitioning

from pyiceberg.catalog import load_catalog

catalog = load_catalog("glue", type="glue", region_name="us-east-1")

# Create table with hidden partitions
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, TimestampType, DoubleType
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform

schema = Schema(
    NestedField(1, "order_id", StringType()),
    NestedField(2, "event_ts", TimestampType()),
    NestedField(3, "amount", DoubleType()),
)

# Partition by DAY of event_ts — but query just filters on event_ts
spec = PartitionSpec(PartitionField(2, 100, DayTransform(), "event_day"))

table = catalog.create_table("db.orders", schema=schema, partition_spec=spec)

# Query works without specifying partition column:
# SELECT * FROM orders WHERE event_ts BETWEEN '2025-05-01' AND '2025-05-31'
# Iceberg auto-prunes to correct day partitions
```

> **💡 Interview tip:** "What's the difference between Iceberg's hidden partitioning and Hive-style partitioning?" — Hive partitioning stores data in directories named after partition values (`dt=2025-05-21/`), and queries must filter on that exact column name to get pruning. Iceberg applies transform functions (YEAR, MONTH, DAY, HOUR, BUCKET, TRUNCATE) to columns, stores the transformed values in the metadata, and automatically applies pruning for any query filter on the source column. Queries are partition-agnostic — the engine handles it.

### Delta Lake vs Iceberg vs Hudi

The table format wars have largely settled into two dominant camps. Understanding the trade-offs is important for architecture discussions.

```
Delta Lake:
- Best Databricks/Spark integration
- Simpler setup
- Strong Databricks community
- Photon engine (Databricks)
- Use when: primary platform is Databricks

Apache Iceberg:
- Best for multi-engine environments (Spark + Trino + Flink + Athena)
- Better partition evolution
- AWS Athena native support
- Growing adoption in open-source space
- Use when: using AWS Athena heavily, need multi-engine

Apache Hudi (Hadoop Upserts Deletes and Incrementals):
- Best for near-real-time CDC use cases
- Strong AWS EMR integration
- Record-level indexing
- Use when: high-frequency upserts from CDC

Trend: Iceberg winning mindshare in open-source/multi-cloud
       Delta Lake dominant in Databricks ecosystem
```

> **🌍 Real world:** AWS has effectively standardised on Iceberg for its managed services — AWS Glue, Athena, and Lake Formation all have native Iceberg support. If you're building a new data lake on AWS without Databricks, Iceberg is the pragmatic choice. For Databricks shops, Delta Lake + Unity Catalog is the natural fit. The good news: both formats are converging on the same core features, and AWS announced native Delta Lake support in Athena as well.

---

## 3. Modern ELT Stack

The shift from ETL to ELT reflects a fundamental change: cloud data warehouses (Snowflake, BigQuery, Redshift) are powerful enough to do the transformation work. Instead of transforming data before loading it into the warehouse, you load raw data first, then transform it inside the warehouse using SQL. This is faster to build, easier to debug, and preserves the raw data for reprocessing.

```
Source Systems (CRMs, databases, APIs)
        ↓
Ingestion (Fivetran / Airbyte)
        ↓
Cloud Data Warehouse (Snowflake / BigQuery / Redshift)
        ↓
Transformation (dbt)
        ↓
BI Tools (Tableau / Looker / Metabase)
        ↓
Orchestration: Airflow / dbt Cloud / Prefect
```

### Fivetran

Fivetran's value proposition is eliminating the maintenance burden of data connectors. Building and maintaining a Salesforce connector that handles API pagination, rate limits, schema changes, and incremental sync is weeks of engineering work that provides zero business value. Fivetran sells that plumbing so your team focuses on transformation and analysis.

```
- Managed connectors for 300+ SaaS sources (Salesforce, HubSpot, Stripe, etc.)
- Automated schema migration
- Log-based CDC for databases
- Very little setup — connect credentials, choose tables, data flows automatically
- Expensive at scale (priced per monthly active rows)
- Use when: quickly connecting many SaaS sources, low engineering overhead
```

### Airbyte (Open Source Alternative)

Airbyte provides the same functionality as Fivetran but open-source and self-hosted. The trade-off is engineering overhead vs cost savings. At small scale, Fivetran's monthly cost is trivial; at very large scale (hundreds of millions of active rows), Airbyte's self-hosted approach is dramatically cheaper.

```
- Open-source Fivetran alternative
- Self-hosted (free) or Airbyte Cloud (paid)
- 300+ connectors, community-contributed
- More engineering overhead vs Fivetran
- Use when: cost-sensitive, need custom connectors, want control
```

### Reverse ETL

Reverse ETL closes the loop: instead of only moving data from operational systems INTO the warehouse, you move insights from the warehouse BACK into the operational systems your business runs on. The warehouse becomes the master source of truth for business intelligence, feeding back into the CRM, email platform, or ad networks.

```
Move analytics data BACK to operational systems.

Warehouse → Reverse ETL Tool → CRM/Email/Slack/Ad Platforms

Use cases:
- Sync lead scores from warehouse → Salesforce
- Send personalized emails based on warehouse segments
- Update ad audiences based on customer segments

Tools: Census, Hightouch

Pattern: dbt model → Hightouch → Salesforce field update
```

> **🌍 Real world:** Reverse ETL is increasingly important as companies want to operationalise their analytics. A classic example: the data team builds a customer health score model in the warehouse (using dbt); Hightouch syncs that score to Salesforce every hour; the sales team sees live health scores on every account and prioritises outreach accordingly. The data team owns the model logic; the sales team benefits in their existing tool — zero app development needed.

---

## 4. Feature Stores

The problem feature stores solve is subtle but real: ML engineers compute the same features redundantly across teams ("30-day average order value" is built 5 times in 5 different notebooks), and training features are often computed differently from serving features — leading to train/serve skew where a model's production performance is worse than its offline evaluation because the features look slightly different.

A feature store centralises feature definitions, computes them once, and serves the exact same values to both model training and real-time inference.

```
Problem: ML teams build features redundantly.
         Training features computed differently than serving features → skew.

Feature store: central registry for ML features.
- Compute features once, reuse across models
- Same logic for training (batch) and serving (real-time)
- Feature versioning and lineage

Components:
Offline store:  historical feature values (S3, Redshift, Hive)
                Used for training datasets
Online store:   latest feature values (Redis, DynamoDB)
                Used for real-time inference (low latency)

Feature registry: metadata, schema, owner, description

Tools:
- Feast (open source)
- AWS SageMaker Feature Store
- Databricks Feature Store
- Tecton (managed)

Example flow:
1. Define feature: "customer_30d_order_count"
2. Compute offline: Spark job writes to offline store
3. Serve online: streaming job syncs latest values to Redis
4. Training: feature store returns historical values for given timestamp
5. Serving: feature store returns current value from Redis
```

> **💡 Interview tip:** Train/serve skew is a critical concept to mention in ML platform discussions. It happens when the feature computation logic diverges between offline (training) and online (serving) paths — even a small difference (timezone handling, null treatment, rounding) can cause a model to perform significantly worse in production than in evaluation. Feature stores solve this by having a single feature definition that both paths use.

---

## 5. Vector Databases

Traditional databases answer the question "does this row match exactly?" A vector database answers a fundamentally different question: "which rows are most semantically similar to this query?" This is not keyword matching — it's geometric proximity in a high-dimensional embedding space. Two documents that use completely different words but discuss the same concept will have vectors that are close together.

Think of it like a map: instead of "find the house at this exact address" (traditional DB), a vector DB finds "the 5 nearest houses to this location" — but in a 1,536-dimensional mathematical space where "location" encodes meaning.

```
Purpose: store and search high-dimensional vectors (embeddings)
         from ML models (text, images, audio)

Use case: "find documents semantically similar to this query"
          → convert query to vector → find nearest vectors in DB

Vector search types:
ANN (Approximate Nearest Neighbor):
- Faster than exact search
- Small accuracy tradeoff
- Algorithms: HNSW, IVFFlat, LSH

Distance metrics:
- Cosine similarity: angle between vectors (best for text)
- L2 (Euclidean): spatial distance
- Dot product: inner product

Tools:
pgvector:  PostgreSQL extension — good for < 1M vectors
           SELECT * FROM embeddings ORDER BY embedding <-> query_vec LIMIT 5;

Pinecone:  managed, serverless, high scale
Weaviate:  open source, multi-modal
Chroma:    lightweight, local dev
Qdrant:    open source, Rust-based
Milvus:    open source, high performance

When to use pgvector:
- Already using PostgreSQL
- Moderate vector count (< 10M)
- Don't want another service

When to use Pinecone/Weaviate:
- High scale (100M+ vectors)
- Need managed service
- Real-time ingestion
```

> **💡 Interview tip:** ANN (Approximate Nearest Neighbor) algorithms like HNSW (Hierarchical Navigable Small World) are what make vector search fast at scale. Exact nearest-neighbor search requires comparing your query vector to every stored vector — O(n) and slow at millions of vectors. HNSW builds a multi-layer graph where you navigate from a coarse approximation to increasingly precise layers, finding approximate nearest neighbors in O(log n). The tradeoff is a small recall hit (might miss the truly closest vector occasionally) for a massive speed gain.

---

## 6. Embeddings

An embedding is a way of representing anything — a sentence, a product, an image, a customer's purchase history — as a list of floating-point numbers (a vector) that captures its semantic meaning. The magic is that the geometric relationships between vectors encode semantic relationships: "data engineer" and "ETL developer" will have vectors that point in nearly the same direction, while "pizza recipe" will point in a completely different direction.

Embeddings are created by large neural networks (embedding models) trained to place semantically similar things close together in the vector space. This is the foundational technology behind semantic search, RAG systems, and recommendation engines.

```
Embedding: fixed-size vector representation of text/images/audio
           that captures semantic meaning

Text embedding example:
"data engineering"  → [0.12, -0.34, 0.89, ...] (1536 dimensions)
"etl pipeline"      → [0.11, -0.31, 0.85, ...] (similar!)
"pizza recipe"      → [0.93, 0.45, -0.12, ...] (different)

The vectors for semantically similar text are geometrically close.

Models:
text-embedding-3-small (OpenAI): 1536 dims, cheap
text-embedding-3-large (OpenAI): 3072 dims, better quality
all-MiniLM-L6-v2 (HuggingFace): 384 dims, free, fast

Generating with OpenAI:
from openai import OpenAI
client = OpenAI()
response = client.embeddings.create(input="data engineering", model="text-embedding-3-small")
vector = response.data[0].embedding  # list of 1536 floats

Generating locally (free):
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode("data engineering")  # numpy array [384]
```

> **🌍 Real world:** For production RAG systems at scale, the choice of embedding model matters. OpenAI's `text-embedding-3-small` is cheap, fast, and high-quality — good for most use cases. For fully offline/private deployments (financial services, healthcare), local models like `all-MiniLM-L6-v2` (via sentence-transformers) are commonly used. The key constraint: you must use the same embedding model for both ingestion (encoding your documents) and retrieval (encoding user queries) — switching models requires re-embedding the entire corpus.

---

## 7. RAG — Retrieval Augmented Generation

RAG (Retrieval Augmented Generation) is the architecture that makes LLMs useful for enterprise applications. A raw LLM has a knowledge cutoff, can hallucinate, and knows nothing about your business's specific data, policies, or documents. RAG grounds the LLM in your actual data by retrieving relevant context before generating a response. The LLM's job shifts from "know everything" to "reason well given this context."

The analogy: instead of asking a brilliant colleague who might make things up, you hand them the relevant documentation and ask them to answer based on that. The retrieval step ensures the LLM's response is anchored in documents you control and trust.

```
Problem: LLMs have knowledge cutoff, hallucinate, don't know your data.
RAG: augment LLM with relevant context retrieved from your knowledge base.

Flow:
User query
    ↓ embed query → vector
Vector DB (search nearest documents)
    ↓ return relevant chunks
LLM (query + context)
    ↓
Answer grounded in your data

Pipeline:
1. Ingestion:
   - Load documents (PDFs, Confluence pages, Slack messages, code)
   - Split into chunks (512-2048 tokens)
   - Embed each chunk
   - Store embeddings + metadata in vector DB

2. Retrieval:
   - Embed user query
   - Search vector DB for top-k similar chunks
   - (Optionally) re-rank results

3. Generation:
   - Stuff chunks into LLM prompt context
   - LLM answers based on retrieved context

Tools:
- LangChain: framework for building RAG pipelines
- LlamaIndex: data framework for LLMs
- AWS Bedrock Knowledge Bases: managed RAG

Example (LangChain):
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA

# Build vector store from documents
vectorstore = Chroma.from_documents(docs, OpenAIEmbeddings())

# RAG chain
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4o-mini"),
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5})
)
result = qa_chain.invoke("What is our data retention policy?")
```

> **💡 Interview tip:** Common RAG architecture questions: (1) "How do you choose chunk size?" — smaller chunks (256-512 tokens) give more precise retrieval but lose context; larger chunks (1024-2048) retain context but dilute relevance. Typical starting point is 512 tokens with 50-token overlap. (2) "How do you improve retrieval quality?" — re-ranking (use a cross-encoder model to re-score retrieved chunks), hybrid search (combine BM25 keyword search with vector search), HyDE (generate a hypothetical answer, embed it, use it for retrieval). (3) "How do you keep the vector DB in sync with updated documents?" — track document hash/modification time, re-embed changed documents, delete stale embeddings.

> **🌍 Real world:** Internal knowledge bases (documentation Q&A, policy lookup, runbook search) are the most common enterprise RAG use cases. A data engineering team might build a RAG system over their dbt model documentation, Confluence wiki, and Slack history — letting engineers ask "what does the `dim_customers` table mean?" and get an answer grounded in actual documentation rather than an LLM hallucination.

---

## 8. AI-Powered Data Pipelines

LLMs can be integrated directly into data pipelines as smart transformation components — replacing complex hand-written classification logic with a natural-language-instructed model. A Spark UDF wrapping an LLM call can classify, extract, or validate thousands of records per minute in a batch job.

### LLM for Data Quality

```python
# Use LLM to classify/fix messy data
from openai import OpenAI
client = OpenAI()

def classify_customer_intent(description: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"Classify this customer support ticket into one of: [billing, technical, account, other].\nTicket: {description}\nReturn only the category."
        }]
    )
    return response.choices[0].message.content.strip()

# PySpark UDF using LLM (batch processing)
import pandas as pd
from pyspark.sql.functions import pandas_udf

@pandas_udf("string")
def classify_batch(descriptions: pd.Series) -> pd.Series:
    return descriptions.apply(classify_customer_intent)

df.withColumn("intent", classify_batch(col("ticket_text")))
```

> **💡 Interview tip:** Using a Pandas UDF (vectorised UDF) over a regular PySpark UDF is important for LLM-based pipelines. Pandas UDFs process data in Arrow-serialised batches rather than row-by-row, significantly reducing serialisation overhead. More importantly, you can implement batching inside the UDF — grouping multiple rows into a single LLM API call (using the batch completions API) to maximise throughput and reduce cost.

> **🌍 Real world:** LLM-powered data quality is a real use case at scale. Traditional rule-based classifiers for messy free-text (customer feedback, support tickets, product descriptions) are expensive to build and maintain. An LLM with a well-crafted prompt can match hand-tuned classifiers with far less development effort. The economics work when the classification work is high-value (routing support tickets, tagging products for search) and the LLM cost per record is small relative to the manual effort.

### Data Pipeline with LangGraph

```python
# Orchestrate multi-step data processing with LLM agents
from langgraph.graph import StateGraph
from typing import TypedDict

class PipelineState(TypedDict):
    raw_data: list
    validated_data: list
    transformed_data: list
    errors: list

def validate_node(state: PipelineState) -> PipelineState:
    # Use LLM to identify data quality issues
    ...

def transform_node(state: PipelineState) -> PipelineState:
    # Transform validated data
    ...

def route(state: PipelineState):
    if state["errors"]:
        return "handle_errors"
    return "transform"

workflow = StateGraph(PipelineState)
workflow.add_node("validate", validate_node)
workflow.add_node("transform", transform_node)
workflow.add_conditional_edges("validate", route)
```

---

## 9. Prefect vs Airflow

Airflow and Prefect both orchestrate data workflows, but their design philosophies differ significantly. Airflow requires you to think in terms of DAGs — directed acyclic graphs defined at import time, with static structure. Prefect is Python-first: you write a regular Python function, add decorators, and Prefect handles the orchestration. This makes Prefect much easier to work with for dynamic workflows where the number of tasks isn't known until runtime.

```
Airflow:
- Mature (2015), large community
- DAG-based (Python code defines DAG structure)
- Best for: complex dependencies, many integrations, established teams
- Managed: AWS MWAA, Astronomer, Cloud Composer

Prefect:
- Modern Python-first (2019)
- Write regular Python, add @flow and @task decorators
- Dynamic workflows (loop over unknown number of items)
- Better error handling and observability
- Managed: Prefect Cloud

from prefect import flow, task

@task
def extract(date: str):
    return fetch_data(date)

@task
def transform(data):
    return clean_data(data)

@task
def load(data):
    write_to_warehouse(data)

@flow
def etl_pipeline(date: str):
    raw = extract(date)
    clean = transform(raw)
    load(clean)

etl_pipeline("2025-05-21")
```

> **💡 Interview tip:** "Airflow vs Prefect — when would you choose each?" The pragmatic answer: if you're joining a team that already uses Airflow, you'll use Airflow (it's deeply entrenched). For greenfield projects, Prefect's developer experience is meaningfully better — no DAG serialisation constraints, easier local testing (just run the Python file), better retry and caching semantics. Prefect's `@task(cache_key_fn=task_input_hash)` is a genuinely powerful feature: tasks that have already run with the same inputs are skipped, enabling cheap re-runs of failed pipelines.

> **🌍 Real world:** Airflow's dominance comes from its maturity and ecosystem — thousands of operators (KubernetesPodOperator, DbtCloudRunJobOperator, S3ToRedshiftOperator) and a well-understood operational model. In practice, most large DE teams use Airflow for production pipelines and might adopt Prefect or Dagster for new projects where developer velocity matters more than ecosystem breadth.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Delta Lake | ACID + time travel on S3 Parquet — Databricks native |
| _delta_log | Transaction log = every change recorded = time travel possible |
| Z-ORDER | Co-locate related data in fewer files — like Snowflake clustering keys |
| Iceberg | Open table format — multi-engine, hidden partitioning, partition evolution |
| Fivetran | Managed ingestion connectors — quick SaaS integration |
| Airbyte | Open-source Fivetran alternative — more control |
| Reverse ETL | Warehouse → operational systems (Salesforce, email) |
| Feature store | Centralized ML features — consistent train/serve, eliminate skew |
| Vector DB | Store embeddings — semantic similarity search via ANN |
| RAG | LLM + retrieved context — answer grounded in your actual data |
| Embeddings | Dense vector representation — semantically similar = geometrically close |
| Prefect | Modern Python-first orchestration — alternative to Airflow |
| Delta MERGE | Upsert into Delta table — SCD Type 1 / CDC application |
