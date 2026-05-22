# Data Engineer — Complete Learning Plan from Scratch
> Every topic from Sai Suhas Kumar's resume, structured beginner → advanced

---

## 1. Python

### Basics
- Variables, data types, type casting
- Strings — slicing, formatting, methods
- Lists, tuples, sets, dictionaries
- Conditionals and loops
- Functions — args, kwargs, default values
- File I/O — read, write, append

### Intermediate
- List comprehensions and dict comprehensions
- Lambda functions
- Map, filter, reduce
- Error handling — try/except/finally
- Modules and packages — import system
- Virtual environments

### Advanced
- Object-oriented programming — classes, inheritance, polymorphism, encapsulation
- Abstract classes and interfaces
- Decorators
- Generators and iterators
- Context managers — `with` statement
- Type hints and annotations
- `*args` and `**kwargs` internals

### Data Engineering Specific
- `pandas` — Series, DataFrame, indexing, groupby, merge, pivot, apply
- `pydantic` — data validation and settings management
- `pytest` — unit testing, fixtures, mocking
- Shell scripting with Python — `subprocess`, `os`, `pathlib`
- Logging best practices
- Working with file formats — CSV, JSON, Parquet, ORC

---

## 2. SQL

### Basics
- SELECT, WHERE, ORDER BY, LIMIT
- INSERT, UPDATE, DELETE
- Aggregate functions — COUNT, SUM, AVG, MIN, MAX
- GROUP BY, HAVING
- JOINs — INNER, LEFT, RIGHT, FULL OUTER, CROSS
- Subqueries

### Intermediate
- CTEs (Common Table Expressions)
- Window functions — ROW_NUMBER, RANK, DENSE_RANK, NTILE, LAG, LEAD, FIRST_VALUE, LAST_VALUE
- CASE statements
- String functions, date functions, numeric functions
- NULL handling — COALESCE, NULLIF, IS NULL
- UNION vs UNION ALL

### Advanced
- Query optimisation — indexes, execution plans, EXPLAIN/ANALYZE
- Partitioning — range, list, hash
- Stored procedures and functions
- Triggers
- Transactions — ACID properties, isolation levels
- Normalisation — 1NF, 2NF, 3NF, BCNF
- Denormalisation — when and why

---

## 3. Data Modeling

### Concepts
- Entities, attributes, relationships
- ER diagrams
- Primary keys, foreign keys, surrogate keys

### Dimensional Modeling
- Fact tables vs dimension tables
- Star schema
- Snowflake schema
- When to use star vs snowflake
- Measures vs dimensions
- Grain of a fact table

### Slowly Changing Dimensions (SCD)
- SCD Type 1 — overwrite
- SCD Type 2 — versioning with effective dates
- SCD Type 3 — previous value column
- SCD Type 4, 6 (hybrid)

### Modern Patterns
- Data vault — hubs, links, satellites
- Medallion architecture — Bronze, Silver, Gold layers
- One Big Table (OBT) pattern

---

## 4. Data Warehousing

### Concepts
- OLTP vs OLAP
- Row-oriented vs columnar storage
- Compression in columnar formats
- Materialized views
- Partitioning and clustering

### Amazon Redshift
- Architecture — leader node, compute nodes
- Distribution styles — KEY, ALL, EVEN, AUTO
- Sort keys — compound vs interleaved
- VACUUM and ANALYZE
- Workload Management (WLM)
- Redshift Spectrum — querying S3 from Redshift
- COPY command — loading data
- UNLOAD command — exporting data

### Snowflake
- Architecture — storage layer, compute layer, cloud services layer
- Virtual warehouses — scaling up vs scaling out
- Multi-cluster warehouses
- Clustering keys
- Zero-copy cloning
- Time travel and fail-safe
- Snowpipe — continuous data ingestion
- Data sharing
- Stages — internal vs external
- File formats in Snowflake
- Query profiling and optimisation

---

## 5. AWS Core Services

