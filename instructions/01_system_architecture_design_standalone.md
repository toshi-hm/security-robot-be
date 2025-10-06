# セキュリティロボット強化学習システム - 自己完結型アーキテクチャ設計書

## 1. プロジェクト概要

### 1.1 研究背景と目的

本プロジェクトは、強化学習を活用して屋内環境における警備ロボットの巡回ルートと配置場所を最適化する研究システムです。従来の固定的な巡回パターンでは、動的に変化する脅威への対応が困難であり、全エリアの効率的な監視が実現できませんでした。

**解決する課題:**
- 動的環境変化への適応的な巡回ルート生成
- 全エリアの効率的なカバレッジ最大化
- リアルタイム脅威検出と対応の最適化
- 移動コストと監視効果のバランス最適化

**アプローチ:**
メッシュベース環境モデル(格子状に分割された2次元空間)上で、PPO(Proximal Policy Optimization)およびA3C(Asynchronous Advantage Actor-Critic)アルゴリズムを用いてロボットの行動方策を学習します。Web UIによるリアルタイム可視化により、学習過程とロボット行動の詳細な観察が可能です。

### 1.2 現状システムの課題

既存システムはFlask + Dashによるモノリシック構成(単一アプリケーション約2,600行)で、以下の課題があります:

- フロントエンドとバックエンドの密結合による保守性の低下
- 同期的処理によるUI応答性の悪化(学習中UIがフリーズ)
- 状態管理の複雑化(Dashのコールバック地獄)
- 並行開発の困難(フロント・バック分離不可)
- テストの困難(統合テストのみ、単体テスト不可)

### 1.3 新アーキテクチャの利点

分離型アーキテクチャにより以下を実現します:

- **保守性向上**: 関心の分離による明確な責任境界
- **パフォーマンス向上**: 非同期処理とWebSocketによる高速化
- **開発効率向上**: フロント・バックの並行開発可能
- **テスト容易性**: 層ごとの単体テスト実施可能
- **スケーラビリティ**: 将来的な機能拡張への対応力

## 2. システム全体アーキテクチャ

### 2.1 3層アーキテクチャ概要

```
┌─────────────────────────────────────────┐
│   プレゼンテーション層(Frontend)        │
│   Vue.js 3.5 + Nuxt v4 + TypeScript     │
│   - SPAによるリッチなUI体験             │
│   - Composition APIによる状態管理        │
│   - Element Plusコンポーネントライブラリ │
│   - Chart.js/D3.jsによる可視化          │
│   - Socket.IOによるリアルタイム通信      │
└──────────────┬──────────────────────────┘
               │ HTTPS/REST + WebSocket
┌──────────────┴──────────────────────────┐
│   アプリケーション層(Backend API)       │
│   Python 3.12 + FastAPI + PyTorch       │
│   - RESTful APIエンドポイント            │
│   - WebSocket通信マネージャー            │
│   - Celeryバックグラウンドタスク         │
│   - 強化学習エンジン統合                │
└──────────────┬──────────────────────────┘
               │
┌──────────────┴──────────────────────────┐
│   データ・インフラ層                    │
│   PostgreSQL + Redis + Docker           │
│   - 学習セッション・メトリクスDB        │
│   - タスクキュー・キャッシュ            │
│   - コンテナオーケストレーション        │
└─────────────────────────────────────────┘
```

### 2.2 各層の詳細設計

#### 2.2.1 フロントエンド層

**技術スタック:**
- Vue.js 3.5: 最新のComposition APIとscript setup構文
- Nuxt v4: ファイルベースルーティング、SSG/SPA対応
- TypeScript 5.9: 厳格な型チェック(strict mode)
- Element Plus 3.x: 100+の業務用UIコンポーネント
- Pinia 2.x: Vueの公式状態管理(TypeScript完全対応)
- Socket.IO Client 4.8: WebSocketクライアント
- Chart.js 4.5 / D3.js 7.x: データ可視化

**主要機能実装:**

1. **ダッシュボード画面**
   - リアルタイム環境状態表示: D3.jsでヒートマップ描画、脅威レベルを色分け(緑=低、黄=中、赤=高)
   - 学習進捗グラフ: Chart.jsで報酬・損失・カバー率を時系列プロット、リアルタイム更新
   - 統計カード: アクティブジョブ数、完了モデル数、平均報酬などの KPI表示

