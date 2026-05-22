# Docker — Complete Notes from Scratch

---

## 1. Containers vs Virtual Machines

The core insight of Docker is that most of the "isolation" you need between applications doesn't actually require running a full operating system. A container is just a process on the host machine, wrapped in a namespace so it can't see other processes, and given a controlled view of the filesystem. This is why containers start in milliseconds and use megabytes of RAM rather than gigabytes.

A useful analogy: a VM is like renting an entire apartment (your own kitchen, living room, walls) — whereas a container is like renting a desk in a co-working space where the building (OS kernel) is shared, but your workspace is isolated.

```
Virtual Machine (VM):
┌─────────────────────────────┐
│  App A    │    App B        │
│  Guest OS │    Guest OS     │
│  (full OS — GBs of overhead)│
├─────────────────────────────┤
│       Hypervisor            │
│       Host OS               │
│       Hardware              │
└─────────────────────────────┘

Container:
┌─────────────────────────────┐
│  App A      │   App B       │
│  (libs/deps)│   (libs/deps) │
├─────────────────────────────┤
│       Docker Engine         │
│       Host OS               │
│       Hardware              │
└─────────────────────────────┘

Key difference:
- VM: full OS per application (heavy, slow to start)
- Container: shares host OS kernel, isolates processes (lightweight, fast)

Container advantages:
- Start in milliseconds (vs minutes for VMs)
- Use MB of memory (vs GB)
- "Works on my machine" problem solved — same env everywhere
- Consistent dev → staging → production
```

> **💡 Interview tip:** Interviewers often ask "what's the difference between a container and a VM?" The answer they want to hear is: containers share the host OS kernel and isolate processes using Linux namespaces and cgroups, while VMs run a full guest OS on a hypervisor. Containers are lighter and faster to start, but share the kernel — which means less isolation than a VM.

> **🌍 Real world:** In data engineering, containers solve the classic dependency hell problem. Your Spark ETL job needs Python 3.10 + specific library versions, your ML model needs Python 3.11 + conflicting versions. Containers let both run on the same server without conflict. Airflow, Spark workers, and Kafka brokers each get their own container with exactly the environment they need.

---

## 2. Docker Architecture

Understanding the difference between an image and a container is foundational — the image is the blueprint (static, read-only), the container is the running instance. Think of a Docker image like a class definition in Python and a container like an instance of that class.

```
Docker Client     — CLI tool you type commands into (docker run, docker build)
Docker Daemon     — background service (dockerd) that manages containers
Docker Registry   — stores images (Docker Hub, ECR, GCR)

Image  — read-only template with your app + dependencies (built from Dockerfile)
Container — running instance of an image (like a process from a program)
```

> **🌍 Real world:** In most data engineering teams, the CI/CD pipeline builds the Docker image on every merge to main, pushes it to ECR (AWS's container registry), and the orchestration system (ECS, EKS, or Airflow's KubernetesPodOperator) pulls and runs it. You, the engineer, define the Dockerfile — the pipeline handles the rest.

---

## 3. Dockerfile

A Dockerfile is a recipe for building an image. Each instruction (`RUN`, `COPY`, `ENV`) creates a new immutable layer on top of the previous one. Docker caches these layers — so if a layer's inputs haven't changed, Docker reuses the cached result rather than rebuilding it. This is why the ORDER of instructions in a Dockerfile has a direct impact on how fast your builds are.

```dockerfile
# Base image (FROM) — always start from an existing image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (separate layer — caches well)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (separate layer — only invalidated when requirements.txt changes)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (invalidated by any code change)
COPY src/ ./src/

# Environment variables with defaults (override at runtime)
ENV APP_ENV=production
ENV PORT=8000

# Expose port (documentation only — doesn't actually publish)
EXPOSE 8000

# Run as non-root user (security best practice)
RUN useradd -m appuser
USER appuser

# CMD — default command when container starts (overridable)
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ENTRYPOINT — fixed command (CMD appended as args)
# ENTRYPOINT ["python"] — then CMD ["-m", "uvicorn", ...] 
# Result: python -m uvicorn ...
```

### Layer Caching — Build Efficiently

This is one of the highest-leverage Dockerfile optimisations. Docker layers are cached based on their inputs. If you COPY your entire source code before running `pip install`, then every single code change — even a one-line fix — will invalidate the pip install layer and force a full re-download of all dependencies. Copy `requirements.txt` first and Docker only re-installs deps when that file actually changes.

