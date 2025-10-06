# セキュリティロボット強化学習システム - AI実装ガイド

## 🎯 このドキュメントの目的

このガイドは、AI開発アシスタント(Claude Code, GitHub Copilot等)を活用して、セキュリティロボット強化学習システムを段階的に実装するための詳細な指示書です。

**重要:** このドキュメントと親ディレクトリの設計書を組み合わせることで、リポジトリ知識なしでも完全な実装が可能です。

## 📚 前提知識

### 必要な設計書
実装前に以下を熟読してください:
1. `../01_system_architecture_design_standalone.md` - システム全体設計
2. `../02_backend_api_design_standalone.md` - バックエンドAPI詳細
3. `../03_frontend_design_standalone.md` - フロントエンド設計(Nuxt v4 + Vue.js 3)
4. `../04_test_design_standalone.md` - テスト設計(pytest, Vitest, Playwright)
5. `../05_infrastructure_deployment_standalone.md` - インフラ・デプロイメント設計

### 技術要件
- Python 3.12+
- Node.js 20+
- pnpm 9.12.0 (パッケージマネージャー)
- Docker & Docker Compose
- PostgreSQL 15
- Redis 7

## 🏗️ 実装フェーズ

### Phase 1: 環境準備 (Day 1-2)

#### 1.1 リポジトリ初期化

```bash
# バックエンドリポジトリ作成
mkdir security-robot-rl-backend
cd security-robot-rl-backend

# Python環境初期化
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 依存関係ファイル作成
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9
redis==5.0.1
celery==5.3.4
python-multipart==0.0.6
websockets==12.0
torch==2.1.1
stable-baselines3==2.2.1
gymnasium==0.29.1
numpy==1.24.3
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2
EOF

pip install -r requirements.txt
```

```bash
# フロントエンドリポジトリ作成
mkdir security-robot-rl-frontend
cd security-robot-rl-frontend

# Nuxt v4プロジェクト初期化(pnpmを使用)
pnpm dlx nuxi@latest init . --packageManager pnpm

# 追加依存関係インストール(設計書 03_frontend_design_standalone.md 参照)
pnpm add @element-plus/nuxt@latest
pnpm add @pinia/nuxt@latest
pnpm add @vueuse/nuxt@latest
pnpm add chart.js vue-chartjs
pnpm add socket.io-client@^4.8
pnpm add axios@^1.7
pnpm add d3@^7.9

# 開発依存関係インストール
pnpm add -D @playwright/test@^1.49 vitest@^3.0
pnpm add -D eslint@^9.37 stylelint@^16.25 vue-tsc@^2.1
pnpm add -D sass@^1.83
```

#### 1.2 Docker Compose環境構築

```yaml
# docker-compose.yml
version: '3.8'

services:
  # PostgreSQL
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
      POSTGRES_DB: ${DB_NAME:-security_robot_rl}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # バックエンド
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-password}@postgres:5432/${DB_NAME:-security_robot_rl}
      REDIS_URL: redis://redis:6379
      CELERY_BROKER_URL: redis://redis:6379
    volumes:
      - ./backend:/app
      - ./models:/app/models
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Celeryワーカー
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    environment:
      DATABASE_URL: postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-password}@postgres:5432/${DB_NAME:-security_robot_rl}
      CELERY_BROKER_URL: redis://redis:6379
    volumes:
      - ./backend:/app
      - ./models:/app/models
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

  # フロントエンド
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    environment:
      NUXT_PUBLIC_API_BASE_URL: http://localhost:8000
      NUXT_PUBLIC_WS_URL: ws://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev

volumes:
  postgres_data:
```

```dockerfile
# backend/Dockerfile.dev
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

```dockerfile
# frontend/Dockerfile.dev
FROM node:20-alpine

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000

CMD ["pnpm", "run", "dev"]
```

#### 1.3 環境変数設定

```bash
# backend/.env
DATABASE_URL=postgresql://postgres:password@localhost:5432/security_robot_rl
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379

MODELS_DIR=./models
LOGS_DIR=./logs
CHECKPOINTS_DIR=./checkpoints

# CORS設定
CORS_ORIGINS=["http://localhost:3000"]
```

```bash
# frontend/.env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
NUXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Phase 2: バックエンド基盤実装 (Day 3-5)

#### 2.1 ディレクトリ構造作成

