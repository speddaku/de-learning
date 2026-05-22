# Apache Airflow — Complete Notes from Scratch

---

## Why Airflow Exists

Before workflow orchestrators, data teams scheduled jobs with cron. Cron works fine for independent scripts, but falls apart when jobs have dependencies: "run job B only after job A succeeds, and only if job C hasn't run yet today." Airflow models these dependencies explicitly as a Directed Acyclic Graph (DAG), handles retries, surfaces failures in a UI, and keeps history of every run. It's essentially "cron + dependency management + observability."

> **🌍 Real world:** Airflow is the most widely-used workflow orchestrator in data engineering. Even if your team uses Prefect, Dagster, or dbt Cloud, understanding Airflow deeply is expected in interviews because most organizations have some Airflow footprint. The concepts (DAG, task, sensor, XCom) also transfer to other orchestrators.

---

## 1. Architecture

Understanding Airflow's architecture helps you reason about where failures come from and how to scale the system. The scheduler is the brain, but it only *schedules* — it doesn't run anything itself. The executor decides *how* tasks run. Workers actually *execute* the tasks.

```
Scheduler:
- Heart of Airflow
- Continuously parses DAG files
- Determines which tasks are ready to run
- Submits tasks to executor

Executor:
- Decides HOW tasks run (locally, on workers, in K8s)
- LocalExecutor: parallel on same machine
- CeleryExecutor: distributed workers via message queue
- KubernetesExecutor: each task in its own Pod

Workers:
- CeleryExecutor only — actual machines running tasks
- Pick up tasks from queue (Redis/RabbitMQ)

Webserver:
- UI at port 8080
- View DAGs, task logs, history

Metadata DB (PostgreSQL or MySQL):
- Stores DAG runs, task states, connections, variables, XComs
- Queried constantly by scheduler/webserver

Triggerer:
- Handles deferrable operators (non-blocking waits)
- New in Airflow 2.2+
```

> **💡 Interview tip:** "What happens when the Airflow metadata database gets slow?" This is a real production problem. The scheduler queries the metadata DB in a tight loop — if the DB is overloaded, the scheduler's heartbeat degrades, tasks take longer to be marked as queued/running/success, and the whole system appears "slow." The fix is usually: proper DB indexing, regular cleanup of old DAG runs (`airflow db clean`), and using PostgreSQL (not MySQL or SQLite) in production.

---

## 2. DAGs — Directed Acyclic Graphs

### Basic DAG Structure

A DAG file is a Python file that Airflow's scheduler parses repeatedly (every few seconds by default). This means the top-level DAG file code runs frequently — expensive operations at the module level (database queries, API calls) will slow down the scheduler. Keep DAG definition code lightweight; put heavy logic inside your task callables.

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,       # don't wait for previous run to succeed
    'email': ['alerts@example.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,  # 5min, 10min, 20min...
}

with DAG(
    dag_id='daily_etl_pipeline',
    default_args=default_args,
    description='Daily sales ETL pipeline',
    start_date=datetime(2025, 1, 1),
    schedule='0 2 * * *',           # daily at 2am UTC
    catchup=False,                  # don't backfill historical runs
    tags=['etl', 'sales'],
    max_active_runs=1,              # only 1 run at a time
) as dag:
    
    def extract(**context):
        # context includes execution_date, dag, task, etc.
        ds = context['ds']  # execution date as string 'YYYY-MM-DD'
        print(f"Extracting data for {ds}")
        return {"rows_extracted": 50000}
    
    def transform(**context):
        ti = context['task_instance']
        extract_result = ti.xcom_pull(task_ids='extract')
        print(f"Transforming {extract_result['rows_extracted']} rows")
    
    extract_task = PythonOperator(
        task_id='extract',
        python_callable=extract,
    )
    
    transform_task = PythonOperator(
        task_id='transform',
        python_callable=transform,
    )
    
    load_task = BashOperator(
        task_id='load',
        bash_command='echo "Loading data for {{ ds }}"',  # Jinja template
    )
    
    # Task dependencies
    extract_task >> transform_task >> load_task
```

> **💡 Interview tip:** `depends_on_past=True` means a task instance won't run if the same task in the *previous* DAG run didn't succeed. Use this carefully — if a task fails on day 1, all subsequent days are blocked indefinitely. It's useful for append-only pipelines where processing day 2 before day 1 is complete would be wrong, but it's a common source of mysterious DAG stalls.

---

## 3. Operators

### Python and Bash

`PythonOperator` is the workhorse — it calls any Python function. `BashOperator` runs any shell command. The Jinja template `{{ ds }}` in BashOperator is resolved at runtime to the execution date string, making it easy to pass the processing date to scripts.

```python
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