2. **学習制御画面**
   - パラメータフォーム: Element Plusのel-formで入力検証、アルゴリズム選択(PPO/A3C)、環境サイズ、報酬重み設定
   - 学習開始/停止ボタン: API呼び出し+楽観的UI更新
   - リアルタイム進捗表示: WebSocket経由で受信した進捗データをリアクティブに反映

3. **プレイバック画面**
   - エピソード選択: ドロップダウンで過去の学習セッション選択
   - タイムライン制御: 再生/一時停止、速度調整(0.5x, 1x, 2x)、手動シーク
   - ステップバイステップ表示: 各ステップの環境状態、行動、報酬を可視化

**DDD(Domain-Driven Design)適用:**

```
configs/
  api.ts              # APIエンドポイントURL定義(環境変数から注入)

libs/
  domains/            # ドメインモデル
    training/
      TrainingSession.ts    # 学習セッションのビジネスロジック
      - id, name, algorithm, status, progress()メソッド等
    environment/
      Environment.ts        # 環境状態のビジネスロジック
      - grid, robot, threats, computeCoverageRatio()等

  repositories/       # データアクセス抽象化
    training/
      TrainingRepository.ts    # インターフェース定義
      TrainingRepositoryImpl.ts # $fetch使用の実装
      - findAll(), findById(), start(), stop()等のメソッド

composables/        # アプリケーションロジック
  useTraining.ts    # 学習管理のビジネスロジック
  - TrainingRepositoryを使用してデータ取得・操作
  - リアクティブな状態管理(ref, computed)

stores/             # グローバル状態管理(Pinia)
  training.ts       # Composableを経由してリポジトリ使用

components/         # プレゼンテーション層(表示のみ)
  training/
    TrainingControl.vue  # UIコンポーネント(ロジックなし)
```

**コーディング規約:**
- Vueファイル構造: `<script setup lang="ts">` → `<template>` → `<style lang="scss" scoped>`
- CSS命名: BEM記法 (例: `training-control__button--primary`)
- API通信: 必ずRepository経由(直接$fetch禁止)
- エンドポイント: configs/api.tsで一元管理

#### 2.2.2 バックエンド層

**技術スタック:**
- FastAPI: 高性能非同期Webフレームワーク、自動OpenAPIドキュメント生成
- Uvicorn: ASGI サーバー
- SQLAlchemy 2.0: ORM(非同期対応)
- Alembic: データベースマイグレーション
- Pydantic 2.5: データバリデーション・シリアライゼーション
- PyTorch: 深層学習フレームワーク
- Stable-Baselines3: PPO実装ライブラリ
- Celery: 分散タスクキュー
- Redis: メッセージブローカー・キャッシュ
- PostgreSQL: リレーショナルデータベース

**レイヤー構造:**

```
app/
  main.py                    # FastAPIアプリケーション初期化
  - CORS設定(localhost許可)
  - ルーター登録
  - ライフサイクルイベント(startup/shutdown)

  core/
    config.py                # 環境変数管理(Pydantic Settings)
    database.py              # SQLAlchemy設定、接続プール
    redis_client.py          # Redis接続管理

  api/
    endpoints/
      training.py            # 学習制御API
      - POST /training/start: 学習セッション開始
      - POST /training/{id}/stop: 学習停止
      - GET /training/{id}/status: 状態取得
      - GET /training/{id}/metrics: メトリクス取得

      environment.py         # 環境制御API
      - GET /environment/state: 現在状態
      - POST /environment/reset: リセット
      - POST /environment/action: アクション実行

    websocket/
      connection_manager.py  # WebSocket接続管理
      - connect(), disconnect(), broadcast()
      - セッション別接続管理

      training_events.py     # 学習進捗配信
      - /ws/training/{session_id}エンドポイント
      - 進捗データのリアルタイム配信

  services/
    training_service.py      # 学習管理サービス
    - create_session(): DBにセッション登録
    - start_training(): Celeryタスク起動
    - stop_training(): タスク停止
    - get_metrics(): メトリクス取得

  models/
    database.py              # SQLAlchemyモデル
    schemas.py               # Pydantic スキーマ

  ml/
    environment.py           # Gymnasium環境実装
    training/
      ppo_trainer.py         # PPO学習ロジック
      a3c_trainer.py         # A3C学習ロジック

  tasks/
    training_tasks.py        # Celeryタスク定義
```