### AWS Fundamentals
- IAM — users, roles, policies, least privilege
- VPC basics — subnets, security groups, route tables
- CloudWatch — metrics, logs, alarms, dashboards
- S3 — buckets, objects, prefixes, versioning
- S3 storage classes
- S3 lifecycle policies
- S3 event notifications
- S3 partitioning strategies for analytics

### AWS Lambda
- Serverless architecture concepts
- Lambda functions — handlers, runtime, layers
- Event sources and triggers
- Cold starts and warm starts
- Concurrency — reserved and provisioned
- Lambda with S3, DynamoDB, SQS, EventBridge
- Deployment packages and container images
- Environment variables and secrets management

### AWS Glue
- Glue architecture — Data Catalog, crawlers, ETL jobs
- Glue Data Catalog — databases, tables, partitions
- Glue Crawlers — discovering schemas automatically
- Glue ETL jobs — script vs visual (Glue Studio)
- DynamicFrame vs Spark DataFrame
- Job bookmarks — incremental processing
- Glue Workflows
- Glue triggers — scheduled, conditional, on-demand
- Glue connection types
- Glue vs EMR — when to use which
- Glue Studio — visual ETL

### AWS Step Functions
- State machine concepts
- State types — Task, Choice, Wait, Parallel, Map, Pass, Fail, Succeed
- Express vs Standard workflows
- Error handling — Catch and Retry
- Input/output processing — InputPath, OutputPath, ResultPath, Parameters
- Integrating with Lambda, Glue, ECS, SNS, SQS
- Step Functions vs Airflow

### Amazon Athena
- Serverless query service on S3
- Presto/Trino under the hood
- Supported file formats — Parquet, ORC, JSON, CSV, Avro
- Partitioning for performance
- Partition projection
- Query optimisation — columnar formats, compression, partitioning
- Athena workgroups
- Athena + Glue Data Catalog integration
- Cost optimisation

### AWS EventBridge
- Events, rules, targets
- Scheduled expressions — cron and rate
- Event patterns and filtering
- EventBridge vs CloudWatch Events vs SNS vs SQS

### Amazon RDS
- Managed relational databases
- PostgreSQL on RDS — configuration, parameter groups
- Read replicas vs Multi-AZ
- Automated backups and snapshots
- Connection pooling

### AWS Data Pipeline (Legacy)
- Pipeline definition
- Activities, schedules, data nodes, preconditions
- AWS Data Pipeline vs Glue — understanding the shift

---

## 6. ETL/ELT Pipelines

### Concepts
- ETL vs ELT — when to use which
- Batch processing vs stream processing
- Full load vs incremental load
- Idempotency — designing pipelines that are safe to re-run
- Exactly-once, at-least-once, at-most-once semantics
- Data lineage
- Data quality validation

### Pipeline Design Patterns
- Landing → Raw → Curated → Consumption pattern
- Partitioning strategies for large datasets
- Handling schema changes and schema evolution
- Late-arriving data handling
- Watermarks and event time vs processing time
- Dead letter queues and error handling
- Checkpointing and restartability

### File Formats
- CSV — pros, cons, use cases
- JSON — nested data, pros and cons
- Parquet — columnar, compression, row groups, metadata
- ORC — columnar, stripes, indexes, ACID support
- Avro — schema evolution, row-based, good for streaming
- Parquet vs ORC vs Avro — when to use which

---

## 7. Apache Spark & PySpark

### Spark Architecture
- Driver and executors
- Cluster manager — Standalone, YARN, Kubernetes
- SparkContext and SparkSession
- DAG (Directed Acyclic Graph) execution model
- Stages and tasks
- Lazy evaluation

### RDDs
- Resilient Distributed Datasets — basics
- Transformations — map, filter, flatMap, reduceByKey
- Actions — collect, count, take, saveAsTextFile
- RDD vs DataFrame vs Dataset

### DataFrames and Datasets
- Creating DataFrames
- Schema — StructType, StructField, data types
- Transformations — select, filter, where, withColumn, drop, rename
- Aggregations — groupBy, agg, count, sum, avg
- Joins — inner, left, right, full, cross, semi, anti
- Window functions in Spark
- User Defined Functions (UDFs)
- Handling null values