```bash
cd backend
mkdir -p app/{core,api/{endpoints,websocket},services,models,ml/{environments,training,utils},tasks,utils}
mkdir -p tests/{api,services,ml}
mkdir -p migrations/versions
touch app/__init__.py
touch app/core/__init__.py
touch app/api/__init__.py
```

#### 2.2 設定管理実装

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """アプリケーション設定"""

    # API設定
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    # データベース
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # ディレクトリ
    MODELS_DIR: str = "./models"
    LOGS_DIR: str = "./logs"
    CHECKPOINTS_DIR: str = "./checkpoints"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

#### 2.3 データベース接続実装

```python
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# エンジン作成
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 接続テスト
    echo=False  # 本番ではFalse
)

# セッションファクトリ
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ベースクラス
Base = declarative_base()

# 依存性注入用
def get_db():
    """データベースセッション提供"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### 2.4 データベースモデル実装

設計書(`02_backend_api_design_standalone.md`の3.2節)のSQLAlchemyモデルをそのまま実装してください。

```python
# app/models/database.py
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class TrainingSession(Base):
    """学習セッションモデル"""
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    algorithm = Column(String(10), nullable=False)
    environment_type = Column(String(20), nullable=False)
    status = Column(String(20), default="created")

    # ... (設計書の完全なモデル定義を使用)

    # テーブル制約
    __table_args__ = (
        CheckConstraint("algorithm IN ('ppo', 'a3c')", name="check_algorithm"),
        CheckConstraint("environment_type IN ('standard', 'enhanced')", name="check_environment_type"),
        CheckConstraint("status IN ('created', 'running', 'paused', 'completed', 'failed')", name="check_status"),
    )
```

#### 2.5 Alembicマイグレーション初期化

```bash
# Alembic初期化
alembic init migrations

# alembic.ini編集
# sqlalchemy.url = postgresql://postgres:password@localhost:5432/security_robot_rl

# migrations/env.py編集
from app.models.database import Base
target_metadata = Base.metadata

# 初回マイグレーション作成
alembic revision --autogenerate -m "Initial schema"

# マイグレーション実行
alembic upgrade head
```

### Phase 3: API実装 (Day 6-8)

#### 3.1 FastAPIアプリケーション初期化

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import training, environment, models, playback
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション
app = FastAPI(
    title="セキュリティロボット強化学習API",
    description="PPO/A3C学習制御・リアルタイム可視化API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ルーター登録
app.include_router(training.router, prefix=f"{settings.API_PREFIX}/training", tags=["training"])
app.include_router(environment.router, prefix=f"{settings.API_PREFIX}/environment", tags=["environment"])
app.include_router(models.router, prefix=f"{settings.API_PREFIX}/models", tags=["models"])
app.include_router(playback.router, prefix=f"{settings.API_PREFIX}/playback", tags=["playback"])

# ヘルスチェック
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "security-robot-rl-backend"}

# 起動イベント
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Security Robot RL Backend API")
    # データベース接続確認等

# 終了イベント
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Security Robot RL Backend API")
```

#### 3.2 Pydanticスキーマ実装

設計書(`02_backend_api_design_standalone.md`の3.3節)のPydanticスキーマをそのまま実装してください。

```python
# app/models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, Dict, Any, List
from datetime import datetime

class TrainingSessionCreate(BaseModel):
    """学習セッション作成リクエスト"""
    # ... (設計書の完全なスキーマ定義を使用)
```

#### 3.3 APIエンドポイント実装

設計書(`02_backend_api_design_standalone.md`の4章)のAPIエンドポイントをそのまま実装してください。

```python
# app/api/endpoints/training.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.schemas import TrainingSessionCreate, TrainingSessionResponse, TrainingMetricsResponse
from app.services.training_service import TrainingService

router = APIRouter()

@router.post("/start", response_model=TrainingSessionResponse, status_code=202)
async def start_training(
    config: TrainingSessionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # ... (設計書の完全な実装を使用)
```

### Phase 4: WebSocket・Celery実装 (Day 9-10)

設計書(`02_backend_api_design_standalone.md`の4.2節および6章)のWebSocket・Celery実装をそのまま実装してください。

### Phase 5: フロントエンド実装 (Day 11-17)

設計書(`03_frontend_design_standalone.md`)のアーキテクチャとコンポーネント定義をそのまま実装してください。