**API設計例:**

```python
# POST /api/v1/training/start
# リクエスト:
{
  "name": "実験_PPO_20x20_探索重視",
  "algorithm": "ppo",  # or "a3c"
  "environment_type": "enhanced",  # or "standard"
  "total_timesteps": 50000,
  "env_width": 20,
  "env_height": 20,
  "coverage_weight": 1.5,
  "exploration_weight": 3.0,
  "diversity_weight": 2.0
}

# レスポンス(202 Accepted):
{
  "session_id": 123,
  "name": "実験_PPO_20x20_探索重視",
  "status": "created",
  "created_at": "2025-10-05T12:34:56Z"
}

# 裏側の処理:
# 1. TrainingSessionをDBに登録(status="created")
# 2. Celeryタスクrun_training_task.delay(session_id=123)を起動
# 3. タスク内でPPOTrainerインスタンス化、学習開始
# 4. 100ステップごとにRedis Pub/Subで進捗配信
# 5. WebSocketマネージャーがsession_id=123の全接続に配信
```

**WebSocketプロトコル:**

```javascript
// クライアント→サーバー接続
const socket = io('ws://localhost:8000/ws/training/123');

// 進捗購読
socket.emit('subscribe', {type: 'training_progress'});

// サーバー→クライアント配信(100ステップごと)
socket.on('training_progress', (data) => {
  // data = {
  //   session_id: 123,
  //   timestep: 1000,
  //   episode: 25,
  //   reward: 48.5,
  //   loss: 0.024,
  //   coverage_ratio: 0.82,
  //   timestamp: "2025-10-05T12:35:10Z"
  // }
  updateProgressChart(data);
});
```

#### 2.2.3 データ・インフラ層

**PostgreSQLスキーマ設計:**

```sql
-- 学習セッションテーブル
CREATE TABLE training_sessions (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  algorithm VARCHAR(10) NOT NULL CHECK (algorithm IN ('ppo', 'a3c')),
  environment_type VARCHAR(20) NOT NULL CHECK (environment_type IN ('standard', 'enhanced')),
  status VARCHAR(20) NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'running', 'paused', 'completed', 'failed')),

  total_timesteps INTEGER NOT NULL,
  current_timestep INTEGER DEFAULT 0,
  episodes_completed INTEGER DEFAULT 0,

  env_width INTEGER DEFAULT 8,
  env_height INTEGER DEFAULT 8,

  coverage_weight FLOAT DEFAULT 1.5,
  exploration_weight FLOAT DEFAULT 3.0,
  diversity_weight FLOAT DEFAULT 2.0,

  model_path VARCHAR(512),  -- 学習済みモデルファイルパス
  config JSONB,  -- 詳細パラメータ(JSON形式)

  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,

  INDEX idx_status (status),
  INDEX idx_created_at (created_at DESC)
);

-- 学習メトリクステーブル(時系列データ)
CREATE TABLE training_metrics (
  id SERIAL PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,

  timestep INTEGER NOT NULL,
  episode INTEGER,
  reward FLOAT NOT NULL,
  loss FLOAT,
  coverage_ratio FLOAT,
  exploration_score FLOAT,

  timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_session_timestep (session_id, timestep),
  INDEX idx_timestamp (timestamp DESC)
);

-- 環境状態スナップショット(プレイバック用)
CREATE TABLE environment_states (
  id SERIAL PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
  step INTEGER NOT NULL,

  robot_x INTEGER NOT NULL,
  robot_y INTEGER NOT NULL,
  robot_orientation INTEGER NOT NULL,  -- 0=北, 1=東, 2=南, 3=西

  threat_grid JSONB NOT NULL,  -- [[0.2, 0.5, ...], [...], ...]
  coverage_map JSONB,  -- [[0, 1, ...], [...], ...]
  suspicious_objects JSONB,  -- [{x: 3, y: 5, level: 0.8}, ...]

  timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_session_step (session_id, step)
);
```

**Redis使用用途:**

1. **Celeryブローカー**: タスクキュー管理
2. **Pub/Sub**: 学習進捗のリアルタイム配信
3. **キャッシュ**: APIレスポンスキャッシュ(GET /training/list等)
4. **セッション管理**: WebSocket接続状態

**Docker Compose構成:**