PythonOperator(
    task_id='run_python',
    python_callable=my_function,
    op_kwargs={'param': 'value'},       # keyword args to function
    op_args=['arg1', 'arg2'],           # positional args
)

BashOperator(
    task_id='run_bash',
    bash_command='python /path/to/script.py --date {{ ds }}',
)
```

### AWS Operators

AWS provider operators hide the polling complexity for long-running jobs. Without `wait_for_completion=True`, `GlueJobOperator` would just *trigger* the Glue job and move on — the next task would start immediately even if Glue is still running. With it, the task polls Glue until the job completes (or fails), making the Airflow task duration reflect the actual Glue job duration.

```python
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.operators.s3 import S3CreateObjectOperator
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from airflow.providers.amazon.aws.operators.redshift_sql import RedshiftSQLOperator

# Trigger Glue job and wait for completion
GlueJobOperator(
    task_id='run_glue_etl',
    job_name='my-glue-job',
    job_desc='Daily ETL',
    script_location='s3://bucket/scripts/etl.py',
    s3_bucket='my-bucket',
    iam_role_name='GlueServiceRole',
    create_job_kwargs={'GlueVersion': '4.0', 'WorkerType': 'G.1X', 'NumberOfWorkers': 5},
    script_args={'--input_date': '{{ ds }}'},
    aws_conn_id='aws_default',
    wait_for_completion=True,
)

# Run SQL in Redshift
RedshiftSQLOperator(
    task_id='refresh_summary',
    sql="""
        DELETE FROM daily_sales WHERE date = '{{ ds }}';
        INSERT INTO daily_sales SELECT ... WHERE date = '{{ ds }}';
    """,
    redshift_conn_id='redshift_default',
)
```

### Empty / Dummy Operator (for grouping)

`EmptyOperator` is a no-op — it does nothing but acts as an anchor point for dependencies. Use it to create fan-out (one task triggers many in parallel) and fan-in (many tasks must all complete before proceeding) patterns. It also makes your DAG graph much more readable in the Airflow UI.

```python
from airflow.operators.empty import EmptyOperator

start = EmptyOperator(task_id='start')
end = EmptyOperator(task_id='end')

start >> [task1, task2, task3] >> end  # fan-out then fan-in
```

---

## 4. Sensors

Sensors are a special type of operator designed to *wait* for something to become true. They're critical for event-driven pipelines: instead of scheduling a job at a fixed time and hoping the upstream data has arrived, you use a sensor to wait until the data is actually there.

```python
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.sensors.time_delta import TimeDeltaSensor
from airflow.sensors.sql import SqlSensor

# Wait for S3 file to exist
S3KeySensor(
    task_id='wait_for_source_file',
    bucket_name='my-data-bucket',
    bucket_key='landing/sales/{{ ds }}/data.parquet',
    aws_conn_id='aws_default',
    mode='reschedule',      # reschedule (free up slot) vs poke (hold slot)
    poke_interval=60,       # check every 60 seconds
    timeout=3600,           # fail after 1 hour
)

# Wait for another DAG's task to complete
ExternalTaskSensor(
    task_id='wait_for_upstream_dag',
    external_dag_id='upstream_pipeline',
    external_task_id='final_load',
    allowed_states=['success'],
    execution_date_fn=lambda dt: dt,
    mode='reschedule',
)

# Wait for SQL condition
SqlSensor(
    task_id='wait_for_data',
    conn_id='postgres_default',
    sql="SELECT COUNT(*) FROM raw_orders WHERE date = '{{ ds }}'",
    success=lambda cnt: cnt > 0,
    mode='reschedule',
    poke_interval=300,
)
```

**mode='poke' vs mode='reschedule':**

This is one of the most important operational distinctions in Airflow. Imagine workers as chairs: `poke` mode means a sensor sits in a chair the entire time it's waiting, even if it's just sleeping between checks. `reschedule` mode means the sensor gets up and frees the chair between checks, sitting back down only when it's time to check again. If you have 20 sensors all waiting several hours for S3 files, `poke` mode will consume 20 worker slots for hours, starving other tasks. `reschedule` mode costs essentially zero resources while waiting.

```
poke:       task holds a worker slot while waiting (blocks other tasks from running)
reschedule: task releases worker slot between checks (efficient, preferred for long waits)
```

> **💡 Interview tip:** "What's the difference between poke and reschedule mode in sensors, and when would you use each?" Use `poke` only for very short waits (< 1-2 minutes) where the overhead of rescheduling isn't worth it. Use `reschedule` for everything else — especially sensors that might wait hours for upstream data. Getting this wrong in production is a classic way to run out of worker capacity and have your entire Airflow cluster grind to a halt.

> **🌍 Real world:** A common production issue: a team deploys 50 S3KeySensors in poke mode, each waiting up to 6 hours for daily files. With a worker concurrency of 32, those 50 sensors immediately consume all workers and no actual processing tasks can run. Everything is queued. The fix is `mode='reschedule'` — but understanding *why* this happens requires knowing that each poke-mode sensor holds a worker slot.

---

## 5. Hooks

Hooks are the connection layer — they abstract the details of connecting to external systems (credentials, connection pooling, retry logic) so your task code just calls high-level methods like `get_records()` or `load_file()`. Connection details are stored in Airflow's connection store (encrypted in the metadata DB) and referenced by `conn_id`, not hardcoded.

```python
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.hooks.base import BaseHook