#### 5.1 Nuxt設定

```typescript
// nuxt.config.ts (設計書 3.1節参照)
export default defineNuxtConfig({
  future: {
    compatibilityVersion: 4,
  },

  devtools: { enabled: true },
  ssr: false, // SPA mode

  css: ['~/assets/css/main.css'],

  modules: [
    '@element-plus/nuxt',
    '@pinia/nuxt',
    '@vueuse/nuxt'
  ],

  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
      wsUrl: process.env.NUXT_PUBLIC_WS_URL || 'ws://localhost:8000'
    }
  },

  typescript: {
    strict: true,
    typeCheck: true,
    shim: false
  },

  vite: {
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: '@use "~/assets/styles/variables" as *;'
        }
      }
    }
  },

  compatibilityDate: '2025-01-01'
})
```

#### 5.2 DDD構造実装

設計書(`03_frontend_design_standalone.md`の2.1節)のディレクトリ構造に従ってください:

```
frontend/
├── configs/
│   └── api.ts              # APIエンドポイント定義
├── libs/
│   ├── domains/            # ドメインモデル(TrainingSession, Metrics等)
│   ├── repositories/       # データアクセス層(API呼び出し)
│   ├── entities/           # DTO変換
│   └── utils/              # ユーティリティ
├── composables/            # ビジネスロジック(useTraining, useMetrics等)
├── stores/                 # Piniaストア(グローバル状態)
├── components/             # UIコンポーネント(設計書3.2節参照)
│   ├── training/           # 学習制御コンポーネント
│   ├── visualization/      # 可視化コンポーネント
│   ├── playback/          # プレイバック機能
│   └── common/            # 共通コンポーネント
├── pages/                  # ページコンポーネント
├── assets/
│   └── styles/            # SCSS/BEM記法スタイル
└── tests/                 # Vitest単体テスト
```

#### 5.3 主要コンポーネント実装

設計書(`03_frontend_design_standalone.md`の3.2節)に定義された以下のコンポーネントを実装:

**学習制御UI**:
- `TrainingConfigForm.vue` - 学習パラメータ設定
- `TrainingControlPanel.vue` - 開始/停止/一時停止
- `TrainingStatusDisplay.vue` - リアルタイムステータス

**可視化UI**:
- `RewardChart.vue` - Chart.js報酬グラフ
- `EnvironmentHeatmap.vue` - D3.js環境ヒートマップ
- `MetricsTable.vue` - Element Plus統計テーブル

**プレイバック機能**:
- `PlaybackPlayer.vue` - エピソード再生
- `PlaybackTimeline.vue` - タイムライン操作

```typescript
// configs/api.ts
const API_BASE_URL = process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export const API_ENDPOINTS = {
  training: {
    start: `${API_BASE_URL}/api/v1/training/start`,
    stop: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/stop`,
    pause: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/pause`,
    resume: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/resume`,
    status: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/status`,
    metrics: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/metrics`,
    list: `${API_BASE_URL}/api/v1/training/sessions`
  },
  models: {
    list: `${API_BASE_URL}/api/v1/models`,
    download: (id: number) => `${API_BASE_URL}/api/v1/models/${id}/download`
  },
  playback: {
    list: `${API_BASE_URL}/api/v1/playback`,
    get: (id: number) => `${API_BASE_URL}/api/v1/playback/${id}`
  },
  websocket: `${API_BASE_URL.replace('http', 'ws')}/ws/training`
} as const
```

### Phase 6: テスト実装 (Day 18-20)

設計書(`04_test_design_standalone.md`)のテスト戦略とカバレッジ目標に従って実装してください。

#### 6.1 バックエンドテスト (カバレッジ目標: 90%以上)

```python
# tests/conftest.py (設計書 2.1節参照)
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.main import app
from fastapi.testclient import TestClient

# テスト用DB
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

```python
# tests/api/test_training.py (設計書 2.2節参照)
def test_start_training(client):
    """学習セッション開始API統合テスト"""
    response = client.post("/api/v1/training/start", json={
        "name": "Test PPO",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 1000,
        "env_width": 8,
        "env_height": 8
    })
    assert response.status_code == 202
    data = response.json()
    assert data["name"] == "Test PPO"
    assert data["algorithm"] == "ppo"
    assert data["status"] == "created"

def test_get_training_metrics(client):
    """学習メトリクス取得APIテスト"""
    # 設計書の4.2.2節 統合テストシナリオを参照
    pass
```

