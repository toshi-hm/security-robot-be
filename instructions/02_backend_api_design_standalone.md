# バックエンドAPI設計仕様書 - 自己完結版

## 1. バックエンドAPI概要

### 1.1 技術スタックと選定理由

**コア技術:**
- **FastAPI 0.104+**: 高性能非同期Webフレームワーク、自動OpenAPIドキュメント生成、型ヒント活用
- **Python 3.12**: 最新の言語機能、パフォーマンス改善
- **Uvicorn**: ASGI対応の高速サーバー
- **Pydantic 2.5**: データバリデーションとシリアライゼーション、TypeScript連携

**データベース:**
- **PostgreSQL 15**: エンタープライズグレードRDBMS、JSONB型対応
- **SQLAlchemy 2.0**: ORM、非同期対応
- **Alembic**: データベースマイグレーション管理

**非同期処理:**
- **Celery 5.3**: 分散タスクキュー
- **Redis 7**: メッセージブローカー、キャッシュ、Pub/Sub

**強化学習:**
- **PyTorch 2.1**: 深層学習フレームワーク
- **Stable-Baselines3 2.2**: PPO実装
- **Gymnasium 0.29**: 強化学習環境インターフェース

**選定理由:**
- FastAPIは非同期処理とOpenAPI自動生成により開発効率向上
- PostgreSQLは複雑なクエリとJSON型のサポート
- Celeryは長時間実行タスク(学習)のバックグラウンド処理
- PyTorchは研究分野での標準、柔軟性が高い

### 1.2 アーキテクチャパターン

**レイヤー構造:**

```
┌────────────────────────────────────┐
│  API Layer (FastAPI Endpoints)    │  ← HTTP/WebSocketリクエスト処理
├────────────────────────────────────┤
│  Service Layer (Business Logic)   │  ← ビジネスロジック実装
├────────────────────────────────────┤
│  Repository Layer (Data Access)   │  ← データアクセス抽象化
├────────────────────────────────────┤
│  Model Layer (ORM/Schema)          │  ← データ構造定義
├────────────────────────────────────┤
│  ML Layer (Reinforcement Learning)│  ← 強化学習エンジン
└────────────────────────────────────┘
```

**依存性注入パターン:**

```python
# FastAPIの依存性注入を活用
from fastapi import Depends
from sqlalchemy.orm import Session

# データベースセッション提供
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# エンドポイントでの使用
@router.get("/training/{session_id}")
async def get_session(
    session_id: int,
    db: Session = Depends(get_db)  # 自動注入
):
    service = TrainingService(db)
    return service.get_session(session_id)
```

## 2. ディレクトリ構造と各モジュールの責務

