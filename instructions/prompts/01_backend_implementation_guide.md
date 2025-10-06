# セキュリティロボット強化学習システム - バックエンド実装ガイド

## 🎯 このドキュメントの目的

このガイドは、**バックエンドのみ**に特化した実装指示書です。AI開発アシスタント(Claude Code, GitHub Copilot等)を活用して、セキュリティロボット強化学習システムのバックエンドAPIを段階的に実装します。

**重要:** このドキュメントと親ディレクトリの設計書(`01_system_architecture_design_standalone.md`, `02_backend_api_design_standalone.md`)を組み合わせることで、フロントエンド実装なしでバックエンド単体で完全なAPI機能を実装できます。

## 📚 前提知識

### 🔴 実装開始前の必須作業

**IMPORTANT**: 実装作業を開始する前に、必ず以下のファイルを読んでください:

1. **`../../report/PROGRESS.md`** - 現在の実装状況
   - 何が完了し、何がTODOかを把握
   - 既知の問題や課題を確認
   - 次のアクションアイテムを確認

2. **`../../report/DIARY.md`** - 開発セッション履歴
   - 過去のセッションで何を実施したかを確認
   - 学んだことや気づきを把握
   - 前回のセッションからの引き継ぎ事項を確認

3. **`../../CLAUDE.md`** - プロジェクト概要と進捗管理ワークフロー

### 必要な設計書
実装前に以下を熟読してください:
1. `../01_system_architecture_design_standalone.md` - システム全体設計(バックエンド部分に注目)
2. `../02_backend_api_design_standalone.md` - バックエンドAPI詳細設計

### 技術要件
- Python 3.12+
- **uv** (パッケージマネージャー) - このプロジェクトでは pip/venv の代わりに uv を使用
- Docker & Docker Compose
- PostgreSQL 15 (開発環境では SQLite も使用可能)
- Redis 7

### 現在のプロジェクト構造

このリポジトリには既に基本的な構造が実装されています:

```
security-robot-be/
├── app/
│   ├── main.py                      # FastAPIアプリケーションエントリーポイント
│   ├── core/
│   │   ├── config.py                # 設定管理
│   │   ├── environment/             # 環境サービス
│   │   ├── training/                # 学習サービス
│   │   ├── websocket/               # WebSocket管理
│   │   └── files/                   # ファイル管理
│   ├── api/
│   │   └── v1/                      # APIバージョン1
│   │       ├── api.py               # ルーター統合
│   │       └── endpoints/           # エンドポイント
│   │           ├── training.py      # 学習制御API
│   │           ├── environment.py   # 環境制御API
│   │           ├── jobs.py          # ジョブ管理API
│   │           ├── files.py         # ファイル管理API
│   │           ├── websocket.py     # WebSocketエンドポイント
│   │           └── health.py        # ヘルスチェック
│   ├── db/                          # データベース設定
│   ├── models/                      # SQLAlchemyモデル
│   ├── schemas/                     # Pydanticスキーマ
│   ├── tasks/                       # Celeryタスク
│   └── utils/                       # ユーティリティ
├── rl/                              # 強化学習コンポーネント
│   ├── environments/                # RL環境実装
│   ├── algorithms/                  # RL アルゴリズム(PPO, A3C)
│   ├── callbacks/                   # 学習コールバック
│   └── utils/                       # 可視化・評価ユーティリティ
├── tests/                           # テストスイート
├── requirements.txt                 # 依存関係
└── CLAUDE.md                        # プロジェクト指示書
```

## 🏗️ 実装フェーズ

### Phase 1: 環境準備・確認 (Day 1)

#### 1.1 開発環境セットアップ

```bash
# uvのインストール確認
uv --version

# 仮想環境作成(既に存在する場合はスキップ)
uv venv

# 仮想環境の有効化(オプション、uvは自動的に仮想環境を使用可能)
source .venv/bin/activate  # Linux/macOS
# または
.venv\Scripts\activate  # Windows

# 依存関係インストール
uv pip install -r requirements.txt

# 開発用依存関係インストール
uv pip install pytest pytest-asyncio httpx
```

#### 1.2 データベースセットアップ

**開発環境: SQLiteを使用(デフォルト)**

```bash
# .env ファイル作成(まだ存在しない場合)
cat > .env << 'EOF'
# データベース設定(開発環境はSQLite)
DATABASE_URL=sqlite+aiosqlite:///./security_robot.db

# Redis設定(Celery用)
REDIS_URL=redis://localhost:6379/0

# API設定
API_PREFIX=/api/v1
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080

# ログ設定
LOG_LEVEL=INFO
EOF

# データベース初期化(起動時に自動作成されるため手動実行は不要)
# FastAPIアプリ起動時にBase.metadata.create_all()が実行される
```