### Spark SQL
- Creating temp views and global views
- Running SQL on DataFrames
- Catalyst optimizer
- Tungsten execution engine

### Performance Optimisation
- Partitions — understanding default parallelism
- Repartition vs coalesce
- Broadcast joins — when and how to use
- Sort-merge join vs broadcast join vs shuffle hash join
- Data skew — causes and solutions (salting, skew hint)
- Caching and persistence — storage levels
- Spark UI — jobs, stages, tasks, DAG visualisation
- Shuffle — what causes it, how to minimise
- Predicate pushdown
- Column pruning

### PySpark Specific
- PySpark with AWS Glue
- DynamicFrame — resolveChoice, applyMapping, relationalize
- Reading and writing various formats
- Working with S3 in PySpark

---

## 8. PostgreSQL

### Core
- Data types — numeric, text, boolean, date/time, JSON, UUID, arrays
- Constraints — NOT NULL, UNIQUE, CHECK, PRIMARY KEY, FOREIGN KEY
- Indexes — B-tree, hash, GIN, GiST — when to use which
- EXPLAIN and EXPLAIN ANALYZE — reading execution plans
- Vacuum and autovacuum
- Table partitioning — range, list, hash

### Advanced
- Stored procedures — PL/pgSQL
- Functions — SQL functions vs PL/pgSQL functions
- Triggers
- CTEs — recursive CTEs
- JSON and JSONB operations
- Full-text search
- Extensions — pg_stat_statements, pgcrypto, pgvector
- Connection pooling — PgBouncer
- Replication — logical vs physical

---

## 9. CI/CD & DevOps

### Git
- Branching strategies — GitFlow, trunk-based development
- Merge vs rebase
- Pull requests and code reviews
- Resolving merge conflicts
- Git hooks
- Tagging and releases

### Jenkins
- Pipeline as code — Jenkinsfile
- Declarative vs scripted pipeline
- Stages and steps
- Parallel execution
- Triggers — webhook, scheduled, upstream
- Credentials and secrets management
- Jenkins agents
- Integrating with AWS

### CI/CD Concepts
- Continuous Integration — automated testing on every commit
- Continuous Delivery vs Continuous Deployment
- Build, test, deploy pipeline
- Environment promotion — dev → staging → production
- Blue/green deployments
- Rollback strategies

### Infrastructure as Code
- IaC concepts — immutable infrastructure
- AWS CloudFormation basics
- Terraform (to learn) — HCL, state, modules, providers

---

## 10. Data Quality & Observability

### Data Quality Concepts
- Completeness, accuracy, consistency, timeliness, validity, uniqueness
- Data quality checks — row counts, null checks, range checks, referential integrity
- Schema validation
- Data contracts

### Tools
- Great Expectations — expectations, validation, data docs
- Soda Core — checks YAML, scans
- dbt tests — schema tests, custom tests

### Pipeline Observability
- Logging best practices — structured logging
- Metrics — pipeline duration, rows processed, error rates
- Alerting — CloudWatch Alarms, SNS notifications
- Data lineage tracking

---

## 11. Apache Airflow (To Learn)

### Basics
- Architecture — scheduler, executor, webserver, metadata DB, workers
- DAGs — definition, structure, default args
- Operators — PythonOperator, BashOperator, S3Operator, GlueJobOperator
- Sensors — S3KeySensor, ExternalTaskSensor
- Hooks — S3Hook, PostgresHook
- XComs — passing data between tasks
- Variables and Connections

### Intermediate
- Task dependencies — set_upstream, set_downstream, bitshift operators
- Scheduling — cron expressions, timedelta
- Catchup and backfill
- Task retries and timeouts
- Branching — BranchPythonOperator
- SubDAGs and TaskGroups
- Dynamic DAGs

### Advanced
- Executors — LocalExecutor, CeleryExecutor, KubernetesExecutor
- KubernetesPodOperator
- Airflow with Docker
- Airflow on AWS MWAA (Managed Workflows)
- DAG best practices
- Testing Airflow DAGs

---

## 12. dbt (To Learn)