```yaml
version: '3.8'

services:
  # フロントエンド(Nuxt開発サーバー)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
      - NUXT_PUBLIC_WS_URL=ws://localhost:8000
    command: npm run dev

  # バックエンド(FastAPI + Uvicorn)
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/security_robot_rl
      - REDIS_URL=redis://redis:6379
      - CELERY_BROKER_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # PostgreSQL(データベース)
  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=security_robot_rl
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis(メッセージブローカー・キャッシュ)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Celeryワーカー(学習タスク実行)
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/security_robot_rl
      - CELERY_BROKER_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

volumes:
  postgres_data:
```

## 3. 強化学習システムの詳細設計

### 3.1 環境設計

**メッシュベース環境:**

- **空間表現**: W×Hの2次元グリッド(デフォルト8×8、最大50×50)
- **セル状態**: 各セルは脅威レベル(0.0-1.0)、障害物フラグ、訪問カウントを保持
- **ロボット状態**: (x, y)座標、向き(0=北, 1=東, 2=南, 3=西)、エネルギー残量

**観測空間(Observation Space):**

3次元テンソル: (W, H, 3)
- チャンネル0: 脅威レベルマップ(0.0-1.0の連続値)
- チャンネル1: 障害物マップ(0=通行可, 1=障害物)
- チャンネル2: ロボット位置・向きエンコーディング

```python
# 例: 8x8環境の観測
observation = np.array([
  [[0.2, 0, 0], [0.5, 0, 0], [0.3, 1, 0], ...],  # y=0行
  [[0.1, 0, 0], [0.8, 0, 1], [0.4, 0, 0], ...],  # y=1行(robot at (1,1), facing East)
  ...
])
# shape: (8, 8, 3)
```

**行動空間(Action Space):**

離散行動4種類:
- 0: 前進(現在の向きに1セル移動)
- 1: 左回転(向きを反時計回りに90度変更)
- 2: 右回転(向きを時計回りに90度変更)
- 3: その場巡回(現在位置の巡回範囲内の脅威を低減)

**報酬関数:**

標準環境の報酬:
```
R = R_threat + R_suspicious - C_movement
```

拡張環境の報酬:
```
R = R_threat + R_suspicious + w_cov × R_coverage + w_exp × R_exploration + w_div × R_diversity - C_movement
```

詳細計算式:
```python
# 脅威除去報酬
R_threat = Σ(threat_level_before - threat_level_after) × 10
# 巡回アクション実行時、巡回範囲内(radius=2)の全セルの脅威レベルを0.2低減
# 例: 範囲内5セルの脅威が[0.5, 0.6, 0.4, 0.3, 0.2]なら、
#     R_threat = (0.5+0.6+0.4+0.3+0.2 - 0.3-0.4-0.2-0.1-0.0) × 10 = 10.0

# 不審物除去報酬(時間ボーナス)
R_suspicious = 2.0 + (20.0 - 2.0) × (1 - detection_time / max_time)
# 早く発見するほど高報酬
# 例: 最大100ステップで、30ステップで発見した場合
#     R_suspicious = 2.0 + 18.0 × (1 - 30/100) = 2.0 + 12.6 = 14.6

# カバー率報酬(拡張環境のみ)
R_coverage = (visited_cells / total_cells) × coverage_weight
# 例: 64セル中48セル訪問、w_cov=1.5
#     R_coverage = (48/64) × 1.5 = 1.125

# 探索報酬(拡張環境のみ)
R_exploration = is_new_cell × exploration_weight
# 未訪問セルに移動した場合: R_exploration = 1 × 3.0 = 3.0

# 多様性報酬(拡張環境のみ)
R_diversity = (unique_positions_last_N_steps / N) × diversity_weight
# 直近10ステップで8個の異なる位置訪問: (8/10) × 2.0 = 1.6

# 移動コスト
C_movement = 0.1 × is_forward + 0.05 × is_rotation
# 前進: -0.1, 回転: -0.05, 巡回: 0
```

**動的脅威システム:**

```python
# 毎ステップ、全セルの脅威レベルが微増
threat_level += 0.01  # 上限1.0

# 2%確率で不審物配置
if random.random() < 0.02:
    x, y = random_empty_cell()
    suspicious_objects.append({
        'x': x, 'y': y,
        'initial_level': 0.5,
        'spawn_time': current_step
    })

# 不審物周辺の脅威レベル増加(時間経過で拡散)
for obj in suspicious_objects:
    age = current_step - obj['spawn_time']
    spread_radius = min(age // 10, 3)  # 10ステップごとに1セル拡大、最大3セル
    for cell in cells_within_radius(obj['x'], obj['y'], spread_radius):
        cell.threat_level += 0.05
```