**本番環境: PostgreSQL + Redisを使用**

```bash
# Docker Composeで起動
docker-compose up -d postgres redis

# PostgreSQL接続確認
docker-compose exec postgres psql -U postgres -c "SELECT version();"

# Redis接続確認
docker-compose exec redis redis-cli ping
```

#### 1.3 アプリケーション起動確認

```bash
# FastAPI開発サーバー起動(uvを使用)
uv run uvicorn app.main:app --reload

# または仮想環境を有効化している場合
uvicorn app.main:app --reload

# 別ターミナルでヘルスチェック
curl http://localhost:8000/health

# Swagger UI確認
# ブラウザで http://localhost:8000/docs を開く
```

**期待される出力:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

#### 1.4 Celeryワーカー起動(オプション)

```bash
# Redisが起動している必要があります
docker-compose up -d redis

# Celeryワーカー起動
uv run celery -A app.tasks.celery_app worker --loglevel=info

# または
celery -A app.tasks.celery_app worker --loglevel=info
```

### Phase 2: データベースモデル実装・拡張 (Day 2-3)

#### 2.1 既存モデルの確認

現在のプロジェクトには基本的なモデルが実装されています:
- `app/models/training.py` - 学習セッション関連
- `app/models/environment.py` - 環境状態関連
- `app/models/files.py` - ファイル管理関連

設計書(`02_backend_api_design_standalone.md`の3.2節)と比較して不足している要素を追加実装してください。

#### 2.2 必須モデル要素の確認

**TrainingSessionモデルに必要なフィールド:**
```python
# app/models/training.py
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class TrainingSession(Base):
    """学習セッションモデル"""
    __tablename__ = "training_sessions"

    # 基本フィールド
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    algorithm = Column(String(10), nullable=False)  # 'ppo' or 'a3c'
    environment_type = Column(String(20), nullable=False)  # 'standard' or 'enhanced'
    status = Column(String(20), default="created")  # 'created', 'running', 'paused', 'completed', 'failed'

    # 学習パラメータ
    total_timesteps = Column(Integer, nullable=False)
    current_timestep = Column(Integer, default=0)
    episodes_completed = Column(Integer, default=0)

    # 環境設定
    env_width = Column(Integer, default=8)
    env_height = Column(Integer, default=8)

    # 報酬パラメータ(拡張環境用)
    coverage_weight = Column(Float, default=1.5)
    exploration_weight = Column(Float, default=3.0)
    diversity_weight = Column(Float, default=2.0)

    # 追加パラメータ
    learning_rate = Column(Float, default=0.0003)
    batch_size = Column(Integer, default=64)
    num_workers = Column(Integer, default=1)  # A3C用

    # ファイルパス
    model_path = Column(String(512))
    log_path = Column(String(512))

    # 設定全体(JSON)
    config = Column(JSON)

    # タイムスタンプ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # リレーションシップ
    metrics = relationship("TrainingMetrics", back_populates="session", cascade="all, delete-orphan")

    # テーブル制約
    __table_args__ = (
        CheckConstraint("algorithm IN ('ppo', 'a3c')", name="check_algorithm"),
        CheckConstraint("environment_type IN ('standard', 'enhanced')", name="check_environment_type"),
        CheckConstraint("status IN ('created', 'running', 'paused', 'completed', 'failed')", name="check_status"),
    )
```

**TrainingMetricsモデル:**
```python
# app/models/training.py
class TrainingMetrics(Base):
    """学習メトリクスモデル"""
    __tablename__ = "training_metrics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False)

    # メトリクス
    timestep = Column(Integer, nullable=False, index=True)
    episode = Column(Integer)
    reward = Column(Float, nullable=False)
    loss = Column(Float)

    # 環境固有メトリクス
    coverage_ratio = Column(Float)
    exploration_score = Column(Float)
    threat_level_avg = Column(Float)

    # 追加メトリクス(JSON)
    additional_metrics = Column(JSON)

    # タイムスタンプ
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # リレーションシップ
    session = relationship("TrainingSession", back_populates="metrics")

    # インデックス
    __table_args__ = (
        # 複合インデックス
        Index("idx_session_timestep", "session_id", "timestep"),
    )
```

#### 2.3 データベーステーブル作成