設計書(`04_test_design_standalone.md`の2章)に定義された以下のテストカテゴリを実装:
- 単体テスト(環境、学習ロジック、API)
- 統合テスト(API統合、WebSocket通信、Celeryタスク)
- E2Eテスト(学習フロー、プレイバック)

#### 6.2 フロントエンドテスト (カバレッジ目標: 85%以上)

```typescript
// tests/unit/composables/useTraining.spec.ts (設計書 3.2節参照)
import { describe, it, expect, vi } from 'vitest'
import { useTraining } from '~/composables/useTraining'

describe('useTraining', () => {
  it('should start training session', async () => {
    const { startTraining } = useTraining()

    const config = {
      name: 'Test Session',
      algorithm: 'ppo',
      total_timesteps: 1000
    }

    const session = await startTraining(config)
    expect(session.name).toBe('Test Session')
  })

  it('should handle WebSocket updates', async () => {
    // 設計書の3.2.2節 WebSocket通信テストを参照
  })
})
```

```typescript
// tests/e2e/training-workflow.spec.ts (設計書 3.3節参照)
import { test, expect } from '@playwright/test'

test('complete training workflow', async ({ page }) => {
  // 1. 学習設定
  await page.goto('http://localhost:3000')
  await page.fill('[data-testid="training-name"]', 'E2E Test Training')
  await page.selectOption('[data-testid="algorithm"]', 'ppo')

  // 2. 学習開始
  await page.click('[data-testid="start-training"]')
  await expect(page.locator('[data-testid="status"]')).toHaveText('running')

  // 3. リアルタイム更新確認
  await expect(page.locator('[data-testid="episode-count"]')).not.toHaveText('0')

  // 4. 学習停止
  await page.click('[data-testid="stop-training"]')
  await expect(page.locator('[data-testid="status"]')).toHaveText('completed')
})
```

設計書(`04_test_design_standalone.md`の3章)に定義された以下のテストを実装:
- 単体テスト(Composables, Stores, Components)
- E2Eテスト(Playwright: 学習ワークフロー、可視化、プレイバック)

### Phase 7: デプロイメント (Day 21-22)

設計書(`05_infrastructure_deployment_standalone.md`)のインフラ構成と運用手順に従ってください。

#### 7.1 本番環境起動

```bash
# Docker Compose本番環境起動 (設計書 2.1節参照)
docker-compose -f docker-compose.prod.yml up -d

# データベースマイグレーション
docker-compose exec backend alembic upgrade head

# ヘルスチェック
curl http://localhost:8000/health
curl http://localhost:3000

# ログ確認
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f celery-worker
```

#### 7.2 モニタリング設定

設計書(`05_infrastructure_deployment_standalone.md`の4章)のモニタリング戦略を参照:

```bash
# Prometheus起動
docker-compose exec prometheus

# Grafanaダッシュボードアクセス
# http://localhost:3001

# ログ集約(Loki)
docker-compose exec loki
```

#### 7.3 バックアップ・リカバリ

設計書(`05_infrastructure_deployment_standalone.md`の5章)のバックアップ戦略を参照:

```bash
# PostgreSQLバックアップ
docker-compose exec postgres pg_dump -U postgres security_robot_rl > backup.sql

# モデルファイルバックアップ
tar -czf models_backup.tar.gz ./models

# リストア
docker-compose exec -T postgres psql -U postgres security_robot_rl < backup.sql
```

## ✅ 実装チェックリスト

### Phase 1-2: 環境準備・バックエンド基盤
- [ ] Python 3.12+ 仮想環境作成
- [ ] FastAPIアプリケーション起動確認
- [ ] PostgreSQL 15接続成功
- [ ] Redis 7接続成功
- [ ] データベースマイグレーション成功(Alembic)
- [ ] 設計書01, 02のモデル定義完全実装

