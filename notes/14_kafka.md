# Kafka & Streaming — Complete Notes from Scratch

---

## 1. Why Kafka Exists

Traditional message queues like RabbitMQ or SQS are designed around the idea of a task queue: a producer enqueues a job, a consumer picks it up and processes it, the message is deleted. That works well for task dispatch, but data engineering needs something fundamentally different — a durable, replayable log of events that multiple independent systems can read at their own pace.

Kafka is best understood not as a "fancy message queue" but as a **distributed commit log**: an append-only, ordered, replicated record of everything that happened. Just like a database's WAL (write-ahead log) records every change for replication and recovery, Kafka records every event for any consumer to read — now or days from now.

```
Problem: traditional message queues (RabbitMQ, SQS) delete messages after consumption.
For data engineering, we need:
- Multiple consumers reading same data at different speeds
- Replay old data (reprocess, backfill, debug)
- Massive throughput (millions of events/second)
- Durable, ordered log of events

Kafka: distributed commit log (append-only, ordered, replicated)
- Event streaming platform, not just a queue
- Events retained for configurable period (days, weeks, forever)
- Multiple consumer groups read independently
```

> **💡 Interview tip:** The single most important thing to say about Kafka vs a traditional queue is: **Kafka doesn't delete messages after consumption**. This enables replay (reprocess historical data), multiple independent consumer groups (your ETL pipeline and your ML model both read the same events without interfering), and time travel debugging. If you only remember one thing about Kafka, make it this.

> **🌍 Real world:** At a typical e-commerce company, a single `orders` topic might be consumed by: the ETL pipeline writing to the data warehouse, the fraud detection service scoring transactions in real time, the notification service sending confirmation emails, and the inventory service decrementing stock counts — all independently, at their own pace, without any coordination.

---

## 2. Architecture

### Core Components

Understanding the relationship between topics, partitions, and offsets is the mental model everything else builds on. A topic is the logical category (like a database table name). A partition is the physical unit — an ordered, append-only log stored on disk. Offsets are the sequence numbers within each partition, and each consumer group tracks its own position independently.

```
Broker:       Kafka server — stores and serves messages
Cluster:      Multiple brokers working together
ZooKeeper:    Coordination service (being replaced by KRaft in Kafka 3.x)
KRaft:        Kafka's built-in consensus (no ZooKeeper needed)

Topic:        Named stream of events (like a database table)
Partition:    Ordered, immutable sequence within a topic
              Partitions allow parallelism
              Each partition is on one broker (replicated to others)
Offset:       Position of a message within a partition (starts at 0)
              Each consumer tracks its own offset

Producer:     Writes messages to topics
Consumer:     Reads messages from topics
Consumer Group: Multiple consumers sharing work (each partition → one consumer)

Leader:       Partition that handles all reads/writes (per partition)
Follower:     Replica that syncs from leader (failover candidate)
ISR:          In-Sync Replicas — followers caught up with leader
```

### How Messages Flow

The key insight here is that partitions enable horizontal parallelism, while consumer groups enable independent, isolated reads. Two consumer groups reading the same topic are completely unaware of each other — each has its own bookmark (offset) and reads at its own pace, as if the other didn't exist.

```
Producer → [Partition 0: msg0, msg1, msg2...]
           [Partition 1: msg0, msg1, msg2...]   → Consumer Group A
           [Partition 2: msg0, msg1, msg2...]
                                                 → Consumer Group B
                                                 → Consumer Group C

Each group maintains its own offsets — reads data at its own pace.
Consumers in the SAME group split partitions between them (parallel).
```

> **💡 Interview tip:** "How many consumers can you add to a consumer group before you get no additional benefit?" — the answer is: the number of partitions. If a topic has 12 partitions, you can have at most 12 active consumers in a group (one per partition). A 13th consumer would sit idle. This is why partition count is a forward-looking capacity decision — set it higher than your current consumer count if you anticipate needing to scale.

---

## 3. Topics and Partitions

Partitions are Kafka's unit of parallelism and ordering. The trade-off to understand: within a partition, messages are strictly ordered and only one consumer (per group) reads from it. Across partitions, there's no ordering guarantee. The solution is to use a message key — Kafka hashes the key to deterministically assign messages with the same key to the same partition, guaranteeing order for that entity.

