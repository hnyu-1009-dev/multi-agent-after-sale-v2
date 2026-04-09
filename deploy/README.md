# Docker Deployment Guide

This directory now contains the deployment layout for the standalone next version of the project.

## Files

- `docker-compose.yml`: build images from the current source tree and run them locally
- `docker-compose.acr.yml`: pull prebuilt images from a registry and run them on the target host
- `deploy/docker/api.Dockerfile`: main application image
- `deploy/docker/knowledge.Dockerfile`: knowledge service image
- `deploy/docker/web.Dockerfile`: frontend + Nginx image
- `deploy/nginx/site.conf`: gateway config for SPA routing, API proxying, and SSE passthrough
- `deploy/env/*.example`: environment templates

## Runtime services

- `core-db`: MySQL 8.0
- `core-api`: main FastAPI service on container port `8080`
- `retrieval-api`: knowledge FastAPI service on container port `8081`
- `edge-web`: Nginx gateway and frontend on container port `80`

## 1. Prepare env files

Copy the templates:

```bash
cp deploy/env/db.env.example deploy/env/db.env
cp deploy/env/core-api.env.example deploy/env/core-api.env
cp deploy/env/kb-api.env.example deploy/env/kb-api.env
```

If you deploy with prebuilt registry images, also copy:

```bash
cp deploy/env/images.env.example deploy/env/images.env
```

## 2. Local source build

Run from the repository root:

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8088
```

If you want a different exposed port:

```bash
PUBLIC_HTTP_PORT=9090 docker compose up -d --build
```

## 3. Registry / ACR deployment

Build and push images from a machine with Docker build access:

```bash
docker build -f deploy/docker/api.Dockerfile -t <registry>/after-sale-next-core-api:latest .
docker build -f deploy/docker/knowledge.Dockerfile -t <registry>/after-sale-next-kb-api:latest .
docker build -f deploy/docker/web.Dockerfile -t <registry>/after-sale-next-web:latest .
docker push <registry>/after-sale-next-core-api:latest
docker push <registry>/after-sale-next-kb-api:latest
docker push <registry>/after-sale-next-web:latest
```

Then on the target host:

```bash
docker login <registry>
docker compose --env-file deploy/env/images.env -f docker-compose.acr.yml up -d
```

## 4. Useful commands

```bash
docker compose ps
docker compose logs -f
docker compose logs -f core-api
docker compose logs -f retrieval-api
docker compose logs -f edge-web
docker compose down
docker compose down -v
```

## 5. Persistence

- MySQL data: named volume `core_db_data`
- Knowledge vectors: named volume `kb_vector_data`
- Knowledge workspace: named volume `kb_workspace`
- Legacy JSON memories: mounted read-only from `backend/app/user_memories` for one-way migration into MySQL memory storage