```
backend/
├── app/
│   ├── main.py                      # アプリケーションエントリーポイント
│   │   - FastAPIインスタンス生成
│   │   - CORS設定
│   │   - ルーター登録
│   │   - ライフサイクルイベント(startup/shutdown)
│   │
│   ├── core/                        # コア設定モジュール
│   │   ├── config.py                # 環境変数・設定管理
│   │   │   - Pydantic Settingsで型安全な設定
│   │   │   - DATABASE_URL, REDIS_URL等の環境変数
│   │   │
│   │   ├── database.py              # データベース接続管理
│   │   │   - SQLAlchemyエンジン設定
│   │   │   - 接続プール管理
│   │   │   - セッション生成ファクトリ
│   │   │
│   │   └── redis_client.py          # Redis接続管理
│   │       - Redis接続プール
│   │       - Pub/Subクライアント
│   │
│   ├── api/                         # APIエンドポイント
│   │   ├── deps.py                  # 共通依存性
│   │   │   - get_db(): DBセッション提供
│   │   │   - get_redis(): Redisクライアント提供
│   │   │
│   │   ├── endpoints/               # RESTful APIエンドポイント
│   │   │   ├── training.py          # 学習制御API
│   │   │   │   - POST /start: 学習開始
│   │   │   │   - POST /{id}/stop: 学習停止
│   │   │   │   - GET /{id}/status: 状態取得
│   │   │   │   - GET /{id}/metrics: メトリクス取得
│   │   │   │
│   │   │   ├── environment.py       # 環境制御API
│   │   │   │   - GET /state: 環境状態取得
│   │   │   │   - POST /reset: 環境リセット
│   │   │   │   - POST /action: アクション実行(デモモード)
│   │   │   │
│   │   │   ├── models.py            # モデル管理API
│   │   │   │   - GET /list: モデル一覧
│   │   │   │   - POST /upload: モデルアップロード
│   │   │   │   - GET /{filename}/download: ダウンロード
│   │   │   │
│   │   │   └── playback.py          # プレイバックAPI
│   │   │       - GET /sessions: セッション一覧
│   │   │       - GET /{id}/frames: フレームデータ取得
│   │   │
│   │   └── websocket/               # WebSocket通信
│   │       ├── connection_manager.py # 接続管理
│   │       │   - connect/disconnect処理
│   │       │   - ブロードキャスト機能
│   │       │   - セッション別接続管理
│   │       │
│   │       └── training_events.py   # 学習進捗配信
│   │           - /ws/training/{session_id}エンドポイント
│   │           - 進捗イベント配信
│   │
│   ├── services/                    # ビジネスロジック層
│   │   ├── training_service.py      # 学習管理サービス
│   │   │   - create_session(): セッション作成
│   │   │   - start_training(): 学習開始(Celeryタスク起動)
│   │   │   - stop_training(): 学習停止
│   │   │   - get_metrics(): メトリクス取得
│   │   │
│   │   ├── environment_service.py   # 環境管理サービス
│   │   │   - create_environment(): 環境インスタンス生成
│   │   │   - reset_environment(): 環境リセット
│   │   │   - execute_action(): アクション実行
│   │   │
│   │   └── model_service.py         # モデル管理サービス
│   │       - list_models(): モデル一覧取得
│   │       - save_model(): モデル保存
│   │       - load_model(): モデルロード
│   │
│   ├── models/                      # データモデル
│   │   ├── database.py              # SQLAlchemyモデル
│   │   │   - TrainingSession: 学習セッション
│   │   │   - TrainingMetrics: 学習メトリクス
│   │   │   - EnvironmentState: 環境状態スナップショット
│   │   │
│   │   └── schemas.py               # Pydanticスキーマ
│   │       - TrainingSessionCreate: 作成リクエスト
│   │       - TrainingSessionResponse: レスポンス
│   │       - TrainingMetricsResponse: メトリクスレスポンス
│   │
│   ├── ml/                          # 強化学習エンジン
│   │   ├── environments/
│   │   │   ├── base.py              # 基底環境クラス
│   │   │   ├── standard.py          # 標準環境実装
│   │   │   └── enhanced.py          # 拡張環境実装
│   │   │
│   │   ├── training/
│   │   │   ├── base_trainer.py      # トレーナー基底クラス
│   │   │   ├── ppo_trainer.py       # PPO学習ロジック
│   │   │   └── a3c_trainer.py       # A3C学習ロジック
│   │   │
│   │   └── utils/
│   │       ├── callbacks.py         # 学習コールバック
│   │       └── checkpoints.py       # チェックポイント管理
│   │
│   └── tasks/                       # Celeryタスク
│       ├── celery_app.py            # Celeryアプリ設定
│       └── training_tasks.py        # 学習バックグラウンドタスク
│
├── tests/                           # テストスイート
│   ├── conftest.py                  # pytest設定・フィクスチャ
│   ├── api/                         # APIテスト
│   ├── services/                    # サービステスト
│   └── ml/                          # ML層テスト
│
├── migrations/                      # Alembicマイグレーション
│   └── versions/
│
├── docker/
│   ├── Dockerfile                   # 本番用
│   └── Dockerfile.dev               # 開発用
│
├── pyproject.toml                   # プロジェクト設定
├── requirements.txt                 # 依存関係
└── .env.example                     # 環境変数サンプル
```

## 3. データベース設計

### 3.1 テーブル定義

**TrainingSessionテーブル:**