```
Topic "orders":
Partition 0: [order#1, order#3, order#7, ...]
Partition 1: [order#2, order#5, order#8, ...]
Partition 2: [order#4, order#6, order#9, ...]

Partition count:
- More partitions = more parallelism (but more overhead)
- Max consumers in a group = number of partitions
- Rule of thumb: partitions = max(expected consumers) or 10-50 for most topics

Partition assignment for messages:
- With key: hash(key) % num_partitions → deterministic, same key → same partition
- Without key: round-robin across partitions

Message ordering:
- Only guaranteed WITHIN a partition (not across)
- Use message key if order matters per entity (customer_id as key → all orders for same customer in same partition, in order)
```

> **🌍 Real world:** Using `customer_id` as the Kafka message key is a very common pattern. It guarantees all events for the same customer land in the same partition and are processed in order. This matters for state machines — you need to process "order placed" before "order shipped" for the same customer. Without a key, these could end up in different partitions and be processed out of order.

> **💡 Interview tip:** Be ready to discuss the partition count trade-off. More partitions = more parallelism and throughput, but also more overhead (more file handles on brokers, slower rebalancing, more metadata). A common mistake is under-partitioning at creation time — you can't easily reduce partition count later (you can increase, but that changes key-to-partition routing, breaking ordering guarantees for existing keys).

---

## 4. Producers

The producer configuration, especially `acks`, is where you control the durability vs latency trade-off. `acks=all` is the right default for data engineering — you'd rather have slightly higher write latency than lose an event because the leader died before a replica caught up.

```python
from confluent_kafka import Producer

producer = Producer({
    'bootstrap.servers': 'localhost:9092',
    'acks': 'all',                  # wait for all ISR to ack (safest)
    'retries': 3,
    'max.in.flight.requests.per.connection': 1,  # ensure ordering with retries
    'enable.idempotence': True,     # exactly-once at producer level
    'compression.type': 'snappy',   # compress: none, gzip, snappy, lz4, zstd
})

def delivery_callback(err, msg):
    if err:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}')

# Produce with key (same key → same partition → ordered)
import json

order = {
    'order_id': '12345',
    'customer_id': 'C001',
    'amount': 99.99,
    'ts': '2025-05-21T10:00:00'
}

producer.produce(
    topic='orders',
    key='C001',                          # customer_id as key
    value=json.dumps(order).encode(),
    callback=delivery_callback
)

producer.flush()  # wait for all messages to be delivered

# Producer acks:
# acks=0: fire and forget — no confirmation (fastest, can lose data)
# acks=1: leader acks — faster, loses data if leader dies before replica sync
# acks=all (or -1): all ISR ack — slowest, safest
```

> **💡 Interview tip:** The `acks` setting is a classic interview topic. Be able to explain all three modes and when you'd use each. For DE pipelines, `acks=all` + `enable.idempotence=True` is standard. Idempotent producers assign sequence numbers to messages so the broker can deduplicate retries — without it, a network timeout followed by a retry could produce a duplicate message.

> **🌍 Real world:** `compression.type: snappy` is worth mentioning in interviews. Kafka messages are typically JSON or Avro, which compress well. Snappy gives 3-5x compression with minimal CPU overhead — at millions of events per second, this is a meaningful cost and throughput win. Snappy is the common choice; use `lz4` for even lower CPU overhead, `zstd` for best compression ratio.

---

## 5. Consumers

The consumer's `enable.auto.commit` setting and manual offset management are where most production bugs live. Auto-commit is convenient but dangerous: it periodically commits offsets regardless of whether your processing succeeded, meaning a crash between commit and processing leaves messages unprocessed with no way to know. Manual commit — committing only after successful processing — gives you at-least-once delivery semantics.

```python
from confluent_kafka import Consumer
import json

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'etl-pipeline-group',
    'auto.offset.reset': 'earliest',    # start from beginning if no committed offset
    # 'auto.offset.reset': 'latest',   # start from new messages only
    'enable.auto.commit': False,        # manual offset commit (safer)
})

consumer.subscribe(['orders'])

try:
    while True:
        msg = consumer.poll(timeout=1.0)  # poll every 1 second
        
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        
        # Process message
        order = json.loads(msg.value().decode('utf-8'))
        print(f"Received: {order}")
        
        # Process...
        process_order(order)
        
        # Commit offset AFTER successful processing
        consumer.commit(message=msg)     # synchronous commit
        # consumer.commit(asynchronous=True)  # async commit (faster but less safe)

finally:
    consumer.close()
```

### Consumer Groups

A consumer group is how Kafka scales consumption horizontally. Within a group, each partition is owned by exactly one consumer — so work is automatically divided and parallelised. When a consumer fails, Kafka rebalances and redistributes its partitions to surviving consumers, providing automatic failover without any coordination code in your application.

