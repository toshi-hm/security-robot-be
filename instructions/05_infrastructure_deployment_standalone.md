# インフラ・デプロイメント・運用設計書 - セキュリティロボット強化学習システム

## 1. インフラストラクチャ概要

### 1.1 インフラ設計方針

**対象環境**: ローカル開発・研究用途(単独使用者想定)

**設計原則**:
- Docker Composeによるコンテナオーケストレーション
- 開発環境と本番環境の構成統一
- 環境変数による設定外部化
- ボリュームマウントによるデータ永続化
- ヘルスチェックによる自動復旧

### 1.2 システム構成図

```
┌─────────────────────────────────────────────────────┐
│ Host Machine (Development/Research)                 │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Docker Compose Orchestration                  │  │
│  │                                               │  │
│  │  ┌────────────────┐    ┌─────────────────┐  │  │
│  │  │  Frontend      │    │  Backend        │  │  │
│  │  │  (Nuxt SSR)    │◄───┤  (FastAPI)      │  │  │
│  │  │  Port: 3000    │    │  Port: 8000     │  │  │
│  │  └────────────────┘    └─────────────────┘  │  │
│  │         │                      │             │  │
│  │         │                      ├─────────────┤  │
│  │         │              ┌───────▼───────┐     │  │
│  │         │              │  PostgreSQL   │     │  │
│  │         │              │  Port: 5432   │     │  │
│  │         │              └───────────────┘     │  │
│  │         │                      │             │  │
│  │         │              ┌───────▼───────┐     │  │
│  │         │              │  Redis        │     │  │
│  │         │              │  Port: 6379   │     │  │
│  │         │              └───────────────┘     │  │
│  │         │                      │             │  │
│  │  ┌──────▼──────────────────────▼───────┐    │  │
│  │  │  Nginx Reverse Proxy              │    │  │
│  │  │  Port: 80/443                     │    │  │
│  │  └──────────────────────────────────┘    │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ Volume Mounts (Data Persistence)         │  │
│  │  - postgres_data/                        │  │
│  │  - redis_data/                           │  │
│  │  - models/                               │  │
│  │  - logs/                                 │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## 2. Docker Compose設計

### 2.1 完全なdocker-compose.yml

```yaml
version: '3.9'

services:
  # PostgreSQL データベース
  postgres:
    image: postgres:15-alpine
    container_name: security-robot-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-security_robot_rl}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --locale=C"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - app-network

  # Redis (タスクキュー・キャッシュ)
  redis:
    image: redis:7-alpine
    container_name: security-robot-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    networks:
      - app-network

  # FastAPI バックエンド
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-development}
    container_name: security-robot-backend
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-security_robot_rl}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - models_data:/app/models
      - logs_data:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    restart: unless-stopped
    networks:
      - app-network

  # Celery Worker (バックグラウンドタスク)
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-development}
    container_name: security-robot-celery-worker
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-security_robot_rl}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./backend:/app
      - models_data:/app/models
      - logs_data:/app/logs
    depends_on:
      - redis
      - postgres
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
    restart: unless-stopped
    networks:
      - app-network

  # Nuxt フロントエンド
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-development}
    container_name: security-robot-frontend
    environment:
      - NUXT_PUBLIC_API_BASE_URL=http://backend:8000
      - NUXT_PUBLIC_WS_URL=ws://backend:8000
      - NODE_ENV=${NODE_ENV:-development}
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.nuxt
    depends_on:
      - backend
    command: npm run dev
    restart: unless-stopped
    networks:
      - app-network

  # Nginx リバースプロキシ (本番用)
  nginx:
    image: nginx:alpine
    container_name: security-robot-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    restart: unless-stopped
    networks:
      - app-network
    profiles:
      - production

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  models_data:
    driver: local
  logs_data:
    driver: local

networks:
  app-network:
    driver: bridge
```

### 2.2 環境変数設定 (.env)

```bash
# .env (開発環境)

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_dev_password
POSTGRES_DB=security_robot_rl_dev

# Redis
REDIS_PASSWORD=

# Application
ENVIRONMENT=development
LOG_LEVEL=DEBUG
BUILD_TARGET=development
NODE_ENV=development

# Backend
DATABASE_URL=postgresql://postgres:postgres_dev_password@postgres:5432/security_robot_rl_dev
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Frontend
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
NUXT_PUBLIC_WS_URL=ws://localhost:8000
```

```bash
# .env.production (本番環境)

# Database
POSTGRES_USER=security_robot_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD_SECRET}
POSTGRES_DB=security_robot_rl_prod

# Redis
REDIS_PASSWORD=${REDIS_PASSWORD_SECRET}

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
BUILD_TARGET=production
NODE_ENV=production