# S3 Hook
s3_hook = S3Hook(aws_conn_id='aws_default')
files = s3_hook.list_keys(bucket_name='my-bucket', prefix='landing/sales/')
s3_hook.download_file(key='path/to/file.csv', bucket_name='my-bucket', local_path='/tmp/')
s3_hook.load_file('/tmp/output.csv', 'output/data.csv', 'my-bucket', replace=True)

# Postgres Hook
pg_hook = PostgresHook(postgres_conn_id='postgres_default')

# Run query
records = pg_hook.get_records("SELECT * FROM orders WHERE date = %s", parameters=['2025-05-21'])

# Get pandas DataFrame
df = pg_hook.get_pandas_df("SELECT * FROM orders LIMIT 100")

# Run SQL
pg_hook.run("UPDATE orders SET status = 'processed' WHERE date = %s", parameters=['2025-05-21'])
```

---

## 6. XComs — Passing Data Between Tasks

XComs (cross-communications) let tasks share small pieces of information — like the S3 path of a file produced by one task, which needs to be consumed by the next. The critical constraint is that XComs are stored in Airflow's metadata database, which is not designed for large payloads. Passing a Pandas DataFrame through XCom will bloat your metadata DB and create performance problems.

```python
# Push value (via return value — auto-push)
def extract(**context):
    data = fetch_data()
    return {"row_count": len(data), "file_path": "s3://..."}
    # this return value is automatically pushed to XCom

# Push value explicitly
def extract(**context):
    ti = context['task_instance']
    ti.xcom_push(key='file_path', value='s3://bucket/file.parquet')

# Pull value
def transform(**context):
    ti = context['task_instance']
    
    # Pull return value (key='return_value')
    extract_result = ti.xcom_pull(task_ids='extract')
    
    # Pull specific key
    file_path = ti.xcom_pull(task_ids='extract', key='file_path')

# IMPORTANT:
# - XComs stored in Airflow metadata DB
# - Keep small! Don't push large DataFrames
# - Use S3 paths, not actual data content
# - Max size: ~64KB (MySQL), ~1GB (PostgreSQL with BLOB backend)
```

> **💡 Interview tip:** "How do you pass data between Airflow tasks?" The correct answer for a senior DE: "XCom for small metadata like file paths, record counts, or status flags. For actual data, write to S3 (or GCS/ADLS) in one task and pass the path via XCom to the next. Never push DataFrames or large result sets through XCom — it bloats the metadata DB." This distinction between passing *references* vs *data* is what separates engineers who've operated Airflow in production from those who haven't.

---

## 7. Variables and Connections

### Variables

Airflow Variables are key-value pairs stored in the metadata DB, accessible from any DAG or task. Use them for configuration that changes between environments (dev/prod bucket names, batch sizes, feature flags) without changing DAG code. Be aware: every `Variable.get()` call makes a database query — don't call it inside task loops.

```python
from airflow.models import Variable

# Get variable (with default)
bucket = Variable.get("data_lake_bucket", default_var="my-default-bucket")

# Get JSON variable
config = Variable.get("etl_config", deserialize_json=True)
# config = {"batch_size": 1000, "max_retries": 3}

# In templates (Jinja)
# bash_command='aws s3 ls {{ var.value.data_lake_bucket }}'
```

### Connections

```python
from airflow.hooks.base import BaseHook

conn = BaseHook.get_connection("my_postgres")
print(conn.host, conn.port, conn.schema, conn.login)