```sql
CREATE TABLE training_sessions (
    -- 主キー
    id SERIAL PRIMARY KEY,

    -- 基本情報
    name VARCHAR(255) NOT NULL,
    algorithm VARCHAR(10) NOT NULL CHECK (algorithm IN ('ppo', 'a3c')),
    environment_type VARCHAR(20) NOT NULL CHECK (environment_type IN ('standard', 'enhanced')),
    status VARCHAR(20) NOT NULL DEFAULT 'created'
        CHECK (status IN ('created', 'running', 'paused', 'completed', 'failed')),

    -- 学習パラメータ
    total_timesteps INTEGER NOT NULL CHECK (total_timesteps > 0),
    current_timestep INTEGER DEFAULT 0 CHECK (current_timestep >= 0),
    episodes_completed INTEGER DEFAULT 0 CHECK (episodes_completed >= 0),

    -- 環境設定
    env_width INTEGER DEFAULT 8 CHECK (env_width >= 3 AND env_width <= 50),
    env_height INTEGER DEFAULT 8 CHECK (env_height >= 3 AND env_height <= 50),

    -- 報酬パラメータ(拡張環境用)
    coverage_weight FLOAT DEFAULT 1.5 CHECK (coverage_weight >= 0),
    exploration_weight FLOAT DEFAULT 3.0 CHECK (exploration_weight >= 0),
    diversity_weight FLOAT DEFAULT 2.0 CHECK (diversity_weight >= 0),

    -- 追加パラメータ
    learning_rate FLOAT DEFAULT 0.0003,
    batch_size INTEGER DEFAULT 64,
    num_workers INTEGER DEFAULT 1,  -- A3C用

    -- ファイルパス
    model_path VARCHAR(512),
    log_path VARCHAR(512),

    -- 設定全体(JSONB)
    config JSONB,

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- インデックス
    INDEX idx_status (status),
    INDEX idx_algorithm (algorithm),
    INDEX idx_created_at (created_at DESC)
);

-- 例データ
INSERT INTO training_sessions (
    name, algorithm, environment_type, total_timesteps,
    env_width, env_height, config
) VALUES (
    '実験1_PPO_標準環境',
    'ppo',
    'standard',
    50000,
    20,
    20,
    '{"description": "基本性能測定", "notes": "ベースライン実験"}'::jsonb
);
```

**TrainingMetricsテーブル:**

```sql
CREATE TABLE training_metrics (
    -- 主キー
    id SERIAL PRIMARY KEY,

    -- 外部キー
    session_id INTEGER NOT NULL
        REFERENCES training_sessions(id) ON DELETE CASCADE,

    -- メトリクス
    timestep INTEGER NOT NULL CHECK (timestep >= 0),
    episode INTEGER CHECK (episode >= 0),
    reward FLOAT NOT NULL,
    loss FLOAT,

    -- 環境固有メトリクス
    coverage_ratio FLOAT CHECK (coverage_ratio >= 0 AND coverage_ratio <= 1),
    exploration_score FLOAT CHECK (exploration_score >= 0 AND exploration_score <= 1),
    threat_level_avg FLOAT CHECK (threat_level_avg >= 0 AND threat_level_avg <= 1),

    -- 追加メトリクス(JSONB)
    additional_metrics JSONB,

    -- タイムスタンプ
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- インデックス
    INDEX idx_session_timestep (session_id, timestep),
    INDEX idx_session_timestamp (session_id, timestamp DESC),
    UNIQUE (session_id, timestep)
);

-- 例データ
INSERT INTO training_metrics (
    session_id, timestep, episode, reward, loss,
    coverage_ratio, exploration_score, threat_level_avg
) VALUES
    (1, 1000, 25, 45.2, 0.034, 0.72, 0.58, 0.35),
    (1, 2000, 50, 52.8, 0.028, 0.81, 0.65, 0.28),
    (1, 3000, 75, 58.3, 0.022, 0.87, 0.71, 0.22);
```

**EnvironmentStateテーブル:**

```sql
CREATE TABLE environment_states (
    -- 主キー
    id SERIAL PRIMARY KEY,

    -- 外部キー
    session_id INTEGER NOT NULL
        REFERENCES training_sessions(id) ON DELETE CASCADE,

    -- ステップ情報
    episode INTEGER NOT NULL,
    step INTEGER NOT NULL CHECK (step >= 0),

    -- ロボット状態
    robot_x INTEGER NOT NULL,
    robot_y INTEGER NOT NULL,
    robot_orientation INTEGER NOT NULL CHECK (robot_orientation >= 0 AND robot_orientation <= 3),

    -- 環境状態(JSONB)
    threat_grid JSONB NOT NULL,
    -- 例: [[0.2, 0.5, 0.3], [0.1, 0.8, 0.4], ...]

    coverage_map JSONB,
    -- 例: [[0, 1, 2], [1, 0, 1], ...] (訪問回数)

    suspicious_objects JSONB,
    -- 例: [{"x": 3, "y": 5, "level": 0.8, "spawn_time": 120}]

    -- 行動情報
    action_taken INTEGER CHECK (action_taken >= 0 AND action_taken <= 3),
    reward_received FLOAT,

    -- タイムスタンプ
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- インデックス
    INDEX idx_session_episode_step (session_id, episode, step),
    UNIQUE (session_id, episode, step)
);
```

### 3.2 SQLAlchemyモデル実装

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