# Backend
DATABASE_URL=postgresql://security_robot_user:${POSTGRES_PASSWORD_SECRET}@postgres:5432/security_robot_rl_prod
REDIS_URL=redis://:${REDIS_PASSWORD_SECRET}@redis:6379/0
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD_SECRET}@redis:6379/1
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD_SECRET}@redis:6379/2

# Frontend
NUXT_PUBLIC_API_BASE_URL=https://api.example.com
NUXT_PUBLIC_WS_URL=wss://api.example.com
```

## 3. Dockerfile設計

### 3.1 バックエンド Dockerfile

```dockerfile
# backend/Dockerfile

# ベースイメージ
FROM python:3.12-slim as base

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# uv インストール
RUN pip install --no-cache-dir uv

# 依存関係のみコピー(レイヤーキャッシュ最適化)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 開発環境ステージ
FROM base as development

# ソースコード全体コピー
COPY . .

# ホットリロード用
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=development

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# 本番環境ステージ
FROM base as production

# 本番用依存関係のみ
RUN uv sync --frozen --no-dev

# ソースコードコピー
COPY . .

# 非rootユーザー作成
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 3.2 フロントエンド Dockerfile

```dockerfile
# frontend/Dockerfile

# ベースイメージ
FROM node:20-alpine as base

WORKDIR /app

# 依存関係のみコピー(レイヤーキャッシュ最適化)
COPY package*.json ./
RUN npm ci

# 開発環境ステージ
FROM base as development

# ソースコード全体コピー
COPY . .

ENV NODE_ENV=development

EXPOSE 3000

CMD ["npm", "run", "dev"]

# ビルドステージ
FROM base as builder

COPY . .

ENV NODE_ENV=production
RUN npm run build

# 本番環境ステージ
FROM node:20-alpine as production

WORKDIR /app

# ビルド成果物のみコピー
COPY --from=builder /app/.output ./.output
COPY --from=builder /app/package*.json ./

# 本番用依存関係のみ
RUN npm ci --only=production

# 非rootユーザー
RUN addgroup -g 1000 appuser && adduser -D -u 1000 -G appuser appuser
USER appuser

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
```

### 3.3 Nginx設定

```nginx
# nginx/nginx.conf

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    include /etc/nginx/conf.d/*.conf;
}
```

```nginx
# nginx/conf.d/default.conf

# アップストリーム定義
upstream backend_api {
    server backend:8000;
}

upstream frontend_app {
    server frontend:3000;
}

# HTTPサーバー
server {
    listen 80;
    server_name localhost;

    client_max_body_size 100M;

    # フロントエンド(Nuxt)
    location / {
        proxy_pass http://frontend_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # バックエンドAPI
    location /api/ {
        proxy_pass http://backend_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS設定
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;

        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://backend_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocketタイムアウト設定
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # 静的ファイル(モデルダウンロード等)
    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

## 4. デプロイメント手順

### 4.1 初回セットアップ

```bash
# 1. リポジトリクローン
git clone https://github.com/your-org/security-robot-rl.git
cd security-robot-rl

# 2. 環境変数設定
cp .env.example .env
# .envを編集してパスワード等を設定

# 3. Docker Composeでビルド
docker-compose build

# 4. データベースマイグレーション
docker-compose run --rm backend uv run alembic upgrade head

# 5. 初期データ投入(オプション)
docker-compose run --rm backend uv run python scripts/seed_data.py

# 6. すべてのサービス起動
docker-compose up -d

# 7. ログ確認
docker-compose logs -f

# 8. ヘルスチェック
curl http://localhost:8000/health
curl http://localhost:3000
```

### 4.2 アプリケーション更新

```bash
# 1. 最新コードを取得
git pull origin main

# 2. 依存関係更新
docker-compose build --no-cache

# 3. データベースマイグレーション
docker-compose run --rm backend uv run alembic upgrade head

# 4. サービス再起動
docker-compose down
docker-compose up -d

# 5. 動作確認
docker-compose ps
docker-compose logs -f backend frontend
```

### 4.3 ロールバック手順

```bash
# 1. 以前のバージョンに戻す
git checkout <previous-commit-hash>

# 2. データベースをロールバック
docker-compose run --rm backend uv run alembic downgrade -1

# 3. サービス再起動
docker-compose down
docker-compose up -d --build
```

## 5. 運用管理

### 5.1 ログ管理

#### ログ出力先

```
logs/
├── backend/
│   ├── app.log           # アプリケーションログ
│   ├── uvicorn.log       # Uvicornサーバーログ
│   └── celery.log        # Celeryワーカーログ
├── frontend/
│   └── nuxt.log          # Nuxtログ
├── nginx/
│   ├── access.log        # アクセスログ
│   └── error.log         # エラーログ
└── postgres/
    └── postgresql.log    # PostgreSQLログ
```

#### ログローテーション設定

```bash
# /etc/logrotate.d/security-robot-rl