### 3.2 PPOアルゴリズム実装

**Stable-Baselines3ベースの実装:**

```python
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

# モデル構築
model = PPO(
    policy="MlpPolicy",  # 多層パーセプトロンポリシー
    env=SecurityEnvironment(width=20, height=20),
    learning_rate=3e-4,
    n_steps=2048,  # ロールアウトステップ数
    batch_size=64,
    n_epochs=10,  # 更新エポック数
    gamma=0.99,  # 割引率
    gae_lambda=0.95,  # GAE (Generalized Advantage Estimation) λ
    clip_range=0.2,  # PPOクリッピング範囲
    ent_coef=0.01,  # エントロピー係数(探索促進)
    vf_coef=0.5,  # Value Function係数
    max_grad_norm=0.5,  # 勾配クリッピング
    verbose=1,
    tensorboard_log="./tensorboard_logs/"
)

# カスタムコールバック(WebSocket進捗配信)
class WebSocketProgressCallback(BaseCallback):
    def __init__(self, session_id, websocket_manager):
        super().__init__()
        self.session_id = session_id
        self.websocket_manager = websocket_manager
        self.step_count = 0

    def _on_step(self) -> bool:
        self.step_count += 1

        # 100ステップごとに進捗配信
        if self.step_count % 100 == 0:
            progress_data = {
                'session_id': self.session_id,
                'timestep': self.step_count,
                'episode': len(self.model.ep_info_buffer),
                'reward': np.mean([ep_info['r'] for ep_info in self.model.ep_info_buffer[-10:]]),
                'loss': self.model.logger.name_to_value.get('train/loss', 0),
                'coverage_ratio': self.locals['infos'][0].get('coverage_ratio', 0)
            }

            # WebSocket経由で全接続クライアントに配信
            asyncio.create_task(
                self.websocket_manager.broadcast_to_session(
                    self.session_id,
                    {'type': 'training_progress', 'data': progress_data}
                )
            )

        return True  # 学習継続

# 学習実行
model.learn(
    total_timesteps=50000,
    callback=WebSocketProgressCallback(session_id, websocket_manager)
)

# モデル保存
model.save(f"models/ppo_session_{session_id}.zip")
```

**ニューラルネットワーク構造(Stable-Baselines3のMlpPolicy):**

```
Input: observation (W×H×3フラット化) = 8×8×3 = 192次元
  ↓
共有特徴抽出層:
  Dense(64) + ReLU
  Dense(64) + ReLU
  ↓
Policy Head(Actor):           Value Head(Critic):
  Dense(64) + ReLU              Dense(64) + ReLU
  Dense(4) + Softmax            Dense(1)
  ↓                             ↓
  行動確率分布                  状態価値V(s)
  [P(a=0), P(a=1),              スカラー値
   P(a=2), P(a=3)]
```

### 3.3 A3Cアルゴリズム実装

**カスタムPyTorch実装:**