```bash
# アプリケーション起動時に自動作成
uv run uvicorn app.main:app --reload

# または手動で初期化スクリプトを作成
cat > init_db.py << 'EOF'
from app.db.database import engine
from app.db.base_class import Base
from app.models import training, environment, files

# テーブル作成
Base.metadata.create_all(bind=engine)
print("Database tables created successfully")
EOF

uv run python init_db.py
```

### Phase 3: Pydanticスキーマ実装・拡張 (Day 3-4)

#### 3.1 既存スキーマの確認

設計書(`02_backend_api_design_standalone.md`の3.3節)のPydanticスキーマと現在の実装を比較:

```python
# app/schemas/training.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Dict, Any
from datetime import datetime

class TrainingSessionCreate(BaseModel):
    """学習セッション作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=255, description="セッション名")
    algorithm: Literal["ppo", "a3c"] = Field(..., description="学習アルゴリズム")
    environment_type: Literal["standard", "enhanced"] = Field(..., description="環境タイプ")
    total_timesteps: int = Field(..., gt=0, le=1000000, description="総学習ステップ数")

    # 環境パラメータ
    env_width: int = Field(8, ge=3, le=50, description="環境の幅")
    env_height: int = Field(8, ge=3, le=50, description="環境の高さ")

    # 報酬重み(拡張環境用)
    coverage_weight: float = Field(1.5, ge=0.0, le=10.0, description="カバー率報酬重み")
    exploration_weight: float = Field(3.0, ge=0.0, le=10.0, description="探索報酬重み")
    diversity_weight: float = Field(2.0, ge=0.0, le=10.0, description="多様性報酬重み")

    # 学習パラメータ
    learning_rate: float = Field(0.0003, gt=0.0, le=0.1, description="学習率")
    batch_size: int = Field(64, gt=0, le=1024, description="バッチサイズ")
    num_workers: int = Field(1, ge=1, le=16, description="ワーカー数(A3C用)")

    # 追加設定
    config: Optional[Dict[str, Any]] = Field(None, description="追加設定")

    @field_validator('algorithm')
    @classmethod
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
    progress: float = Field(description="進捗率 (0.0-1.0)")
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class TrainingMetricsResponse(BaseModel):
    """学習メトリクスレスポンス"""
    timestep: int
    episode: Optional[int] = None
    reward: float
    loss: Optional[float] = None
    coverage_ratio: Optional[float] = None
    exploration_score: Optional[float] = None
    threat_level_avg: Optional[float] = None
    additional_metrics: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = {"from_attributes": True}
```

### Phase 4: APIエンドポイント実装・拡張 (Day 4-6)

#### 4.1 学習制御APIの実装

設計書(`02_backend_api_design_standalone.md`の4.1節)を参照して実装してください:

```python
# app/api/v1/endpoints/training.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.api.deps import get_db
from app.schemas.training import (
    TrainingSessionCreate,
    TrainingSessionResponse,
    TrainingMetricsResponse
)
from app.core.training.ppo_service import PPOService
from app.core.training.a3c_service import A3CService

router = APIRouter()

@router.post("/start", response_model=TrainingSessionResponse, status_code=202)
async def start_training(
    config: TrainingSessionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
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
    try:
        # アルゴリズムに応じたサービス選択
        if config.algorithm == "ppo":
            service = PPOService(db)
        elif config.algorithm == "a3c":
            service = A3CService(db)
        else:
            raise HTTPException(status_code=400, detail="Invalid algorithm")

        # セッション作成
        session = await service.create_session(config)

        # バックグラウンドで学習開始
        background_tasks.add_task(service.start_training, session.id)

        return TrainingSessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/{session_id}/stop", status_code=200)
async def stop_training(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """学習セッションを停止"""
    from app.core.training.job_manager import JobManager
    
    manager = JobManager()
    success = await manager.stop_job(session_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Training session {session_id} not found or cannot be stopped"
        )

    return {
        "message": f"Training session {session_id} stopped successfully",
        "session_id": session_id
    }

@router.get("/{session_id}/status", response_model=TrainingSessionResponse)
async def get_training_status(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """学習セッションの現在状態を取得"""
    from sqlalchemy import select
    from app.models.training import TrainingSession

    result = await db.execute(
        select(TrainingSession).where(TrainingSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Training session {session_id} not found"
        )

    return TrainingSessionResponse.model_validate(session)

@router.get("/{session_id}/metrics", response_model=List[TrainingMetricsResponse])
async def get_training_metrics(
    session_id: int,
    limit: int = Query(100, ge=1, le=10000, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
    db: AsyncSession = Depends(get_db)
):
    """学習メトリクスを取得"""
    from sqlalchemy import select
    from app.models.training import TrainingMetrics

    result = await db.execute(
        select(TrainingMetrics)
        .where(TrainingMetrics.session_id == session_id)
        .order_by(TrainingMetrics.timestep.desc())
        .offset(offset)
        .limit(limit)
    )
    metrics = result.scalars().all()

    return [TrainingMetricsResponse.model_validate(m) for m in metrics]
```