```dockerfile
# BAD: copy everything first — code change invalidates ALL layers
COPY . .
RUN pip install -r requirements.txt

# GOOD: copy requirements separately — code change only invalidates last layers
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

> **💡 Interview tip:** "How do you optimise Docker build times?" is a common practical question. The answer: order Dockerfile instructions from least-frequently-changing to most-frequently-changing. System packages change rarely, Python deps change occasionally, application code changes constantly — so put them in that order. Also mention BuildKit parallel builds and `.dockerignore`.

### Multi-stage Build (smaller final image)

A multi-stage build solves the problem of build tools bloating your production image. You compile or install everything in a "builder" stage (which can be hundreds of MB), then copy only the final artifacts into a minimal "runtime" stage. The final image never contains `gcc`, `pip`, or any build scaffolding — only what's needed to run.

Think of it like construction: you use heavy machinery (scaffolding, mixers) to build a house, but the final house you hand over doesn't contain the machinery.

```dockerfile
# Stage 1: builder — install everything
FROM python:3.12 AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# Stage 2: runtime — only copy what's needed
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ ./src/
CMD ["python", "src/main.py"]
# Final image is much smaller (no build tools, no pip cache)
```

> **🌍 Real world:** Multi-stage builds are especially valuable for compiled languages (Go, Rust, Java) where the build image needs a full compiler toolchain but the runtime image needs only the binary. For Python in data engineering, the savings come from excluding pip cache, build tools for C-extension packages (psycopg2, numpy), and test dependencies.

---

## 4. Common Docker Commands

These are the bread-and-butter commands you'll use daily. The key ones to know cold for interviews are `docker run` with its flags, `docker exec -it ... bash` for debugging a running container, and `docker logs -f` for tailing output.

```bash
# Build image
docker build -t my-etl:latest .
docker build -t my-etl:1.0.0 -f Dockerfile.prod .

# Run container
docker run my-etl:latest
docker run -d my-etl:latest                    # detached (background)
docker run -p 8080:8000 my-etl:latest          # port mapping host:container
docker run -e DATABASE_URL=postgresql://... my-etl:latest  # env var
docker run -v /host/data:/app/data my-etl:latest           # bind mount
docker run --name my-etl-container my-etl:latest           # named container
docker run --rm my-etl:latest python -c "print('hello')"   # auto-remove on exit

# Container management
docker ps                      # running containers
docker ps -a                   # all containers (including stopped)
docker stop container-id       # graceful stop (SIGTERM)
docker kill container-id       # immediate stop (SIGKILL)
docker rm container-id         # remove stopped container
docker rm -f container-id      # force remove running container

# Execute command in running container
docker exec -it container-id bash    # interactive shell
docker exec container-id python script.py

# Logs
docker logs container-id
docker logs -f container-id          # follow (like tail -f)
docker logs --tail 100 container-id

# Images
docker images                         # list images
docker pull python:3.12-slim          # download from registry
docker push my-registry/my-app:1.0.0 # push to registry
docker rmi image-id                   # remove image
docker image prune                    # remove dangling images

# Inspect
docker inspect container-id           # detailed JSON config
docker stats                          # live CPU/memory usage
```

> **💡 Interview tip:** Know the difference between `docker stop` and `docker kill`. `stop` sends SIGTERM first (giving the app a chance to clean up gracefully), waits 10 seconds, then sends SIGKILL. For ETL jobs that write to databases or commit Kafka offsets, graceful shutdown matters — you want SIGTERM handling in your Python code (`signal.signal(signal.SIGTERM, handler)`).

---

## 5. Docker Compose

Docker Compose solves the multi-container problem: your data pipeline might need Postgres, Redis, Airflow, and your custom ETL service all running together and able to talk to each other. Compose defines the entire stack in a single YAML file and brings it all up with one command.

Think of `docker-compose.yml` as the blueprint for your local development environment — it's the difference between sending a new team member a 10-step setup guide and a single `docker-compose up`.

```yaml
# docker-compose.yml — multi-container applications

version: '3.8'

services:
  # FastAPI backend
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/mydb
      REDIS_URL: redis://redis:6379
    volumes:
      - ./src:/app/src          # bind mount for hot reload in dev
    depends_on:
      db:
        condition: service_healthy  # wait for DB health check
      redis:
        condition: service_started
    restart: unless-stopped
    networks:
      - app-network

  # PostgreSQL
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data  # named volume (persistent)
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # init script
    ports:
      - "5432:5432"         # expose for local dev (remove in prod)
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app-network

  # Redis
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - app-network

  # Airflow (simplified)
  airflow-webserver:
    image: apache/airflow:2.8.0
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@db/airflow
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    ports:
      - "8080:8080"
    depends_on:
      - db
    command: webserver
    networks:
      - app-network