### Phase 3-4: API・非同期処理
- [ ] APIエンドポイント動作確認(Swagger UI: http://localhost:8000/docs)
- [ ] WebSocket接続テスト(設計書02の4.2節)
- [ ] Celeryワーカー起動確認
- [ ] Celeryタスク実行確認(学習ジョブ)
- [ ] バックエンド単体テスト90%以上カバレッジ(pytest-cov)

### Phase 5: フロントエンド
- [ ] pnpm 9.12.0インストール確認
- [ ] Nuxt v4プロジェクト初期化成功
- [ ] TypeScript strict mode有効化・コンパイル成功
- [ ] Element Plus UIコンポーネント表示確認
- [ ] DDD構造実装(libs/, composables/, stores/)
- [ ] Chart.js/D3.js可視化コンポーネント動作確認
- [ ] API通信確認(axios)
- [ ] WebSocketリアルタイム更新確認(Socket.IO)

### Phase 6: テスト
- [ ] バックエンド単体テスト: 90%以上カバレッジ(設計書04の2.1節)
- [ ] バックエンド統合テスト: 主要データフロー100%(設計書04の2.2節)
- [ ] フロントエンド単体テスト: 85%以上カバレッジ(Vitest, 設計書04の3.2節)
- [ ] E2Eテスト(Playwright): クリティカルパス10個以上(設計書04の3.3節)
- [ ] テスト実行速度: 単体2分以内、統合30秒以内、E2E 5分以内

### Phase 7: デプロイメント・統合
- [ ] Docker Compose全サービス起動(設計書05の2.1節)
- [ ] Nginx リバースプロキシ設定(設計書05の2.2節)
- [ ] 学習セッション作成→実行→完了のフロー確認
- [ ] リアルタイム可視化動作確認
- [ ] Prometheusメトリクス収集確認(設計書05の4章)
- [ ] Grafanaダッシュボード表示確認
- [ ] バックアップ・リカバリ手順確認(設計書05の5章)

### 最終確認
- [ ] 全5つの設計書との整合性確認
- [ ] リポジトリ分断後の独立動作確認
- [ ] ドキュメント整備(README.md, API仕様書)
- [ ] コード品質チェック(ESLint, Black, type hints)

## 🎓 実装のベストプラクティス

### 1. 設計書優先アプローチ
**必ず設計書を先に読んでから実装してください**:
- `01_system_architecture_design_standalone.md` - 全体像理解
- `02_backend_api_design_standalone.md` - API詳細設計
- `03_frontend_design_standalone.md` - フロントエンド設計
- `04_test_design_standalone.md` - テスト戦略
- `05_infrastructure_deployment_standalone.md` - インフラ設計

### 2. 段階的実装
一度にすべてを実装せず、**Phase単位で動作確認**しながら進めてください:
1. Phase完了時に動作確認
2. 次Phaseへ進む前にチェックリスト確認
3. 問題があれば設計書で詳細確認

### 3. テスト駆動開発(TDD)
機能実装と同時にテストを書き、継続的に品質を確保してください:
- **バックエンド**: pytest-cov で90%以上カバレッジ
- **フロントエンド**: Vitest で85%以上カバレッジ
- **E2E**: Playwright でクリティカルパス網羅

### 4. コード品質管理
- **TypeScript**: strict mode有効化、型安全性確保
- **Python**: type hints必須、Black自動フォーマット
- **Linter**: ESLint 9.37+, Stylelint 16.25+適用
- **コミット前**: 必ずテスト実行、カバレッジ確認

### 5. 設計書との整合性維持
実装時に以下を常に確認:
- モデル定義が設計書と一致しているか
- APIエンドポイント仕様が設計書通りか
- コンポーネント構造がDDD設計に従っているか
- テストカバレッジが目標値を満たしているか

### 6. リポジトリ分断対応
このガイドと5つの設計書があれば、**現在のリポジトリ知識なしで完全実装可能**です:
- 設計書は自己完結型(standalone)
- すべての技術仕様・データモデル・API定義を含む
- コード例とテストケースが完備

## 📋 実装完了基準

以下をすべて満たした時点で実装完了とみなします:

1. ✅ 全Phase(1-7)のチェックリスト完了
2. ✅ バックエンドカバレッジ90%以上
3. ✅ フロントエンドカバレッジ85%以上
4. ✅ E2Eテスト10個以上成功
5. ✅ Docker Compose全サービス正常起動
6. ✅ 学習→可視化→プレイバックの完全フロー動作確認
7. ✅ 5つの設計書との整合性100%

このガイドと設計書を組み合わせることで、**リポジトリ知識なしで完全なシステムを実装できます**。