#### 4.2 その他のAPIエンドポイント

- `app/api/v1/endpoints/environment.py` - 環境制御API
- `app/api/v1/endpoints/jobs.py` - ジョブ管理API
- `app/api/v1/endpoints/files.py` - ファイル管理API
- `app/api/v1/endpoints/health.py` - ヘルスチェックAPI

既存の実装を確認し、設計書と照らし合わせて不足している機能を追加してください。

### Phase 5: WebSocket・リアルタイム通信実装 (Day 6-7)

#### 5.1 WebSocket接続マネージャーの確認・拡張

設計書(`02_backend_api_design_standalone.md`の4.2節)を参照:

```python
# app/core/websocket/manager.py
from typing import Dict, List, Set
from fastapi import WebSocket
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket接続管理"""

    def __init__(self):
        # 全アクティブ接続
        self.active_connections: List[WebSocket] = []
        # セッション別接続マップ
        self.session_connections: Dict[int, Set[WebSocket]] = {}
        # 接続ロック
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: int = None):
        """WebSocket接続を受け入れ"""
        await websocket.accept()
        
        async with self._lock:
            self.active_connections.append(websocket)
            
            if session_id is not None:
                if session_id not in self.session_connections:
                    self.session_connections[session_id] = set()
                self.session_connections[session_id].add(websocket)

        logger.info(f"WebSocket connected. Session: {session_id}, Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket, session_id: int = None):
        """WebSocket接続を切断"""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            if session_id and session_id in self.session_connections:
                self.session_connections[session_id].discard(websocket)
                
                # 接続がなくなったらセッションエントリ削除
                if not self.session_connections[session_id]:
                    del self.session_connections[session_id]

        logger.info(f"WebSocket disconnected. Session: {session_id}, Remaining: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """特定の接続にメッセージ送信"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def broadcast_to_session(self, session_id: int, message: Dict):
        """特定セッションの全接続にブロードキャスト"""
        if session_id not in self.session_connections:
            return

        disconnected = []
        connections = list(self.session_connections[session_id])
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to session {session_id}: {e}")
                disconnected.append(connection)

        # 切断された接続を削除
        for conn in disconnected:
            await self.disconnect(conn, session_id)

# グローバルインスタンス
manager = WebSocketManager()
```

#### 5.2 WebSocketエンドポイントの実装

```python
# app/api/v1/endpoints/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.websocket.manager import manager
from app.api.deps import get_db
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/training/{session_id}")
async def training_websocket(
    websocket: WebSocket,
    session_id: int,
    db: AsyncSession = Depends(get_db)
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
        # 接続確認メッセージ送信
        await manager.send_personal_message({
            "type": "connected",
            "session_id": session_id,
            "message": "Successfully connected to training progress stream"
        }, websocket)

        # メッセージ受信ループ
        while True:
            try:
                # クライアントからのメッセージ受信(ping等)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Pingに応答
                if message.get("type") == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket, session_id)
        logger.info(f"Client disconnected from session {session_id}")
```

### Phase 6: Celeryバックグラウンドタスク実装 (Day 7-8)

#### 6.1 Celery設定の確認

```python
# app/tasks/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "security_robot_rl",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.training_tasks", "app.tasks.file_tasks"]
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
    worker_prefetch_multiplier=1,
)
```

#### 6.2 学習タスクの実装

設計書(`02_backend_api_design_standalone.md`の6章)を参照して実装:

```python
# app/tasks/training_tasks.py
from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.training import TrainingSession, TrainingMetrics
from app.core.websocket.manager import manager
import logging
import asyncio

logger = logging.getLogger(__name__)

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

    try:
        # セッション取得
        session = db.query(TrainingSession).filter(
            TrainingSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Training session {session_id} not found")

        logger.info(f"Starting training for session {session_id}: {session.name}")

        # 学習実行ロジック
        # (RL環境・アルゴリズムとの統合)
        
        # 進捗コールバック
        def progress_callback(timestep: int, metrics: dict):
            """進捗をWebSocketで配信"""
            # 非同期でWebSocketブロードキャスト
            asyncio.run(manager.broadcast_to_session(session_id, {
                "type": "training_progress",
                "timestep": timestep,
                "metrics": metrics
            }))

            # タスク状態更新
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": timestep,
                    "total": session.total_timesteps,
                    "progress": timestep / session.total_timesteps
                }
            )

        # 学習完了処理
        session.status = "completed"
        db.commit()

        logger.info(f"Training completed for session {session_id}")
        return {"status": "completed", "session_id": session_id}

    except Exception as e:
        logger.error(f"Training failed for session {session_id}: {e}")
        
        if session:
            session.status = "failed"
            db.commit()

        raise

    finally:
        db.close()
```

### Phase 7: 強化学習エンジン統合 (Day 9-11)

#### 7.1 RL環境の実装確認

既存の環境実装を確認:
- `rl/environments/security_env.py` - 標準環境
- `rl/environments/enhanced_env.py` - 拡張環境

設計書(`01_system_architecture_design_standalone.md`の3章)と比較して必要な機能を追加実装。

#### 7.2 PPO/A3Cトレーナーの実装

```python
# app/core/training/ppo_service.py
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from app.models.training import TrainingSession
from rl.environments.security_env import SecurityEnvironment
from rl.environments.enhanced_env import EnhancedSecurityEnvironment
import os

class PPOService:
    """PPO学習サービス"""

    def __init__(self, db):
        self.db = db

    async def create_session(self, config):
        """セッション作成"""
        session = TrainingSession(
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

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def start_training(self, session_id: int):
        """学習開始"""
        # Celeryタスク起動
        from app.tasks.training_tasks import run_training_task
        task = run_training_task.delay(session_id)
        
        # セッション状態更新
        session = await self.db.get(TrainingSession, session_id)
        session.status = "running"
        session.started_at = datetime.utcnow()
        await self.db.commit()
```

### Phase 8: テスト実装 (Day 12-14)

#### 8.1 テスト環境セットアップ

```bash
# テスト用依存関係インストール
uv pip install pytest pytest-asyncio httpx pytest-cov

# テスト実行
uv run pytest

# カバレッジレポート付き
uv run pytest --cov=app --cov-report=html
```

#### 8.2 APIテストの実装

```python
# tests/api/test_training.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_start_training():
    """学習セッション開始APIテスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/training/start", json={
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

@pytest.mark.asyncio
async def test_get_training_status():
    """学習ステータス取得APIテスト"""
    # テスト実装
    pass

@pytest.mark.asyncio
async def test_get_training_metrics():
    """学習メトリクス取得APIテスト"""
    # テスト実装
    pass
```

#### 8.3 統合テスト

```python
# tests/integration/test_training_flow.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_complete_training_flow():
    """学習フロー統合テスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. セッション作成
        create_response = await client.post("/api/v1/training/start", json={
            "name": "Integration Test",
            "algorithm": "ppo",
            "environment_type": "standard",
            "total_timesteps": 100
        })
        assert create_response.status_code == 202
        session_id = create_response.json()["id"]

        # 2. ステータス確認
        status_response = await client.get(f"/api/v1/training/{session_id}/status")
        assert status_response.status_code == 200

        # 3. 学習停止
        stop_response = await client.post(f"/api/v1/training/{session_id}/stop")
        assert stop_response.status_code == 200
```

### Phase 9: Docker環境構築 (Day 15)

#### 9.1 Docker Composeファイルの確認・更新

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

  # バックエンドAPI
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-password}@postgres:5432/${DB_NAME:-security_robot_rl}
      REDIS_URL: redis://redis:6379
    volumes:
      - .:/app
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
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-password}@postgres:5432/${DB_NAME:-security_robot_rl}
      REDIS_URL: redis://redis:6379
    volumes:
      - .:/app
      - ./models:/app/models
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

volumes:
  postgres_data:
```

#### 9.2 Dockerfile作成

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# uvインストール
RUN pip install uv

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# アプリケーションコピー
COPY . .

# ポート公開
EXPOSE 8000

# デフォルトコマンド
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 9.3 Docker環境起動

```bash
# すべてのサービスを起動
docker-compose up -d

# ログ確認
docker-compose logs -f backend

# ヘルスチェック
curl http://localhost:8000/health

# 停止
docker-compose down