# Better: use provider hooks which handle connections automatically
from airflow.providers.postgres.hooks.postgres import PostgresHook
hook = PostgresHook(postgres_conn_id='my_postgres')
```

---

## 8. Scheduling

### execution_date — The Most Confusing Concept in Airflow

`execution_date` trips up almost everyone learning Airflow. It does NOT mean "the time when this DAG run executed." It means the *start of the time interval* that this run is processing. Think of it as the label on a batch of work, not the timestamp of when the work was done.

For a daily DAG with `schedule='0 2 * * *'`:
- The run that fires at 2am on May 22nd has `execution_date = 2025-05-21`
- It's processing data *for* May 21st
- The actual run time is May 22nd, but `ds` gives you "2025-05-21"

This design makes sense for batch pipelines: you're always processing "yesterday's data" and the execution_date tells you *which* day's data you're processing, not when your job ran.

```python
# Cron expressions
schedule='@daily'       # = '0 0 * * *'  — midnight UTC
schedule='@hourly'      # = '0 * * * *'
schedule='@weekly'      # = '0 0 * * 0'  — Sunday midnight
schedule='@monthly'     # = '0 0 1 * *'  — 1st of month
schedule='0 2 * * *'    # daily at 2am UTC
schedule='0 */6 * * *'  # every 6 hours
schedule='0 9 * * 1-5'  # 9am Mon-Fri

# Timedelta
from datetime import timedelta
schedule=timedelta(hours=6)   # every 6 hours

# Execution date vs schedule date:
# DAG scheduled 2025-05-21 00:00 UTC processes data FOR 2025-05-20
# execution_date = logical date (start of interval, not when it runs)
# ds = execution_date as 'YYYY-MM-DD' string
# data_interval_end = when the interval ends (when you'd expect data available)
```

> **💡 Interview tip:** This is arguably the single most common Airflow interview question: "Explain execution_date." The key points: (1) it's the START of the data interval being processed, (2) it's NOT the time the DAG actually ran, (3) for a daily DAG, execution_date is typically one day behind the actual run date, (4) `ds` is the string form of execution_date in `YYYY-MM-DD` format. Bonus: mention that Airflow 2.2+ introduced `data_interval_start` and `data_interval_end` as clearer names for what execution_date actually represents.

### Catchup and Backfill

`catchup=False` is the setting you almost always want in production. Without it, if your DAG has `start_date=datetime(2024, 1, 1)` and you deploy it today, Airflow will immediately attempt to schedule and run 365+ DAG runs to catch up from the start date to now. This can flood your worker pool, overwhelm external systems, and create chaos.

```python
# catchup=True: Airflow runs all intervals from start_date to now
# catchup=False: only run the next scheduled interval going forward

# Backfill specific date range via CLI
airflow dags backfill daily_etl --start-date 2025-01-01 --end-date 2025-01-31
```

> **🌍 Real world:** A common production disaster: a team creates a DAG with `start_date` set to six months ago (to backfill history) and forgets to set `catchup=False`. When they deploy to production, Airflow immediately queues 180+ DAG runs. The workers are overwhelmed, every other pipeline stalls, and the team scrambles to clear the queue. The fix: always start with `catchup=False` and use `airflow dags backfill` for deliberate historical runs.

---

## 9. Branching

Branching lets you route a DAG run down different execution paths based on runtime conditions. The `BranchPythonOperator` returns the `task_id` (or list of task IDs) to execute; all other branches are marked as *skipped*. The key gotcha is the `trigger_rule` on the downstream "merge" task — the default `all_success` rule would fail if any upstream task is skipped, so you need `none_failed_min_one_success`.

```python
from airflow.operators.python import BranchPythonOperator
from airflow.operators.empty import EmptyOperator

def choose_branch(**context):
    ds = context['ds']
    day_of_week = datetime.strptime(ds, '%Y-%m-%d').weekday()
    
    if day_of_week == 6:  # Sunday
        return 'weekly_report'
    return 'daily_report'

branch = BranchPythonOperator(
    task_id='branch',
    python_callable=choose_branch,
)

daily = PythonOperator(task_id='daily_report', ...)
weekly = PythonOperator(task_id='weekly_report', ...)
end = EmptyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

branch >> [daily, weekly] >> end
# trigger_rule: 'none_failed_min_one_success' — end runs if ANY upstream succeeded
# (not the default 'all_success' which would fail when branch skips one)
```

---

## 10. TaskGroups (Replacing SubDAGs)

`TaskGroup` is Airflow 2.x's answer to SubDAGs — it visually groups related tasks in the UI without the operational complexity of SubDAGs (which required their own DAG runs and had concurrency issues). TaskGroups are purely visual organization; they don't change execution behavior.

```python
from airflow.utils.task_group import TaskGroup