### Basics
- What is dbt — transformation layer
- dbt project structure — models, sources, seeds, tests, macros, snapshots
- dbt CLI commands — run, test, compile, docs generate

### Models
- SQL models — SELECT statements as models
- Materialisation types — table, view, incremental, ephemeral
- ref() and source() functions
- Model dependencies and DAG

### Testing
- Schema tests — not_null, unique, accepted_values, relationships
- Custom tests
- dbt test command

### Advanced
- Incremental models — is_incremental(), unique_key, merge strategy
- Snapshots — SCD Type 2 with dbt
- Jinja templating in dbt — variables, macros, if/for blocks
- dbt packages
- dbt docs and lineage graph
- dbt + Snowflake / Redshift
- dbt + Airflow integration

---

## 13. Docker (To Learn)

### Basics
- Containers vs virtual machines
- Docker architecture — daemon, client, registry
- Images and containers
- Dockerfile — FROM, RUN, COPY, WORKDIR, CMD, ENTRYPOINT, ENV
- Building and tagging images
- Running containers — ports, volumes, environment variables

### Intermediate
- docker-compose — services, networks, volumes
- Multi-container applications
- Docker networking
- Docker volumes — bind mounts vs named volumes
- Docker Hub and ECR (AWS)

### Data Engineering Use Cases
- Containerising a Python ETL job
- Running Airflow with Docker Compose
- Running Spark locally in Docker
- Docker + AWS ECS / Fargate basics

---

## 14. Kafka & Streaming (To Learn)

### Concepts
- Stream processing vs batch processing
- Event-driven architecture
- Message queues vs event streams

### Kafka Architecture
- Brokers, clusters, ZooKeeper / KRaft
- Topics and partitions
- Producers and consumers
- Consumer groups and offsets
- Replication factor and ISR

### Core Operations
- Producing messages — key, value, partition, timestamp
- Consuming messages — poll loop, commit strategies
- Auto vs manual offset management
- At-least-once, at-most-once, exactly-once delivery

### Advanced
- Schema Registry and Avro serialisation
- Kafka Streams
- Kafka Connect — source and sink connectors
- Kafka vs AWS Kinesis — when to use which
- Kafka + Spark Structured Streaming

---

## 15. Terraform (To Learn)

### Basics
- Infrastructure as Code with Terraform
- HCL syntax — blocks, arguments, expressions
- Providers — AWS provider setup
- Resources, data sources, variables, outputs, locals

### Core Workflow
- terraform init, plan, apply, destroy
- State file — what it is, why it matters
- Remote state — S3 + DynamoDB locking

### Intermediate
- Modules — creating and using
- Workspaces
- Terraform with AWS — S3, Lambda, Glue, RDS, IAM
- Count and for_each — dynamic resources
- Depends_on and lifecycle

---

## 16. Modern Data Stack & Emerging

### Delta Lake / Apache Iceberg
- ACID transactions on data lakes
- Time travel queries
- Schema evolution
- Partition evolution (Iceberg)
- Delta Lake vs Iceberg vs Hudi
- Delta Lake + Spark

### Modern ELT Stack
- Fivetran / Airbyte — managed connectors
- dbt — transformation layer (see section 12)
- Snowflake / BigQuery / Redshift — destinations
- Reverse ETL concepts

### AI/ML Data Engineering
- Feature stores — what they are and why
- ML pipelines vs data pipelines
- Vector databases — pgvector, Pinecone, Chroma
- Embeddings — what they are
- RAG (Retrieval Augmented Generation) pattern
- LangChain / LangGraph — agent and chain patterns
- Building AI-powered data pipelines

---

## Learning Order (Recommended)

```
Week 1-2   → Python (Intermediate + Advanced)
Week 3-4   → SQL (Advanced) + Data Modeling
Week 5-6   → PySpark deep dive
Week 7-8   → AWS deep dives (Glue, Redshift, Athena, Step Functions)
Week 9-10  → Airflow
Week 11-12 → dbt
Week 13    → Docker
Week 14    → Kafka concepts
Week 15    → Terraform basics
Week 16    → Delta Lake + Modern stack
Ongoing    → LeetCode SQL + Python 3x/week
```