class TrainingSession(Base):
    """学習セッションモデル"""
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    algorithm = Column(String(10), nullable=False)
    environment_type = Column(String(20), nullable=False)
    status = Column(String(20), default="created")

    total_timesteps = Column(Integer, nullable=False)
    current_timestep = Column(Integer, default=0)
    episodes_completed = Column(Integer, default=0)

    env_width = Column(Integer, default=8)
    env_height = Column(Integer, default=8)

    coverage_weight = Column(Float, default=1.5)
    exploration_weight = Column(Float, default=3.0)
    diversity_weight = Column(Float, default=2.0)

    learning_rate = Column(Float, default=0.0003)
    batch_size = Column(Integer, default=64)
    num_workers = Column(Integer, default=1)

    model_path = Column(String(512))
    log_path = Column(String(512))
    config = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # リレーションシップ
    metrics = relationship("TrainingMetrics", back_populates="session", cascade="all, delete-orphan")
    states = relationship("EnvironmentState", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self):
        """辞書形式に変換"""
        return {
            "id": self.id,
            "name": self.name,
            "algorithm": self.algorithm,
            "environment_type": self.environment_type,
            "status": self.status,
            "total_timesteps": self.total_timesteps,
            "current_timestep": self.current_timestep,
            "progress": self.current_timestep / self.total_timesteps if self.total_timesteps > 0 else 0,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

class TrainingMetrics(Base):
    """学習メトリクスモデル"""
    __tablename__ = "training_metrics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False)

    timestep = Column(Integer, nullable=False)
    episode = Column(Integer)
    reward = Column(Float, nullable=False)
    loss = Column(Float)

    coverage_ratio = Column(Float)
    exploration_score = Column(Float)
    threat_level_avg = Column(Float)

    additional_metrics = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # リレーションシップ
    session = relationship("TrainingSession", back_populates="metrics")
```

### 3.3 Pydanticスキーマ定義

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, Dict, Any
from datetime import datetime

class TrainingSessionCreate(BaseModel):
    """学習セッション作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=255, description="セッション名")
    algorithm: Literal["ppo", "a3c"] = Field(..., description="学習アルゴリズム")
    environment_type: Literal["standard", "enhanced"] = Field(..., description="環境タイプ")
    total_timesteps: int = Field(..., gt=0, le=1000000, description="総学習ステップ数")

    env_width: int = Field(8, ge=3, le=50, description="環境の幅")
    env_height: int = Field(8, ge=3, le=50, description="環境の高さ")

    coverage_weight: float = Field(1.5, ge=0.0, le=10.0, description="カバー率報酬重み")
    exploration_weight: float = Field(3.0, ge=0.0, le=10.0, description="探索報酬重み")
    diversity_weight: float = Field(2.0, ge=0.0, le=10.0, description="多様性報酬重み")

    learning_rate: float = Field(0.0003, gt=0.0, le=0.1, description="学習率")
    batch_size: int = Field(64, gt=0, le=1024, description="バッチサイズ")
    num_workers: int = Field(1, ge=1, le=16, description="ワーカー数(A3C用)")

    config: Optional[Dict[str, Any]] = Field(None, description="追加設定")

    @validator('algorithm')
    def validate_algorithm(cls, v):
        if v not in ['ppo', 'a3c']:
            raise ValueError("algorithm must be 'ppo' or 'a3c'")
        return v

class TrainingSessionResponse(BaseModel):
    """学習セッションレスポンス"""
    id: int
    name: str
    algorithm: str
    environment_type: str
    status: str
    total_timesteps: int
    current_timestep: int
    progress: float  # 0.0-1.0
    config: Optional[Dict[str, Any]]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True  # SQLAlchemyモデルから変換可能

class TrainingMetricsResponse(BaseModel):
    """学習メトリクスレスポンス"""
    timestep: int
    episode: Optional[int]
    reward: float
    loss: Optional[float]
    coverage_ratio: Optional[float]
    exploration_score: Optional[float]
    threat_level_avg: Optional[float]
    timestamp: datetime

    class Config:
        from_attributes = True
```

## 4. API エンドポイント詳細仕様

### 4.1 学習制御API

**POST /api/v1/training/start - 学習セッション開始**

```python
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/training", tags=["training"])

@router.post("/start", response_model=TrainingSessionResponse, status_code=202)
async def start_training(
    config: TrainingSessionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    新しい学習セッションを開始

    Args:
        config: 学習設定
        background_tasks: バックグラウンドタスク
        db: データベースセッション

    Returns:
        作成された学習セッション情報

    Raises:
        HTTPException: 設定が不正な場合
    """
    # サービス層でビジネスロジック実行
    service = TrainingService(db)

    try:
        # セッション作成
        session = await service.create_session(config)

        # バックグラウンドでCeleryタスク起動
        background_tasks.add_task(
            service.start_training_background,
            session.id
        )

        return TrainingSessionResponse.from_orm(session)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
```

**リクエスト例:**
```json
POST /api/v1/training/start
Content-Type: application/json

{
  "name": "実験1_PPO_拡張環境_20x20",
  "algorithm": "ppo",
  "environment_type": "enhanced",
  "total_timesteps": 50000,
  "env_width": 20,
  "env_height": 20,
  "coverage_weight": 1.5,
  "exploration_weight": 3.0,
  "diversity_weight": 2.0,
  "learning_rate": 0.0003,
  "batch_size": 64,
  "config": {
    "description": "探索重視の実験",
    "notes": "カバー率80%以上を目標"
  }
}
```

**レスポンス例:**
```json
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "id": 123,
  "name": "実験1_PPO_拡張環境_20x20",
  "algorithm": "ppo",
  "environment_type": "enhanced",
  "status": "created",
  "total_timesteps": 50000,
  "current_timestep": 0,
  "progress": 0.0,
  "config": {
    "description": "探索重視の実験",
    "notes": "カバー率80%以上を目標"
  },
  "created_at": "2025-10-05T10:30:00Z",
  "started_at": null,
  "completed_at": null
}
```

**POST /api/v1/training/{session_id}/stop - 学習停止**

```python
@router.post("/{session_id}/stop", status_code=200)
async def stop_training(
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    実行中の学習セッションを停止

    Args:
        session_id: セッションID
        db: データベースセッション

    Returns:
        停止結果メッセージ

    Raises:
        HTTPException: セッションが見つからない、または停止できない場合
    """
    service = TrainingService(db)

    success = await service.stop_training(session_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Training session {session_id} not found or cannot be stopped"
        )

    return {
        "message": f"Training session {session_id} stopped successfully",
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat()
    }
```

**GET /api/v1/training/{session_id}/status - 状態取得**

```python
@router.get("/{session_id}/status", response_model=TrainingSessionResponse)
async def get_training_status(
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    学習セッションの現在状態を取得

    Args:
        session_id: セッションID
        db: データベースセッション

    Returns:
        学習セッション情報

    Raises:
        HTTPException: セッションが見つからない場合
    """
    service = TrainingService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Training session {session_id} not found"
        )

    return TrainingSessionResponse.from_orm(session)
```

**GET /api/v1/training/{session_id}/metrics - メトリクス取得**

```python
@router.get("/{session_id}/metrics", response_model=List[TrainingMetricsResponse])
async def get_training_metrics(
    session_id: int,
    limit: int = Query(100, ge=1, le=10000, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
    db: Session = Depends(get_db)
):
    """
    学習メトリクスを取得

    Args:
        session_id: セッションID
        limit: 取得件数
        offset: オフセット
        db: データベースセッション

    Returns:
        メトリクスリスト(新しい順)
    """
    service = TrainingService(db)
    metrics = await service.get_metrics(session_id, limit, offset)

    return [TrainingMetricsResponse.from_orm(m) for m in metrics]
```

**レスポンス例:**
```json
GET /api/v1/training/123/metrics?limit=3

HTTP/1.1 200 OK
Content-Type: application/json

[
  {
    "timestep": 5000,
    "episode": 125,
    "reward": 58.3,
    "loss": 0.022,
    "coverage_ratio": 0.87,
    "exploration_score": 0.71,
    "threat_level_avg": 0.22,
    "timestamp": "2025-10-05T10:45:00Z"
  },
  {
    "timestep": 4000,
    "episode": 100,
    "reward": 52.8,
    "loss": 0.028,
    "coverage_ratio": 0.81,
    "exploration_score": 0.65,
    "threat_level_avg": 0.28,
    "timestamp": "2025-10-05T10:40:00Z"
  },
  {
    "timestep": 3000,
    "episode": 75,
    "reward": 45.2,
    "loss": 0.034,
    "coverage_ratio": 0.72,
    "exploration_score": 0.58,
    "threat_level_avg": 0.35,
    "timestamp": "2025-10-05T10:35:00Z"
  }
]
```

### 4.2 WebSocket通信実装

**接続マネージャー実装:**

```python
from typing import Dict, List
from fastapi import WebSocket
import json
import logging

class ConnectionManager:
    """WebSocket接続管理"""

    def __init__(self):
        # 全アクティブ接続
        self.active_connections: List[WebSocket] = []
        # セッション別接続マップ
        self.session_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: Optional[int] = None):
        """
        WebSocket接続を受け入れ

        Args:
            websocket: WebSocketインスタンス
            session_id: セッションID(オプション)
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        if session_id is not None:
            if session_id not in self.session_connections:
                self.session_connections[session_id] = []
            self.session_connections[session_id].append(websocket)

        logging.info(f"WebSocket connected. Session: {session_id}, Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, session_id: Optional[int] = None):
        """
        WebSocket接続を切断

        Args:
            websocket: WebSocketインスタンス
            session_id: セッションID(オプション)
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if session_id and session_id in self.session_connections:
            if websocket in self.session_connections[session_id]:
                self.session_connections[session_id].remove(websocket)

            # 接続がなくなったらセッションエントリ削除
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

        logging.info(f"WebSocket disconnected. Session: {session_id}, Remaining: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """
        特定の接続にメッセージ送信

        Args:
            message: 送信メッセージ(辞書)
            websocket: 送信先WebSocket
        """
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logging.error(f"Failed to send personal message: {e}")

    async def broadcast_to_session(self, session_id: int, message: Dict):
        """
        特定セッションの全接続にブロードキャスト

        Args:
            session_id: セッションID
            message: ブロードキャストメッセージ
        """
        if session_id not in self.session_connections:
            return

        disconnected = []
        for connection in self.session_connections[session_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logging.error(f"Failed to broadcast to session {session_id}: {e}")
                disconnected.append(connection)

        # 切断された接続を削除
        for conn in disconnected:
            self.disconnect(conn, session_id)

    async def broadcast_all(self, message: Dict):
        """
        全接続にブロードキャスト

        Args:
            message: ブロードキャストメッセージ
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)

        # 切断された接続を削除
        for conn in disconnected:
            self.disconnect(conn)

# グローバルインスタンス
manager = ConnectionManager()
```

**WebSocketエンドポイント:**

```python
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/training/{session_id}")
async def training_websocket(
    websocket: WebSocket,
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    学習進捗のリアルタイム配信WebSocket

    Args:
        websocket: WebSocketインスタンス
        session_id: セッションID
        db: データベースセッション
    """
    await manager.connect(websocket, session_id)

    try:
        # Redis Pub/Subで進捗監視開始
        pubsub = redis_client.pubsub()
        channel = f"training_progress_{session_id}"
        pubsub.subscribe(channel)

        # 購読確認メッセージ送信
        await manager.send_personal_message({
            "type": "connected",
            "session_id": session_id,
            "message": "Successfully subscribed to training progress"
        }, websocket)

        # メッセージ受信ループ
        while True:
            # クライアントからのメッセージ受信(ping等)
            try:
                client_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0
                )

                # Pingに応答
                data = json.loads(client_message)
                if data.get("type") == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)

            except asyncio.TimeoutError:
                pass

            # Redis Pub/Subからメッセージ取得
            message = pubsub.get_message()
            if message and message['type'] == 'message':
                progress_data = json.loads(message['data'])

                # クライアントに転送
                await manager.send_personal_message({
                    "type": "training_progress",
                    "session_id": session_id,
                    "data": progress_data,
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        pubsub.unsubscribe(channel)
        logging.info(f"Client disconnected from session {session_id}")

    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id)
```

## 5. サービス層実装

### 5.1 TrainingService詳細

```python
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

class TrainingService:
    """学習管理サービス"""

    def __init__(self, db: Session):
        self.db = db

    async def create_session(self, config: TrainingSessionCreate) -> TrainingSession:
        """
        新しい学習セッションを作成

        Args:
            config: 学習設定

        Returns:
            作成されたセッション

        Raises:
            ValueError: 設定が不正な場合
        """
        # バリデーション
        if config.total_timesteps <= 0:
            raise ValueError("total_timesteps must be positive")

        if config.algorithm == "a3c" and config.num_workers < 1:
            raise ValueError("num_workers must be at least 1 for A3C")

        # DBモデル作成
        db_session = TrainingSession(
            name=config.name,
            algorithm=config.algorithm,
            environment_type=config.environment_type,
            total_timesteps=config.total_timesteps,
            env_width=config.env_width,
            env_height=config.env_height,
            coverage_weight=config.coverage_weight,
            exploration_weight=config.exploration_weight,
            diversity_weight=config.diversity_weight,
            learning_rate=config.learning_rate,
            batch_size=config.batch_size,
            num_workers=config.num_workers,
            config=config.config,
            status="created"
        )

        self.db.add(db_session)
        self.db.commit()
        self.db.refresh(db_session)

        logging.info(f"Created training session {db_session.id}: {config.name}")
        return db_session

    async def start_training_background(self, session_id: int):
        """
        バックグラウンドで学習開始

        Args:
            session_id: セッションID
        """
        from app.tasks.training_tasks import run_training_task

        # セッション存在確認
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status == "running":
            raise ValueError(f"Session {session_id} is already running")

        # Celeryタスク起動
        task = run_training_task.delay(session_id)

        # セッション状態更新
        session.status = "running"
        session.started_at = datetime.utcnow()
        self.db.commit()

        logging.info(f"Started training task {task.id} for session {session_id}")

    async def stop_training(self, session_id: int) -> bool:
        """
        学習を停止

        Args:
            session_id: セッションID

        Returns:
            成功した場合True
        """
        session = self.get_session(session_id)
        if not session:
            return False

        if session.status != "running":
            return False

        # Celeryタスクを停止(タスクIDを保存している場合)
        # ここでは簡易的にステータス更新のみ
        session.status = "paused"
        session.completed_at = datetime.utcnow()
        self.db.commit()

        logging.info(f"Stopped training session {session_id}")
        return True

    def get_session(self, session_id: int) -> Optional[TrainingSession]:
        """
        セッション取得

        Args:
            session_id: セッションID

        Returns:
            セッション(存在しない場合None)
        """
        return self.db.query(TrainingSession).filter(
            TrainingSession.id == session_id
        ).first()

    async def get_metrics(
        self,
        session_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[TrainingMetrics]:
        """
        メトリクス取得

        Args:
            session_id: セッションID
            limit: 取得件数
            offset: オフセット

        Returns:
            メトリクスリスト
        """
        return self.db.query(TrainingMetrics).filter(
            TrainingMetrics.session_id == session_id
        ).order_by(
            TrainingMetrics.timestep.desc()
        ).offset(offset).limit(limit).all()

    async def record_metrics(
        self,
        session_id: int,
        timestep: int,
        metrics_data: Dict
    ):
        """
        メトリクスを記録

        Args:
            session_id: セッションID
            timestep: タイムステップ
            metrics_data: メトリクスデータ
        """
        metrics = TrainingMetrics(
            session_id=session_id,
            timestep=timestep,
            episode=metrics_data.get("episode"),
            reward=metrics_data.get("reward"),
            loss=metrics_data.get("loss"),
            coverage_ratio=metrics_data.get("coverage_ratio"),
            exploration_score=metrics_data.get("exploration_score"),
            threat_level_avg=metrics_data.get("threat_level_avg"),
            additional_metrics=metrics_data.get("additional_metrics")
        )

        self.db.add(metrics)
        self.db.commit()

        # セッションの進捗更新
        session = self.get_session(session_id)
        if session:
            session.current_timestep = timestep
            if metrics_data.get("episode"):
                session.episodes_completed = metrics_data["episode"]
            self.db.commit()
```

## 6. Celeryバックグラウンドタスク

### 6.1 Celery設定

```python
# app/tasks/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "security_robot_rl",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.training_tasks"]
)

# 設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600 * 12,  # 12時間タイムアウト
    worker_prefetch_multiplier=1,  # 1タスクずつ実行
    worker_max_tasks_per_child=10  # 10タスクごとにワーカープロセス再起動
)
```

### 6.2 学習タスク実装

```python
# app/tasks/training_tasks.py
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.database import TrainingSession
from app.ml.training.ppo_trainer import PPOTrainer
from app.ml.training.a3c_trainer import A3CTrainer
import logging
import redis

@celery_app.task(bind=True, name="run_training")
def run_training_task(self, session_id: int):
    """
    学習タスク実行

    Args:
        self: Celeryタスクインスタンス
        session_id: セッションID

    Returns:
        完了メッセージ
    """
    db = SessionLocal()
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        # セッション取得
        session = db.query(TrainingSession).filter(
            TrainingSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Training session {session_id} not found")

        logging.info(f"Starting training for session {session_id}: {session.name}")

        # アルゴリズムに応じてトレーナー作成
        if session.algorithm == "ppo":
            trainer = PPOTrainer(session, db, redis_client)
        elif session.algorithm == "a3c":
            trainer = A3CTrainer(session, db, redis_client)
        else:
            raise ValueError(f"Unknown algorithm: {session.algorithm}")

        # 進捗コールバック定義
        def progress_callback(timestep: int, metrics: Dict):
            """進捗をRedis Pub/Subで配信"""
            channel = f"training_progress_{session_id}"
            message = json.dumps({
                "timestep": timestep,
                "episode": metrics.get("episode"),
                "reward": metrics.get("reward"),
                "loss": metrics.get("loss"),
                "coverage_ratio": metrics.get("coverage_ratio"),
                "exploration_score": metrics.get("exploration_score"),
                "threat_level_avg": metrics.get("threat_level_avg")
            })
            redis_client.publish(channel, message)

            # Celeryタスク状態更新
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": timestep,
                    "total": session.total_timesteps,
                    "progress": timestep / session.total_timesteps
                }
            )

        # 学習実行
        trainer.train(progress_callback=progress_callback)

        # 完了処理
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.commit()

        # 完了通知をWebSocketで配信
        redis_client.publish(
            f"training_progress_{session_id}",
            json.dumps({
                "type": "training_complete",
                "session_id": session_id,
                "status": "completed",
                "model_path": session.model_path,
                "timestamp": datetime.utcnow().isoformat()
            })
        )

        logging.info(f"Training completed for session {session_id}")
        return {"status": "completed", "session_id": session_id}

    except Exception as e:
        logging.error(f"Training failed for session {session_id}: {e}")

        # エラー処理
        if session:
            session.status = "failed"
            session.completed_at = datetime.utcnow()
            db.commit()

        # エラー通知
        redis_client.publish(
            f"training_progress_{session_id}",
            json.dumps({
                "type": "training_error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        )

        raise

    finally:
        db.close()
```

## 7. 強化学習エンジン統合

### 7.1 PPOTrainer実装

```python
# app/ml/training/ppo_trainer.py
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from app.ml.environments.standard import StandardEnvironment
from app.ml.environments.enhanced import EnhancedEnvironment
import os

class PPOTrainer:
    """PPO学習トレーナー"""

    def __init__(self, session: TrainingSession, db: Session, redis_client):
        self.session = session
        self.db = db
        self.redis_client = redis_client

        # 環境作成
        if session.environment_type == "enhanced":
            self.env = EnhancedEnvironment(
                width=session.env_width,
                height=session.env_height,
                coverage_weight=session.coverage_weight,
                exploration_weight=session.exploration_weight,
                diversity_weight=session.diversity_weight
            )
        else:
            self.env = StandardEnvironment(
                width=session.env_width,
                height=session.env_height
            )

        # モデル作成
        self.model = PPO(
            policy="MlpPolicy",
            env=self.env,
            learning_rate=session.learning_rate,
            n_steps=2048,
            batch_size=session.batch_size,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
            verbose=1
        )

    def train(self, progress_callback=None):
        """
        学習実行

        Args:
            progress_callback: 進捗コールバック関数
        """
        # カスタムコールバック
        class ProgressCallback(BaseCallback):
            def __init__(self, callback_fn, session_id, db, verbose=0):
                super().__init__(verbose)
                self.callback_fn = callback_fn
                self.session_id = session_id
                self.db = db
                self.step_count = 0

            def _on_step(self) -> bool:
                self.step_count += 1

                # 100ステップごとに進捗通知
                if self.step_count % 100 == 0 and self.callback_fn:
                    # メトリクス収集
                    ep_info_buffer = self.model.ep_info_buffer
                    metrics = {
                        "episode": len(ep_info_buffer),
                        "reward": np.mean([ep['r'] for ep in ep_info_buffer[-10:]]) if ep_info_buffer else 0,
                        "loss": self.locals.get("loss", 0),
                        "coverage_ratio": self.locals.get("infos", [{}])[0].get("coverage_ratio", 0),
                        "exploration_score": self.locals.get("infos", [{}])[0].get("exploration_score", 0),
                        "threat_level_avg": self.locals.get("infos", [{}])[0].get("threat_level_avg", 0)
                    }

                    # コールバック実行
                    self.callback_fn(self.step_count, metrics)

                    # DBにメトリクス保存
                    from app.services.training_service import TrainingService
                    service = TrainingService(self.db)
                    service.record_metrics(self.session_id, self.step_count, metrics)

                return True

        # 学習実行
        callback = ProgressCallback(progress_callback, self.session.id, self.db)
        self.model.learn(
            total_timesteps=self.session.total_timesteps,
            callback=callback
        )

        # モデル保存
        model_dir = "models"
        os.makedirs(model_dir, exist_ok=True)
        model_path = f"{model_dir}/ppo_session_{self.session.id}.zip"
        self.model.save(model_path)

        # セッション更新
        self.session.model_path = model_path
        self.db.commit()
```

このバックエンドAPI設計により、フロントエンドとの明確な分離、非同期処理による高性能、リアルタイム通信による優れたUXを実現します。