with DAG('pipeline', ...) as dag:
    
    with TaskGroup('extract_group') as extract_group:
        extract_orders = PythonOperator(task_id='extract_orders', ...)
        extract_customers = PythonOperator(task_id='extract_customers', ...)
    
    with TaskGroup('transform_group') as transform_group:
        transform_orders = PythonOperator(task_id='transform_orders', ...)
        transform_customers = PythonOperator(task_id='transform_customers', ...)
    
    load = PythonOperator(task_id='load', ...)
    
    extract_group >> transform_group >> load
```

---

## 11. Dynamic DAGs

When you have a repeating pattern (one task per table, one task per partition, one task per data source), dynamic DAGs eliminate copy-paste. The for-loop approach works in all Airflow versions; the newer `expand()` API (Airflow 2.6+) is cleaner and enables true dynamic task mapping at runtime.

```python
# Generate tasks dynamically (e.g. one task per table)
tables = ['orders', 'customers', 'products', 'inventory']

with DAG('multi_table_etl', ...) as dag:
    start = EmptyOperator(task_id='start')
    end = EmptyOperator(task_id='end')
    
    for table in tables:
        task = PythonOperator(
            task_id=f'load_{table}',
            python_callable=load_table,
            op_kwargs={'table_name': table},
        )
        start >> task >> end

# Airflow 2.6+ — Dynamic Task Mapping (cleaner)
def process(table):
    print(f"Processing {table}")

with DAG('dynamic_mapping', ...) as dag:
    process_task = PythonOperator.partial(
        task_id='process_table',
        python_callable=process,
    ).expand(op_args=[['orders'], ['customers'], ['products']])
```

> **🌍 Real world:** Dynamic task mapping with `expand()` is particularly powerful when the list of items to process isn't known at DAG-write time. You can have a first task that returns a list of S3 keys or table names, and a second task that `expand()`s over that list — the number of parallel tasks is determined at runtime.

---

## 12. Executors

The executor choice has major implications for scalability, isolation, and operational cost. Think of it on a spectrum: LocalExecutor for small/dev setups, CeleryExecutor for traditional scale-out, KubernetesExecutor for cloud-native isolation.

```
LocalExecutor:
- Runs tasks as subprocesses on the same machine as scheduler
- Good for: single-machine, dev/testing, small workloads
- Limitation: bounded by single machine resources

CeleryExecutor:
- Distributed workers via Celery (Redis or RabbitMQ as broker)
- Scale workers horizontally
- Good for: medium-large deployments
- Requires: Redis/RabbitMQ, multiple worker machines

KubernetesExecutor:
- Each task runs in its own Kubernetes Pod
- Perfect isolation (each task gets own image/resources)
- No idle workers — pods spin up/down per task
- Good for: cloud-native, variable workloads, isolation
- Requires: Kubernetes cluster, more ops overhead

AWS MWAA (Managed Workflows for Apache Airflow):
- Fully managed Airflow on AWS
- Automatic scaling, HA, no infra to manage
- Good for: AWS-native, hands-off operations
```

> **💡 Interview tip:** "When would you choose KubernetesExecutor over CeleryExecutor?" KubernetesExecutor wins when: (1) tasks need different Python versions or dependencies (each pod can use a different image), (2) workloads are bursty (no idle workers wasting money), (3) you need strong isolation between tasks. CeleryExecutor wins when: (1) tasks are relatively homogeneous, (2) you need fast task startup (no pod spin-up overhead), (3) your team doesn't have Kubernetes expertise. MWAA wins when you want to eliminate the operational burden of managing Airflow infrastructure entirely.

> **🌍 Real world:** Many AWS-native DE teams run MWAA for the orchestrator itself (managed, no ops) but use GlueJobOperator or ECS operators to kick off the actual compute — so the Airflow workers are just lightweight controllers, and the heavy lifting happens in managed services.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| DAG | Workflow definition — tasks + dependencies, no cycles |
| Scheduler | Parses DAGs, submits ready tasks to executor |
| Executor | HOW tasks run — Local, Celery, Kubernetes |
| execution_date | Logical date (interval start), not actual run time |
| catchup=False | Don't backfill — only run next scheduled interval |
| XCom | Pass small data between tasks — store in metadata DB |
| reschedule mode | Sensor releases slot between polls — use for long waits |
| BranchPython | Conditional routing — skipped tasks handled by trigger_rule |
| TaskGroup | Visual grouping of related tasks in UI |
| MWAA | AWS-managed Airflow — no infra management |