```
Group "etl-pipeline":
  Consumer 1 → Partition 0
  Consumer 2 → Partition 1
  Consumer 3 → Partition 2

Adding Consumer 4:
  (No effect if 3 partitions — one consumer sits idle)
  
Removing Consumer 2 (failure):
  Rebalance triggered → Consumer 1 or 3 takes over Partition 1

Consumer group benefits:
- Parallel processing (each consumer handles subset of partitions)
- Automatic failover (rebalance on consumer failure)
- Independent progress (different groups read at different speeds)
```

> **🌍 Real world:** Consumer group rebalancing is worth understanding deeply. When a consumer joins or leaves (or crashes), Kafka triggers a rebalance — all consumers briefly stop, Kafka reassigns partitions, then consumers resume. During rebalancing, no messages are processed. For high-throughput pipelines, frequent rebalances (e.g., due to noisy consumer restarts) can cause significant lag. `session.timeout.ms` and `heartbeat.interval.ms` tuning controls how quickly Kafka detects a failed consumer and triggers rebalance.

---

## 6. Offset Management

The offset is Kafka's bookmark — it records "this consumer group has successfully processed all messages up to this position in this partition." Offsets are stored in a special internal topic called `__consumer_offsets`. This means if all consumers in a group restart, they pick up exactly where they left off.

```
Committed offset = "I've successfully processed up to this position"
Stored in: __consumer_offsets topic (internal Kafka topic)

auto.offset.reset:
- 'earliest': start from offset 0 if no committed offset exists
- 'latest': start from end (new messages only) if no committed offset

enable.auto.commit = True (default):
- Commits periodically (auto.commit.interval.ms = 5000)
- May process messages, crash before commit → reprocess (at-least-once)

enable.auto.commit = False (safer):
- You control when to commit
- Commit after successful processing → at-least-once
- Commit before processing → at-most-once (can lose messages)
- Transactional commit → exactly-once (complex)

Manual commit patterns:
# Commit after each message (safest, slowest)
consumer.commit(message=msg)

# Commit every N messages (batch efficiency)
count = 0
while True:
    msg = consumer.poll(1.0)
    process(msg)
    count += 1
    if count % 100 == 0:
        consumer.commit()
```

> **💡 Interview tip:** "Explain at-least-once vs exactly-once in Kafka" is a very common question. At-least-once (commit after processing) is the practical default — your processing might run twice on failure, so make it idempotent (same message processed twice = same result). True exactly-once requires Kafka transactions, which are complex and have performance overhead. Most DE teams accept at-least-once + idempotent consumers rather than pay the cost of full EOS (exactly-once semantics).

---

## 7. Replication and Durability

Replication is Kafka's mechanism for fault tolerance. With a replication factor of 3, each partition is stored on 3 different brokers — the cluster survives 2 broker failures without data loss. The `acks=all` + `min.insync.replicas=2` combination is the standard durability configuration: a write is only acknowledged when at least 2 replicas have confirmed it.

```
Replication factor:
- replication.factor=3: each partition on 3 brokers
- Survives 2 broker failures without data loss

min.insync.replicas=2:
- Producer with acks=all requires at least 2 replicas to be in-sync
- Protection against writing to a single replica

Durability configuration:
log.flush.interval.messages=1     # flush every message (slow, safe)
log.flush.interval.ms=1000        # flush every second
log.retention.hours=168           # keep 7 days
log.retention.bytes=-1            # no size limit
log.segment.bytes=1073741824      # 1GB segments
```

> **💡 Interview tip:** The classic durability question: "what's the difference between `replication.factor` and `min.insync.replicas`?" Replication factor is how many copies of data exist. `min.insync.replicas` is the minimum number that must acknowledge a write before the producer gets success. With `replication.factor=3` and `min.insync.replicas=2`: you have 3 copies, and writes require 2 to ack — meaning you can tolerate 1 replica being down while still accepting writes. If 2 replicas go down, writes will fail (producer gets an exception) rather than proceeding with only 1 replica — which protects against silent data loss.

---

## 8. Schema Registry + Avro

Without Schema Registry, changing a Kafka message structure is a coordination nightmare: you'd have to simultaneously update all producers and consumers, or consumers would silently parse incorrect data. Schema Registry solves this by being the single source of truth for message schemas, with enforced compatibility rules so you can evolve schemas safely.