# ボリュームも削除
docker-compose down -v
```

## ✅ 実装チェックリスト

### Phase 1: 環境準備
- [ ] uv インストール確認
- [ ] 仮想環境作成・依存関係インストール
- [ ] .env ファイル作成
- [ ] FastAPI開発サーバー起動確認
- [ ] Swagger UI アクセス確認 (http://localhost:8000/docs)
- [ ] ヘルスチェックAPI動作確認

### Phase 2: データベース
- [ ] TrainingSessionモデル実装・確認
- [ ] TrainingMetricsモデル実装・確認
- [ ] EnvironmentStateモデル実装・確認
- [ ] テーブル制約・インデックス設定
- [ ] データベーステーブル作成確認

### Phase 3: Pydanticスキーマ
- [ ] TrainingSessionCreate スキーマ実装
- [ ] TrainingSessionResponse スキーマ実装
- [ ] TrainingMetricsResponse スキーマ実装
- [ ] バリデーション動作確認

### Phase 4: APIエンドポイント
- [ ] POST /api/v1/training/start 実装
- [ ] POST /api/v1/training/{id}/stop 実装
- [ ] GET /api/v1/training/{id}/status 実装
- [ ] GET /api/v1/training/{id}/metrics 実装
- [ ] 環境制御API実装確認
- [ ] ジョブ管理API実装確認
- [ ] Swagger UIでAPI動作確認

### Phase 5: WebSocket
- [ ] WebSocketManagerクラス実装・確認
- [ ] WebSocketエンドポイント実装
- [ ] 接続・切断処理動作確認
- [ ] ブロードキャスト機能動作確認

### Phase 6: Celery
- [ ] Celeryアプリ設定確認
- [ ] run_training_task実装
- [ ] Celeryワーカー起動確認
- [ ] タスク実行・進捗確認

### Phase 7: RL統合
- [ ] RL環境実装確認
- [ ] PPOServiceクラス実装
- [ ] A3CServiceクラス実装(オプション)
- [ ] 学習実行・モデル保存確認

### Phase 8: テスト
- [ ] pytest設定確認
- [ ] APIテスト実装(3つ以上)
- [ ] 統合テスト実装(1つ以上)
- [ ] テスト実行・カバレッジ確認(目標70%以上)

### Phase 9: Docker
- [ ] Dockerfile作成
- [ ] docker-compose.yml確認
- [ ] Docker環境起動確認
- [ ] 全サービスヘルスチェック

## 🎓 実装のベストプラクティス

### 1. 設計書優先アプローチ
**必ず設計書を先に読んでから実装してください**:
- `../01_system_architecture_design_standalone.md` - システム全体設計
- `../02_backend_api_design_standalone.md` - バックエンドAPI詳細

### 2. 既存コードの活用
このプロジェクトには既に基本構造が実装されています:
- `CLAUDE.md` を読んで現在の実装状況を理解
- 既存コードを確認してから拡張実装
- 重複実装を避ける

### 3. 非同期処理の活用
- FastAPIの非同期機能を活用
- `async`/`await` を適切に使用
- SQLAlchemyの非同期セッション使用

### 4. 型ヒントの徹底
- すべての関数に型ヒント追加
- Pydanticスキーマでバリデーション
- mypyでの型チェック推奨

### 5. テスト駆動開発
- 機能実装と同時にテスト作成
- pytest-covでカバレッジ70%以上維持
- 統合テストで実際のフロー確認

### 6. ログとエラーハンドリング
- 構造化ログ(JSON形式)使用
- 適切な例外処理とHTTPステータスコード
- Swagger UIでエラーレスポンス確認

## 📋 実装完了基準

以下をすべて満たした時点でバックエンド実装完了とみなします:

1. ✅ 全Phase(1-9)のチェックリスト完了
2. ✅ Swagger UI で全APIエンドポイント動作確認
3. ✅ WebSocketリアルタイム通信動作確認
4. ✅ Celeryバックグラウンドタスク実行確認
5. ✅ pytestカバレッジ70%以上
6. ✅ Docker Compose全サービス正常起動
7. ✅ 設計書との整合性100%

## 🚀 次のステップ

バックエンド実装完了後:

1. **APIドキュメント整備**
   - Swagger UI説明の充実
   - エンドポイント使用例の追加

2. **パフォーマンステスト**
   - 負荷テスト実施
   - ボトルネック特定・最適化

3. **セキュリティ強化**
   - 認証・認可実装
   - レート制限追加

4. **フロントエンド統合準備**
   - CORS設定確認
   - WebSocket接続テスト

このガイドにより、**バックエンド単体で完全なAPI機能を実装できます**。