volumes:
  postgres_data:
  redis_data:

networks:
  app-network:
    driver: bridge
```

```bash
# Compose commands
docker-compose up                    # start all services
docker-compose up -d                 # detached
docker-compose up --build            # rebuild images
docker-compose down                  # stop and remove containers
docker-compose down -v               # also remove volumes (destroys data!)
docker-compose logs -f api           # follow logs for specific service
docker-compose exec api bash         # shell into running service
docker-compose ps                    # status
docker-compose restart api           # restart service
```

> **🌍 Real world:** In data engineering teams, Docker Compose is the standard for local development and integration testing. You'll often see a `docker-compose.yml` that spins up Kafka + Zookeeper + Schema Registry + a local Postgres — giving developers a full replica of the production stack on their laptop. CI pipelines (GitHub Actions) also use Compose to run integration tests.

> **💡 Interview tip:** The `depends_on` with `condition: service_healthy` is important — without it, your app might start before Postgres is ready to accept connections. Always pair it with a `healthcheck` on the dependency. This is a very common gotcha in Compose setups.

---

## 6. Docker Volumes — Data Persistence

By default, everything written inside a container is discarded when the container is removed — containers are ephemeral. Volumes solve this by providing storage that lives outside the container lifecycle. Named volumes are Docker-managed (stored in Docker's own directory on the host), while bind mounts map a specific host directory directly into the container.

The practical rule: use **named volumes** for data you want to persist between restarts (Postgres data, Kafka logs), and **bind mounts** in development for code hot-reload (your app code lives on the host but the container sees it live).

```bash
# Named volumes (managed by Docker, persist between container restarts)
docker volume create my_data
docker run -v my_data:/app/data my-app
# Data survives: container stop/start, container removal (not volume removal)

# Bind mounts (map host directory → container directory)
docker run -v /host/path:/container/path my-app
# Used in dev: edit code on host, container sees changes immediately

# tmpfs (in-memory, not persisted)
docker run --tmpfs /tmp my-app

# Volume commands
docker volume ls
docker volume inspect my_data
docker volume rm my_data
docker volume prune          # remove all unused volumes
```

> **💡 Interview tip:** "How does Postgres data persist when a Docker container restarts?" — named volumes. The container is ephemeral; the volume is not. If you `docker-compose down -v` you'll blow away both containers AND volumes (data loss). `docker-compose down` without `-v` keeps volumes intact. This distinction trips people up constantly.

> **🌍 Real world:** In production, containers almost never use Docker volumes for important data — they use external managed storage (RDS, S3, EFS). Docker volumes are most useful in local dev and CI environments where you need Postgres or Kafka to behave like they have persistent state between test runs.

---

## 7. Docker Networking

Containers on the same Docker network can reach each other by their service name — Docker's built-in DNS resolution handles the rest. This is how `DATABASE_URL: postgresql://db:5432/mydb` works in a Compose file: `db` resolves to the IP of the Postgres container because both are on the same network.

```bash
# Default networks
bridge:  default, containers communicate by container name (on same bridge)
host:    container shares host network (no isolation, highest performance)
none:    no networking

# Create custom network
docker network create my-network

# Connect containers to same network (can resolve by name)
docker run --network my-network --name app my-app
docker run --network my-network --name db postgres:15
# app can now reach db at postgres://db:5432/...

# Port mapping
docker run -p 8080:8000 my-app    # host port 8080 → container port 8000
docker run -p 127.0.0.1:8080:8000 # only bind to localhost
```

> **💡 Interview tip:** Port mapping format is `host:container`. If you do `-p 8080:8000`, you visit `localhost:8080` on your machine and the traffic arrives at port 8000 inside the container. A common mistake is reversing them. Also, `EXPOSE 8000` in a Dockerfile is documentation only — it does NOT publish the port. You need `-p` at runtime to actually expose it to the host.

---

## 8. ETL Job in Docker

For batch ETL jobs (as opposed to long-running services), the container pattern is slightly different: the container starts, runs the job, and exits. You pass configuration as environment variables rather than hardcoding them, making the same image usable across different environments and dates.

```dockerfile
# Dockerfile for a Python ETL job
FROM python:3.12-slim

WORKDIR /etl

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl/ ./etl/
COPY config/ ./config/

# Don't use CMD for batch jobs — specify command at runtime
# Or use CMD as default but allow override:
CMD ["python", "etl/daily_load.py"]
```