```python
import torch
import torch.nn as nn
import torch.multiprocessing as mp

# Actor-Criticネットワーク
class A3CNetwork(nn.Module):
    def __init__(self, input_dim, action_dim):
        super().__init__()
        # 共有特徴抽出
        self.feature = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU()
        )

        # Actor Head
        self.actor = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
            nn.Softmax(dim=-1)
        )

        # Critic Head
        self.critic = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        features = self.feature(x)
        action_probs = self.actor(features)
        state_value = self.critic(features)
        return action_probs, state_value

# グローバル共有ネットワーク
global_network = A3CNetwork(input_dim=192, action_dim=4)
global_network.share_memory()  # プロセス間共有

# ワーカープロセス
def worker_process(worker_id, global_network, session_id, config):
    # ワーカー専用の環境とネットワーク
    env = SecurityEnvironment(width=config['env_width'], height=config['env_height'])
    local_network = A3CNetwork(input_dim=192, action_dim=4)
    optimizer = torch.optim.Adam(global_network.parameters(), lr=3e-4)

    episode_count = 0
    while episode_count < config['max_episodes']:
        # グローバルネットワークの重みをローカルにコピー
        local_network.load_state_dict(global_network.state_dict())

        # エピソード実行(N-stepバッチ収集)
        obs, _ = env.reset()
        done = False
        states, actions, rewards, values = [], [], [], []

        for step in range(config['n_steps']):
            obs_tensor = torch.FloatTensor(obs.flatten())
            action_probs, value = local_network(obs_tensor)

            # 行動サンプリング
            action = torch.multinomial(action_probs, 1).item()
            next_obs, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated

            # バッチに追加
            states.append(obs_tensor)
            actions.append(action)
            rewards.append(reward)
            values.append(value.item())

            obs = next_obs
            if done:
                break

        # GAE(Generalized Advantage Estimation)計算
        advantages = compute_gae(rewards, values, gamma=0.99, lam=0.95)

        # 勾配計算
        policy_loss = 0
        value_loss = 0
        for i in range(len(states)):
            action_probs, value = local_network(states[i])

            # Policy Gradient Loss
            log_prob = torch.log(action_probs[actions[i]])
            policy_loss -= log_prob * advantages[i]

            # Value Function Loss
            target_value = rewards[i] + (0.99 * values[i+1] if i+1 < len(values) else 0)
            value_loss += (value - target_value) ** 2

        total_loss = policy_loss + 0.5 * value_loss - 0.01 * entropy(action_probs)

        # グローバルネットワークを非同期更新
        optimizer.zero_grad()
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(local_network.parameters(), max_norm=0.5)

        # 勾配をグローバルネットワークに適用
        for local_param, global_param in zip(local_network.parameters(), global_network.parameters()):
            global_param.grad = local_param.grad
        optimizer.step()

        episode_count += 1

        # 進捗をWebSocket配信
        if episode_count % 10 == 0:
            broadcast_progress(session_id, worker_id, episode_count, np.mean(rewards))

# 並列学習開始
num_workers = 4
processes = []
for worker_id in range(num_workers):
    p = mp.Process(target=worker_process, args=(worker_id, global_network, session_id, config))
    p.start()
    processes.append(p)

for p in processes:
    p.join()
```

**GAE(Generalized Advantage Estimation)実装:**

```python
def compute_gae(rewards, values, gamma=0.99, lam=0.95):
    advantages = []
    gae = 0

    # 逆順で計算
    for i in reversed(range(len(rewards))):
        if i == len(rewards) - 1:
            next_value = 0
        else:
            next_value = values[i + 1]

        # TD誤差
        delta = rewards[i] + gamma * next_value - values[i]

        # GAE累積
        gae = delta + gamma * lam * gae
        advantages.insert(0, gae)

    return torch.FloatTensor(advantages)
```

## 4. データフローとリアルタイム通信

### 4.1 学習開始から完了までのフロー

```
[ユーザー操作]
  ↓
1. フロントエンド: 学習開始ボタンクリック
   → POST /api/v1/training/start {algorithm: "ppo", total_timesteps: 50000, ...}
  ↓
2. バックエンド(FastAPI):
   → TrainingServiceでセッションDB登録(status="created")
   → Celeryタスクrun_training_task.delay(session_id)を非同期起動
   → レスポンス返却(202 Accepted, session_id: 123)
  ↓
3. フロントエンド:
   → WebSocket接続: ws://localhost:8000/ws/training/123
   → 進捗購読メッセージ送信
  ↓
4. Celeryワーカー(バックグラウンド):
   → セッション情報をDBから取得
   → アルゴリズムに応じてPPOTrainer or A3CTrainerインスタンス化
   → model.learn()実行(数分〜数時間)
  ↓
5. 学習中(100ステップごと):
   → コールバック関数で進捗データ生成
   → Redis Pub/Subで"training_progress_{session_id}"チャンネルに配信
   → WebSocketマネージャーがメッセージ受信
   → 該当session_idの全WebSocket接続にブロードキャスト
  ↓
6. フロントエンド:
   → WebSocketメッセージ受信
   → Piniaストア更新(リアクティブ)
   → Chart.jsグラフ自動更新
  ↓
7. 学習完了:
   → モデル保存(models/ppo_session_123.zip)
   → DB更新(status="completed", model_path="...", completed_at=...)
   → WebSocketで完了通知
  ↓
8. フロントエンド:
   → 完了通知受信
   → 成功メッセージ表示
   → モデル一覧更新
```