/path/to/project/logs/**/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        docker-compose kill -s USR1 backend frontend nginx
    endscript
}
```

### 5.2 バックアップ戦略

#### データベースバックアップ

```bash
#!/bin/bash
# scripts/backup_postgres.sh

BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="security_robot_rl_${TIMESTAMP}.sql.gz"

mkdir -p ${BACKUP_DIR}

docker-compose exec -T postgres pg_dump -U postgres security_robot_rl | gzip > ${BACKUP_DIR}/${BACKUP_FILE}

# 7日以上古いバックアップを削除
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}"
```

#### モデルファイルバックアップ

```bash
#!/bin/bash
# scripts/backup_models.sh

BACKUP_DIR="/backups/models"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="models_${TIMESTAMP}.tar.gz"

mkdir -p ${BACKUP_DIR}

tar -czf ${BACKUP_DIR}/${BACKUP_FILE} -C models .

# 30日以上古いバックアップを削除
find ${BACKUP_DIR} -name "*.tar.gz" -mtime +30 -delete

echo "Model backup completed: ${BACKUP_FILE}"
```

#### 自動バックアップ(cron)

```bash
# crontab -e

# 毎日3時にデータベースバックアップ
0 3 * * * /path/to/project/scripts/backup_postgres.sh >> /var/log/backup_postgres.log 2>&1

# 毎週日曜4時にモデルバックアップ
0 4 * * 0 /path/to/project/scripts/backup_models.sh >> /var/log/backup_models.log 2>&1
```

### 5.3 モニタリング

#### ヘルスチェックエンドポイント

```python
# app/api/endpoints/health.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.redis_client import get_redis

router = APIRouter()

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    システムヘルスチェック

    確認項目:
    - APIサーバーの稼働
    - データベース接続
    - Redis接続
    """
    health_status = {
        "status": "healthy",
        "components": {}
    }

    # データベース確認
    try:
        db.execute("SELECT 1")
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = f"unhealthy: {str(e)}"

    # Redis確認
    try:
        redis = get_redis()
        redis.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"

    return health_status
```

#### リソース監視スクリプト

```bash
#!/bin/bash
# scripts/monitor_resources.sh

echo "=== Docker Container Resource Usage ==="
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

echo ""
echo "=== Disk Usage ==="
df -h | grep -E "Filesystem|/dev/"

echo ""
echo "=== PostgreSQL Database Size ==="
docker-compose exec postgres psql -U postgres -c "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) AS size FROM pg_database ORDER BY pg_database_size(pg_database.datname) DESC;"

echo ""
echo "=== Redis Memory Info ==="
docker-compose exec redis redis-cli INFO memory | grep -E "used_memory_human|used_memory_peak_human"
```

### 5.4 トラブルシューティング

#### よくある問題と対処法

**問題1: バックエンドが起動しない**

```bash
# 原因調査
docker-compose logs backend

# データベース接続確認
docker-compose exec postgres psql -U postgres -c "\l"

# 環境変数確認
docker-compose config | grep DATABASE_URL

# 解決策: コンテナ再構築
docker-compose down
docker-compose up -d --build backend
```

**問題2: WebSocket接続エラー**

```bash
# 原因調査
docker-compose logs nginx backend

# Nginx設定確認
docker-compose exec nginx nginx -t

# 解決策: Nginx再起動
docker-compose restart nginx
```

**問題3: Celeryタスクが実行されない**

```bash
# Celeryワーカー状態確認
docker-compose exec celery-worker celery -A app.tasks.celery_app inspect active

# Redis接続確認
docker-compose exec redis redis-cli ping

# 解決策: Celeryワーカー再起動
docker-compose restart celery-worker
```

**問題4: データベースマイグレーションエラー**

```bash
# 現在のマイグレーション状態確認
docker-compose run --rm backend uv run alembic current

# マイグレーション履歴確認
docker-compose run --rm backend uv run alembic history

# 解決策: 手動でマイグレーション実行
docker-compose run --rm backend uv run alembic upgrade head
```

## 6. CI/CD統合

### 6.1 GitHub Actions設定

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        pip install uv
        uv sync

    - name: Run tests
      run: uv run pytest --cov --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379/0

    - name: Upload coverage
      uses: codecov/codecov-action@v3

  frontend-test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '20'

    - name: Install dependencies
      run: npm ci
      working-directory: ./frontend

    - name: Run tests
      run: npm run test:coverage
      working-directory: ./frontend

    - name: Upload coverage
      uses: codecov/codecov-action@v3

  build-docker:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]

    steps:
    - uses: actions/checkout@v4

    - name: Build Docker images
      run: docker-compose build

    - name: Test Docker Compose
      run: |
        docker-compose up -d
        sleep 30
        curl -f http://localhost:8000/health || exit 1
        curl -f http://localhost:3000 || exit 1
        docker-compose down
```

この設計書により、リポジトリを知らない開発者でもインフラ構築・デプロイ・運用を実施できます。