```bash
# Run ETL job
docker run \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  -e AWS_ACCESS_KEY_ID="..." \
  -e AWS_SECRET_ACCESS_KEY="..." \
  -e EXECUTION_DATE="2025-05-21" \
  my-etl:1.0.0

# Or pass env file
docker run --env-file .env my-etl:1.0.0
```

> **🌍 Real world:** In Airflow, the `DockerOperator` and `KubernetesPodOperator` both use this pattern — they launch a container with the ETL image, pass the execution date and credentials as environment variables, wait for it to exit, and capture the exit code as success/failure. This is the dominant pattern for production ETL at scale: one immutable image, parameterised at runtime.

---

## 9. Docker + AWS ECR

ECR (Elastic Container Registry) is AWS's managed Docker registry. Every production DE team on AWS has a workflow that builds, tags, and pushes images to ECR, then ECS or EKS pulls them to run. Knowing this workflow cold is table stakes for any AWS-focused DE role.

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/my-etl:1.0.0 .
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/my-etl:1.0.0

# AWS ECS (run containers at scale)
# ECS Fargate — serverless containers (no EC2 management)
# Define: Task Definition (image, CPU, memory, env vars)
# Run as: ECS Service (long-running) or ECS Task (one-off batch job)
```

> **🌍 Real world:** The typical production DE workflow: GitHub Actions CI builds the image, tags it with the git commit SHA (e.g., `my-etl:abc1234`), pushes to ECR, and updates the ECS task definition to use the new image. Airflow's `EcsRunTaskOperator` then triggers that task definition for each DAG run. Immutable image tags (commit SHA, not `latest`) are critical for auditability.

---

## 10. Best Practices

These aren't theoretical — each one comes from a real class of production incidents or security vulnerabilities. Running as non-root prevents container escape exploits. Scanning for vulnerabilities catches CVEs before they hit prod. Using specific tags prevents silent breakage when a base image updates.

```
Security:
- Never store secrets in Dockerfile/image
  → Use env vars at runtime, AWS Secrets Manager, Parameter Store
- Run as non-root user (USER appuser)
- Use specific image tags (python:3.12-slim not python:latest)
- Scan images for vulnerabilities (docker scout, Trivy, Snyk)

Size optimization:
- Start from slim/alpine base images
- Combine RUN commands to reduce layers: RUN cmd1 && cmd2
- Clean up package managers in same layer: && rm -rf /var/lib/apt/lists/*
- Use multi-stage builds for compiled dependencies
- Add .dockerignore (like .gitignore for Docker)

.dockerignore:
__pycache__/
*.pyc
.env
.git/
tests/
*.md
venv/

Build speed:
- Order Dockerfile: rarely-changing → frequently-changing
- COPY requirements.txt first, then code
- Use BuildKit: DOCKER_BUILDKIT=1 docker build ...

Production:
- Immutable tags (1.0.0 not latest) for deployments
- Health checks in Dockerfile or compose
- Resource limits: docker run --memory 512m --cpus 0.5
- Logging to stdout/stderr (not files) — Docker captures them
```

> **💡 Interview tip:** "How do you handle secrets in Docker?" is almost always asked. The wrong answer is `ENV DB_PASSWORD=supersecret` in the Dockerfile (it's baked into the image layer and visible in `docker history`). The right answer: pass secrets as env vars at container runtime from a secrets manager (AWS Secrets Manager, Vault), or use Docker secrets for Swarm/Compose. Never bake credentials into an image.

> **🌍 Real world:** The `.dockerignore` file is often forgotten but matters a lot. Without it, `COPY . .` will copy your `.git` directory (hundreds of MB on large repos), your `venv/` (already installed inside the container, so it's dead weight), and your `.env` file (secrets!). A good `.dockerignore` can cut image build time and size dramatically.

---

## Key Summary

| Concept | Key Point |
|---------|-----------|
| Container | Isolated process sharing host OS — lightweight, fast |
| Image | Read-only template built from Dockerfile |
| FROM | Base image — use slim variants for smaller images |
| Layer caching | Copy requirements before code — expensive layers cache longer |
| COPY vs ADD | COPY preferred — ADD has auto-extract behavior |
| CMD | Default command — overridable at `docker run` |
| ENTRYPOINT | Fixed command — CMD appended as arguments |
| Bind mount | Host dir → container dir — use in dev for hot reload |
| Named volume | Docker-managed — persists across container restarts |
| docker-compose | Multi-container orchestration — dev/test environments |
| Non-root user | Security — add USER instruction |
| Multi-stage | Build in one stage, copy artifacts to slim runtime stage |
| ECR | AWS container registry — push/pull for ECS/Fargate |