### 4.2 WebSocketメッセージフォーマット

**クライアント→サーバー:**

```json
// 進捗購読
{
  "type": "subscribe",
  "events": ["training_progress", "environment_update"]
}

// 購読解除
{
  "type": "unsubscribe",
  "events": ["training_progress"]
}

// Ping(接続維持)
{
  "type": "ping"
}
```

**サーバー→クライアント:**

```json
// 学習進捗
{
  "type": "training_progress",
  "session_id": 123,
  "data": {
    "timestep": 5000,
    "episode": 125,
    "reward": 52.3,
    "loss": 0.0324,
    "coverage_ratio": 0.87,
    "exploration_score": 0.65
  },
  "timestamp": "2025-10-05T12:35:20Z"
}

// 環境状態更新
{
  "type": "environment_update",
  "session_id": 123,
  "data": {
    "step": 450,
    "robot": {"x": 12, "y": 8, "orientation": 1},
    "threat_grid": [[0.2, 0.5, ...], [...], ...],
    "suspicious_objects": [{"x": 5, "y": 3, "level": 0.7}]
  },
  "timestamp": "2025-10-05T12:35:21Z"
}

// 学習完了
{
  "type": "training_complete",
  "session_id": 123,
  "data": {
    "status": "completed",
    "model_path": "models/ppo_session_123.zip",
    "final_reward": 68.5,
    "total_episodes": 150,
    "duration_seconds": 1245
  },
  "timestamp": "2025-10-05T13:00:00Z"
}

// エラー
{
  "type": "error",
  "session_id": 123,
  "data": {
    "code": "TRAINING_FAILED",
    "message": "GPU out of memory",
    "details": {...}
  },
  "timestamp": "2025-10-05T12:40:00Z"
}
```

### 4.3 非同期処理とパフォーマンス最適化

**Celeryタスクキューアーキテクチャ:**

```
[FastAPI]                 [Redis]               [Celery Worker 1]
                         (Broker)
API Request    ──┐                              ┌─→ PPO Training
  ↓              │                              │
create_session() │      Queue: tasks            │
  ↓              ├──→ [task_1, task_2, ...] ───┤
task.delay()   ──┘         ↓                   │
  ↓                    Result Backend           ├─→ A3C Training
return 202              (Stored Results)        │   (Worker 2)
                            ↓                   │
                        [success/failure]       └─→ Data Processing
                                                    (Worker 3)
```

**データベースクエリ最適化:**

```python
# 悪い例: N+1クエリ問題
sessions = db.query(TrainingSession).all()
for session in sessions:
    metrics = db.query(TrainingMetrics).filter_by(session_id=session.id).all()  # N回実行

# 良い例: JOIN + Eager Loading
from sqlalchemy.orm import joinedload

sessions = db.query(TrainingSession).options(
    joinedload(TrainingSession.metrics)
).all()
# 1回のクエリで全データ取得

# インデックス活用
# CREATE INDEX idx_session_timestep ON training_metrics(session_id, timestep);
recent_metrics = db.query(TrainingMetrics).filter(
    TrainingMetrics.session_id == 123,
    TrainingMetrics.timestep >= 4000
).order_by(TrainingMetrics.timestep.desc()).limit(1000).all()
# インデックススキャンで高速化
```

**APIレスポンスキャッシュ(Redis):**

```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

@router.get("/training/list")
async def list_training_sessions():
    # キャッシュキー
    cache_key = "training:list:all"

    # キャッシュから取得試行
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # キャッシュミス→DB問い合わせ
    sessions = db.query(TrainingSession).all()
    result = [session.to_dict() for session in sessions]

    # キャッシュに保存(60秒TTL)
    redis_client.setex(cache_key, 60, json.dumps(result))

    return result
```

## 5. セキュリティと品質保証

### 5.1 セキュリティ設計(ローカル環境)

**CORS設定:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Nuxt開発サーバー
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**入力検証(Pydantic):**

```python
from pydantic import BaseModel, Field, validator

class TrainingConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    algorithm: Literal["ppo", "a3c"]
    total_timesteps: int = Field(..., gt=0, le=1000000)
    env_width: int = Field(8, ge=3, le=50)
    env_height: int = Field(8, ge=3, le=50)
    coverage_weight: float = Field(1.5, ge=0.0, le=10.0)
    exploration_weight: float = Field(3.0, ge=0.0, le=10.0)

    @validator('algorithm')
    def algorithm_must_be_valid(cls, v):
        if v not in ['ppo', 'a3c']:
            raise ValueError('algorithm must be ppo or a3c')
        return v
```