```
Problem: consumer code breaks when producer changes message structure.
Solution: Schema Registry = central store for Avro/Protobuf/JSON schemas.

Schema Registry:
- Producer registers schema before producing
- Schema ID embedded in message (not full schema)
- Consumer fetches schema by ID, deserializes message
- Schema compatibility checks (backward, forward, full)

Avro schema example:
{
  "type": "record",
  "name": "Order",
  "namespace": "com.example",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "customer_id", "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "status", "type": {"type": "enum", "name": "Status",
      "symbols": ["pending", "confirmed", "shipped"]}},
    {"name": "created_at", "type": "long", "logicalType": "timestamp-millis"}
  ]
}

Compatibility modes:
BACKWARD:  new schema can read old data (safe for consumers to upgrade first)
FORWARD:   old schema can read new data (safe for producers to upgrade first)
FULL:      both backward and forward
NONE:      no compatibility checks (risky)
```

> **💡 Interview tip:** Know the compatibility modes and why they matter for deployment order. BACKWARD compatibility means you upgrade consumers first, then producers (new consumers can read old messages that are still in the topic). FORWARD means producers first. FULL is the safest — upgrade in any order. In practice, BACKWARD is most common: you deploy the new consumer version first, then roll out the new producer.

> **🌍 Real world:** At scale, Avro with Schema Registry typically reduces message size by 30-60% compared to JSON (no field names repeated in every message), while adding schema validation and evolution guarantees. The tradeoff is operational complexity: you need Schema Registry running and available, and debugging binary Avro messages is harder than JSON. Most serious Kafka deployments at enterprise scale use Schema Registry + Avro or Protobuf.

---

## 9. Kafka Connect

Kafka Connect answers the question: "I need to move data from X to Kafka and from Kafka to Y — do I really have to write all that plumbing code?" The answer is no. Connect is a framework of worker processes that run connectors — pluggable components that know how to read from (source) or write to (sink) specific systems. Debezium is the most important source connector in data engineering.

```
Kafka Connect: framework for moving data between Kafka and external systems.
No code needed for common integrations.

Source connectors (→ Kafka):
- Debezium PostgreSQL: CDC from Postgres WAL → Kafka
- JDBC Source: poll database table → Kafka
- S3 Source: read S3 files → Kafka
- Salesforce Source, etc.

Sink connectors (Kafka →):
- S3 Sink: Kafka → S3 (Parquet/JSON/Avro)
- JDBC Sink: Kafka → PostgreSQL/Redshift
- Elasticsearch Sink
- Snowflake Sink

Example: Debezium CDC pipeline
PostgreSQL → Debezium → Kafka (topic: mydb.public.orders) → S3 Sink → S3

# Connector config (deployed via REST API)
{
  "name": "postgres-source",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "dbz",
    "database.dbname": "mydb",
    "database.server.name": "mydb",
    "table.include.list": "public.orders,public.customers",
    "plugin.name": "pgoutput"
  }
}
```

> **💡 Interview tip:** Debezium is a critical concept for DE interviews. The key thing to understand: Debezium reads the Postgres **WAL (write-ahead log)** — the same internal transaction log Postgres uses for replication. This means it captures every INSERT, UPDATE, and DELETE at the database level, without any application code changes, and without polling the table (which can miss deletes and cause lag). This is true CDC. Compare this to JDBC Source connector which polls tables periodically — it can't detect deletes and has latency.

> **🌍 Real world:** The Debezium → Kafka → S3 Sink pattern is one of the most common streaming data lake ingestion patterns. Every database change lands in S3 as a Kafka topic (with the full before/after row state), creating a complete audit log of your database. This is then consumed by the data warehouse to build SCD Type 2 history tables, or by a Delta Lake MERGE job for near-real-time updates.

---

## 10. Kafka Streams (Stream Processing)

Kafka Streams is a JVM library (Java/Scala) for building stateful stream processing applications that read from and write back to Kafka topics. For Python-based DE teams, Faust (Python) or Spark Structured Streaming are more common — but Kafka Streams is worth knowing for interviews.

```java
// Java/Scala — Python uses Faust or Spark Structured Streaming
StreamsBuilder builder = new StreamsBuilder();

KStream<String, Order> orders = builder.stream("orders");

// Filter and transform
KStream<String, EnrichedOrder> enriched = orders
    .filter((key, order) -> order.getAmount() > 0)
    .mapValues(order -> enrich(order));

// Aggregate — count orders per customer per 1-hour window
orders
    .groupByKey()
    .windowedBy(TimeWindows.of(Duration.ofHours(1)))
    .count()
    .toStream()
    .to("order-counts-by-customer");
```

---

## 11. Spark Structured Streaming + Kafka