**エラーハンドリング:**

```python
from fastapi import HTTPException

class TrainingError(Exception):
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code

@app.exception_handler(TrainingError)
async def training_error_handler(request: Request, exc: TrainingError):
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )
```

### 5.2 テスト戦略

**単体テスト(pytest):**

```python
# tests/test_training_service.py
import pytest
from app.services.training_service import TrainingService
from app.models.schemas import TrainingConfigCreate

@pytest.fixture
def training_service(db_session):
    return TrainingService(db_session)

def test_create_session(training_service):
    config = TrainingConfigCreate(
        name="Test PPO",
        algorithm="ppo",
        total_timesteps=1000,
        env_width=8,
        env_height=8
    )

    session = training_service.create_session(config)

    assert session.id is not None
    assert session.name == "Test PPO"
    assert session.algorithm == "ppo"
    assert session.status == "created"
    assert session.total_timesteps == 1000

def test_start_training_invalid_session(training_service):
    with pytest.raises(ValueError, match="Session not found"):
        training_service.start_training(session_id=99999)
```

**E2Eテスト(Playwright):**

```typescript
// tests/e2e/training.spec.ts
import { test, expect } from '@playwright/test';

test('学習セッション作成から完了までのフロー', async ({ page }) => {
  // ダッシュボードに移動
  await page.goto('http://localhost:3000');

  // 学習設定ページに移動
  await page.click('text=新規学習');

  // パラメータ入力
  await page.fill('input[name="name"]', 'E2Eテスト_PPO');
  await page.selectOption('select[name="algorithm"]', 'ppo');
  await page.fill('input[name="total_timesteps"]', '1000');

  // 学習開始
  await page.click('button:has-text("学習開始")');

  // 進捗画面に遷移
  await expect(page).toHaveURL(/\/training\/\d+/);

  // 進捗バーが表示されることを確認
  await expect(page.locator('.progress-bar')).toBeVisible();

  // WebSocketで進捗が更新されることを確認
  await page.waitForSelector('text=/Timestep: [1-9]/');

  // 学習完了まで待機(最大30秒)
  await page.waitForSelector('text=学習完了', { timeout: 30000 });

  // モデル一覧に表示されることを確認
  await page.click('text=モデル一覧');
  await expect(page.locator('text=E2Eテスト_PPO')).toBeVisible();
});
```

## 6. 運用と監視

### 6.1 ログ管理

**構造化ログ(JSON形式):**

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

# 設定
handler = logging.FileHandler("logs/app.log")
handler.setFormatter(JSONFormatter())
logger = logging.getLogger("security_robot_rl")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# 使用例
logger.info("Training session started", extra={
    "session_id": 123,
    "algorithm": "ppo",
    "total_timesteps": 50000
})
```

**ログローテーション:**

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5  # 最大5ファイル保持
)
```

### 6.2 デプロイメントとCI/CD

**GitHub Actions CI/CD:**

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: cd frontend && npm ci
      - run: cd frontend && npm run test:unit
      - run: cd frontend && npm run build

  e2e-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: docker-compose up -d
      - uses: actions/setup-node@v3
      - run: cd frontend && npx playwright install
      - run: cd frontend && npm run test:e2e
```

## 7. まとめと今後の拡張性

### 7.1 アーキテクチャの利点

1. **明確な責任分離**: フロント・バック・データ層の独立性
2. **非同期処理**: 学習タスクによるUIブロッキング防止
3. **リアルタイム性**: WebSocketによる即座な状態反映
4. **テスト容易性**: 各層の独立したテスト実施
5. **拡張性**: 新機能追加時の影響範囲限定

### 7.2 将来的な拡張可能性

- **マルチエージェント対応**: 複数ロボットの協調学習
- **クラウド展開**: AWS/GCP等へのスケールアウト
- **リアルタイムダッシュボード**: Grafana統合
- **モデル自動最適化**: ハイパーパラメータチューニング自動化
- **実機連携**: ROSとの統合による物理ロボット制御

このアーキテクチャにより、研究効率と システム品質の両立を実現します。