Spark Structured Streaming brings the familiar DataFrame API to stream processing. It reads Kafka as a continuous stream of rows (with a `value` column containing the raw bytes), and you apply the same transformations you'd use in batch Spark. The checkpoint location is critical — it's how Spark tracks which Kafka offsets it has processed, enabling restartability.

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, sum as _sum
from pyspark.sql.types import StructType, StringType, DoubleType

spark = SparkSession.builder \
    .appName("KafkaStreaming") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()

# Read from Kafka
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "orders") \
    .option("startingOffsets", "earliest") \
    .load()

# Parse JSON payload
schema = StructType() \
    .add("order_id", StringType()) \
    .add("customer_id", StringType()) \
    .add("amount", DoubleType())

orders = kafka_df.select(
    from_json(col("value").cast("string"), schema).alias("data"),
    col("timestamp")
).select("data.*", "timestamp")

# Windowed aggregation
revenue = orders \
    .withWatermark("timestamp", "10 minutes") \   # allow 10 min late data
    .groupBy(
        window("timestamp", "1 hour"),
        "customer_id"
    ) \
    .agg(_sum("amount").alias("total_revenue"))

# Write to console (dev), S3, Kafka, JDBC
query = revenue.writeStream \
    .format("console") \
    .outputMode("update") \     # append | complete | update
    .option("checkpointLocation", "s3://bucket/checkpoints/revenue/") \
    .start()

query.awaitTermination()
```

> **💡 Interview tip:** Know the three output modes for Structured Streaming: `append` (only new rows, default for non-aggregation), `complete` (entire result table every trigger — only for aggregations), `update` (only rows that changed since last trigger). For windowed aggregations, `update` is the most efficient — you only write the windows that received new data, not the entire table.

> **🌍 Real world:** The `withWatermark` call is essential for stateful aggregations in production. Without a watermark, Spark has to keep all historical state in memory forever (waiting for arbitrarily late data). The watermark tells Spark: "if data is more than 10 minutes late, I'll drop it." This bounds memory usage and allows Spark to emit final results for completed windows. Setting the watermark too tight drops legitimate late-arriving events; too loose uses excessive memory.

---

## 12. Kafka vs AWS Kinesis

Both solve the same problem — durable, ordered, high-throughput event streaming — but with different operational trade-offs. The key decision factor is usually whether you're all-in on AWS (Kinesis is simpler) vs needing ecosystem richness or very high throughput at lower cost (Kafka wins).

```
Kinesis Data Streams:
- AWS managed (no infrastructure)
- 24h default retention (7 days max, extended = extra cost)
- Shards instead of partitions (1 shard = 1MB/s in, 2MB/s out)
- More expensive at scale
- Tight AWS integration (Lambda, Glue, Firehose)
- Good for: AWS-native, small-medium scale, low ops overhead

Kafka (self-hosted or Confluent Cloud / MSK):
- More control, open source
- Configurable retention (days, weeks, unlimited)
- Much cheaper at scale
- Huge ecosystem (Connect, Streams, Schema Registry)
- MSK = AWS-managed Kafka (middle ground)
- Good for: high-volume, complex streaming, multi-cloud

When to use Kinesis:
- Already all-in on AWS
- Don't want to manage Kafka
- Short retention is fine
- Moderate throughput

When to use Kafka:
- High throughput (millions of events/sec)
- Long retention / replay important
- Multiple consumer ecosystems
- Cost-sensitive at scale
```

> **🌍 Real world:** MSK (Amazon Managed Streaming for Kafka) is a popular middle ground — you get Kafka's ecosystem and unlimited retention without managing brokers yourself. The common production pattern: MSK for ingestion (Kafka ecosystem, low cost at scale), with Kinesis Firehose for simple fan-out to S3 when you don't need the full Kafka feature set.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Topic | Named stream of events — logical category |
| Partition | Ordered log within topic — unit of parallelism |
| Consumer group | Multiple consumers share partitions — parallel processing |
| Offset | Position in partition — each group tracks independently |
| acks=all | Wait for all ISR to confirm — safest |
| at-least-once | Commit after processing — duplicates possible |
| Schema Registry | Central schema store — prevents breaking changes |
| Debezium | CDC connector — reads DB WAL → Kafka events |
| Kafka Connect | No-code data movement — source + sink connectors |
| Kafka Streams | Stateful stream processing on JVM |
| Spark + Kafka | Micro-batch or streaming processing with full Spark API |
| Kinesis vs Kafka | Kinesis = AWS-managed ease; Kafka = scale + ecosystem |
