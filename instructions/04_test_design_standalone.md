# テスト詳細設計書 - セキュリティロボット強化学習システム

## 1. テスト戦略概要

### 1.1 テストピラミッド

```
        ┌─────────────┐
       /    E2E Test   \      5% - 10回 - 低速だが高い信頼性
      /─────────────────\
     /  Integration Test \    15% - 50回 - モジュール間統合
    /─────────────────────\
   /   Unit Test (単体)    \  80% - 500回 - 高速で詳細
  /───────────────────────── \
```

#### 各レイヤーの役割

**Unit Test (単体テスト) - 80%**
- **目的**: 個別関数・クラス・コンポーネントの動作検証
- **実行速度**: < 1秒 (全テスト2分以内)
- **カバレッジ目標**:
  - バックエンド: 90%以上
  - フロントエンド: 85%以上
- **ツール**: pytest, Vitest

**Integration Test (統合テスト) - 15%**
- **目的**: モジュール間連携、API統合、WebSocket通信
- **実行速度**: < 30秒
- **カバレッジ目標**: 主要データフロー100%
- **ツール**: pytest, FastAPI TestClient

**E2E Test (エンドツーエンドテスト) - 5%**
- **目的**: 実際のブラウザでのユーザーシナリオ検証
- **実行速度**: < 5分
- **カバレッジ目標**: クリティカルパス100%
- **ツール**: Playwright

### 1.2 品質ゲート

#### コードカバレッジ
- **バックエンド総合**: 90%以上 (pytest-cov)
- **フロントエンド総合**: 85%以上 (Vitest coverage)
- **E2Eカバレッジ**: 主要ユーザーフロー10個以上

#### テスト実行速度
- **単体テスト**: 全体2分以内
- **統合テスト**: 30秒以内
- **E2Eテスト**: 5分以内

#### CI/CD要件
- **プルリクエスト**: すべてのテストが通過必須
- **mainブランチマージ**: カバレッジ低下禁止
- **テスト失敗時**: マージブロック

### 1.3 テスト環境

#### バックエンドテスト環境
```yaml
Python: 3.12
Database: SQLite (in-memory) または PostgreSQL (Docker)
Redis: redis-mock または Redis (Docker)
Testing Framework: pytest 8.x
Coverage Tool: pytest-cov
HTTP Client: httpx (TestClient)
```

#### フロントエンドテスト環境
```yaml
Node.js: 20.x
Testing Framework: Vitest 3.2
Component Testing: @vue/test-utils
DOM Environment: happy-dom
Coverage Tool: @vitest/coverage-v8
E2E Framework: Playwright 1.55
```

## 2. バックエンド単体テスト設計

### 2.1 pytest設定 (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
    --asyncio-mode=auto
markers =
    slow: 遅いテスト
    integration: 統合テスト
    unit: 単体テスト
    e2e: E2Eテスト
```

### 2.2 conftest.py (グローバルフィクスチャ)

```python
# tests/conftest.py

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Application imports
from app.main import app
from app.core.database import Base, get_db
from app.models.database import TrainingSession, TrainingMetrics

# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

@pytest.fixture(scope="session")
def event_loop():
    """イベントループを作成"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    各テストで新しいDBセッションを作成
    テスト終了後にクリーンアップ
    """
    # テーブル作成
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # テーブル削除
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient with database override
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

@pytest.fixture
def sample_training_session(db_session: Session) -> TrainingSession:
    """サンプル学習セッション作成"""
    session = TrainingSession(
        name="Test Session",
        algorithm="ppo",
        environment_type="standard",
        status="created",
        total_timesteps=10000,
        current_timestep=0,
        episodes_completed=0,
        env_width=8,
        env_height=8,
        coverage_weight=1.5,
        exploration_weight=3.0,
        diversity_weight=2.0
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session
```

### 2.3 APIエンドポイントテスト

```python
# tests/unit/api/test_training_endpoints.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

def test_start_training_success(client: TestClient, db_session: Session):
    """
    学習開始APIの正常系テスト

    検証項目:
    - ステータスコード200
    - セッションIDが返る
    - データベースにセッションが保存される
    - Celeryタスクが起動される
    """
    training_data = {
        "name": "Test Training Session",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 10000,
        "env_width": 8,
        "env_height": 8,
        "coverage_weight": 1.5,
        "exploration_weight": 3.0,
        "diversity_weight": 2.0
    }

    with patch('app.tasks.training_tasks.run_training_task') as mock_task:
        mock_task.delay.return_value = MagicMock(id="test-task-id")

        response = client.post("/api/v1/training/start", json=training_data)

        # レスポンス検証
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == training_data["name"]
        assert data["algorithm"] == training_data["algorithm"]
        assert data["status"] == "created"
        assert "id" in data

        # Celeryタスク呼び出し検証
        mock_task.delay.assert_called_once()

def test_start_training_validation_error(client: TestClient):
    """
    学習開始APIのバリデーションエラーテスト

    検証項目:
    - 必須フィールド欠落時422エラー
    - 不正な値の場合422エラー
    """
    # 名前が空
    invalid_data = {
        "name": "",
        "algorithm": "ppo",
        "environment_type": "standard"
    }

    response = client.post("/api/v1/training/start", json=invalid_data)
    assert response.status_code == 422

    # アルゴリズムが不正
    invalid_data = {
        "name": "Test",
        "algorithm": "invalid_algo",
        "environment_type": "standard",
        "total_timesteps": 10000,
        "env_width": 8,
        "env_height": 8
    }

    response = client.post("/api/v1/training/start", json=invalid_data)
    assert response.status_code == 422

def test_get_training_status(
    client: TestClient,
    sample_training_session
):
    """
    学習状態取得APIテスト

    検証項目:
    - 存在するセッションの取得成功
    - 存在しないセッションの404エラー
    """
    session_id = sample_training_session.id

    response = client.get(f"/api/v1/training/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert data["name"] == sample_training_session.name
    assert data["status"] == "created"

def test_get_training_status_not_found(client: TestClient):
    """存在しないセッションID"""
    response = client.get("/api/v1/training/999/status")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_training_service_create_session(db_session: Session):
    """
    TrainingService.create_session() のテスト

    サービス層のビジネスロジックを直接テスト
    """
    from app.services.training_service import TrainingService
    from app.models.schemas import TrainingSessionCreate

    service = TrainingService(db_session)
    config = TrainingSessionCreate(
        name="Service Test Session",
        algorithm="ppo",
        environment_type="enhanced",
        total_timesteps=10000,
        env_width=12,
        env_height=12,
        coverage_weight=2.0,
        exploration_weight=4.0,
        diversity_weight=2.5
    )

    session = await service.create_session(config)

    assert session is not None
    assert session.name == "Service Test Session"
    assert session.algorithm == "ppo"
    assert session.environment_type == "enhanced"
    assert session.status == "created"
```

### 2.4 強化学習環境テスト

```python
# tests/unit/ml/test_environment.py

import pytest
import numpy as np
from typing import Tuple

# 環境クラスの実装例をテスト
class SecurityEnvironment:
    """
    セキュリティロボット環境

    観測空間: (W, H, 3) の3Dテンソル
      - チャンネル0: 脅威レベル (0.0-1.0)
      - チャンネル1: 障害物マップ (0 or 1)
      - チャンネル2: ロボット位置

    行動空間: 4離散行動
      - 0: 前進
      - 1: 左回転
      - 2: 右回転
      - 3: その場巡回
    """
    def __init__(self, width: int = 8, height: int = 8):
        self.width = width
        self.height = height
        self.action_space_n = 4

        # 初期化
        self.robot_x = 0
        self.robot_y = 0
        self.robot_orientation = 0  # 0=北, 1=東, 2=南, 3=西
        self.threat_grid = np.zeros((height, width))
        self.step_count = 0

    def reset(self) -> Tuple[np.ndarray, dict]:
        """環境をリセット"""
        self.robot_x = self.width // 2
        self.robot_y = self.height // 2
        self.robot_orientation = 0
        self.threat_grid = np.random.rand(self.height, self.width) * 0.3
        self.step_count = 0

        observation = self._get_observation()
        info = {"reset": True}
        return observation, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """1ステップ実行"""
        reward = 0.0

        if action == 0:  # 前進
            reward = self._move_forward()
        elif action == 1:  # 左回転
            self.robot_orientation = (self.robot_orientation - 1) % 4
            reward = -0.05
        elif action == 2:  # 右回転
            self.robot_orientation = (self.robot_orientation + 1) % 4
            reward = -0.05
        elif action == 3:  # 巡回
            reward = self._patrol()

        self.step_count += 1
        observation = self._get_observation()
        terminated = False
        truncated = self.step_count >= 1000
        info = {"step": self.step_count}

        return observation, reward, terminated, truncated, info

    def _move_forward(self) -> float:
        """前進処理"""
        dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][self.robot_orientation]
        new_x = self.robot_x + dx
        new_y = self.robot_y + dy

        # 境界チェック
        if 0 <= new_x < self.width and 0 <= new_y < self.height:
            self.robot_x = new_x
            self.robot_y = new_y
            return -0.1  # 移動コスト
        return -0.5  # 壁にぶつかるペナルティ

    def _patrol(self) -> float:
        """巡回処理"""
        threat_level = self.threat_grid[self.robot_y][self.robot_x]
        self.threat_grid[self.robot_y][self.robot_x] *= 0.5  # 脅威レベル減少
        return threat_level * 10  # 脅威削減報酬

    def _get_observation(self) -> np.ndarray:
        """観測取得"""
        obs = np.zeros((self.height, self.width, 3))
        obs[:, :, 0] = self.threat_grid  # 脅威レベル
        obs[self.robot_y, self.robot_x, 2] = 1.0  # ロボット位置
        return obs

@pytest.fixture
def environment():
    """環境フィクスチャ"""
    return SecurityEnvironment(width=8, height=8)

def test_environment_initialization(environment):
    """環境初期化テスト"""
    assert environment.width == 8
    assert environment.height == 8
    assert environment.action_space_n == 4

def test_environment_reset(environment):
    """リセット機能テスト"""
    observation, info = environment.reset()

    # 観測形状確認
    assert observation.shape == (8, 8, 3)

    # ロボット位置が中央付近
    assert 0 <= environment.robot_x < environment.width
    assert 0 <= environment.robot_y < environment.height

    # 情報辞書
    assert "reset" in info

def test_environment_step_move_forward(environment):
    """前進アクションテスト"""
    environment.reset()
    initial_x = environment.robot_x
    initial_y = environment.robot_y

    observation, reward, terminated, truncated, info = environment.step(0)

    # 観測形状
    assert observation.shape == (8, 8, 3)

    # 位置が変わったか（向きによる）
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)

def test_environment_step_turn_left(environment):
    """左回転アクションテスト"""
    environment.reset()
    initial_orientation = environment.robot_orientation

    environment.step(1)  # 左回転

    expected_orientation = (initial_orientation - 1) % 4
    assert environment.robot_orientation == expected_orientation

def test_environment_step_turn_right(environment):
    """右回転アクションテスト"""
    environment.reset()
    initial_orientation = environment.robot_orientation

    environment.step(2)  # 右回転

    expected_orientation = (initial_orientation + 1) % 4
    assert environment.robot_orientation == expected_orientation

def test_environment_step_patrol(environment):
    """巡回アクションテスト"""
    environment.reset()

    # 脅威レベルを設定
    environment.threat_grid[environment.robot_y][environment.robot_x] = 0.5
    initial_threat = environment.threat_grid[environment.robot_y][environment.robot_x]

    observation, reward, terminated, truncated, info = environment.step(3)

    # 脅威レベルが減少
    assert environment.threat_grid[environment.robot_y][environment.robot_x] < initial_threat

    # 報酬がプラス
    assert reward > 0

def test_environment_boundaries(environment):
    """境界テスト"""
    environment.reset()

    # 端に配置
    environment.robot_x = 0
    environment.robot_y = 0
    environment.robot_orientation = 3  # 西向き

    observation, reward, terminated, truncated, info = environment.step(0)

    # 境界外に出ない
    assert environment.robot_x >= 0
    assert environment.robot_y >= 0

    # ペナルティ報酬
    assert reward < 0

@pytest.mark.parametrize("width,height", [(5, 5), (10, 10), (20, 20)])
def test_environment_different_sizes(width, height):
    """異なるサイズの環境テスト"""
    env = SecurityEnvironment(width=width, height=height)

    assert env.width == width
    assert env.height == height

    observation, info = env.reset()
    assert observation.shape == (height, width, 3)
```

### 2.4.1 バッテリーシステムテスト

バッテリーシステムの追加に伴い、以下のテストケースを実装します。

```python
# tests/unit/rl/test_security_env_battery.py

import pytest
from rl.environments.security_env import SecurityEnvironment


@pytest.fixture
def battery_env():
    """バッテリーシステム有効化環境のフィクスチャ"""
    return SecurityEnvironment(width=10, height=10)


def test_battery_initialization(battery_env):
    """バッテリーが100%で初期化されることを確認"""
    obs, info = battery_env.reset()

    assert battery_env.battery_percentage == 100.0
    assert battery_env.is_charging == False
    assert 'battery_percentage' in info
    assert info['battery_percentage'] == 100.0


def test_battery_drain_rate(battery_env):
    """バッテリーが正しく消費されることを確認(1000ステップで1%)"""
    battery_env.reset()

    # 充電ステーションから離れる
    battery_env.robot_x = 0
    battery_env.robot_y = 0

    initial_battery = battery_env.battery_percentage

    # 1000ステップ実行
    for _ in range(1000):
        obs, reward, done, truncated, info = battery_env.step(0)

    # 1%消費されているはず(誤差0.1以内)
    assert abs(battery_env.battery_percentage - (initial_battery - 1.0)) < 0.1


def test_battery_charging_on_station(battery_env):
    """充電ステーション上でバッテリーが充電されることを確認"""
    battery_env.reset()

    # バッテリーを50%に設定
    battery_env.battery_percentage = 50.0

    # 充電ステーション上に配置（既にリセット時に配置されている）
    assert battery_env.robot_x == battery_env.charging_station_x
    assert battery_env.robot_y == battery_env.charging_station_y

    # 10ステップ実行（巡回アクションで充電ステーション上に留まる）
    for _ in range(10):
        obs, reward, done, truncated, info = battery_env.step(3)

    # 10%充電されているはず
    assert abs(battery_env.battery_percentage - 60.0) < 0.1
    assert battery_env.is_charging == True


def test_battery_depletion_penalty(battery_env):
    """バッテリー切れ時に特大ペナルティが付与されることを確認"""
    battery_env.reset()

    # バッテリーを強制的に0%に設定
    battery_env.battery_percentage = 0.001  # ほぼ0

    # 1ステップ実行してバッテリー切れを発生させる
    battery_env.robot_x = 0
    battery_env.robot_y = 0
    obs, reward, done, truncated, info = battery_env.step(0)

    # バッテリー切れによる特大ペナルティ
    assert reward <= -100.0
    assert done == True


def test_observation_space_includes_battery(battery_env):
    """観測空間が5チャンネルであることを確認"""
    obs, info = battery_env.reset()

    # 観測空間は(10, 10, 5)
    assert battery_env.observation_space.shape == (10, 10, 5)
    assert len(obs) == 10
    assert len(obs[0]) == 10
    assert len(obs[0][0]) == 5


def test_charging_station_in_observation(battery_env):
    """観測空間に充電ステーション位置が含まれることを確認"""
    obs, info = battery_env.reset()

    station_x = battery_env.charging_station_x
    station_y = battery_env.charging_station_y

    # チャンネル3に充電ステーションが記録されている
    assert obs[station_y][station_x][3] == 1.0

    # チャンネル4にバッテリー残量（正規化済み）が記録されている
    assert obs[0][0][4] == 1.0  # 100% = 1.0


def test_battery_in_info_dict(battery_env):
    """info辞書にバッテリー情報が含まれることを確認"""
    obs, info = battery_env.reset()

    assert 'battery_percentage' in info
    assert 'is_charging' in info
    assert 'distance_to_charging_station' in info
    assert 'charging_station_position' in info

    assert 0.0 <= info['battery_percentage'] <= 100.0
    assert isinstance(info['is_charging'], bool)
    assert isinstance(info['distance_to_charging_station'], (int, float))
    assert isinstance(info['charging_station_position'], tuple)


def test_charging_stops_when_moving_away(battery_env):
    """充電ステーションから離れると充電が停止することを確認"""
    battery_env.reset()

    # バッテリーを50%に設定
    battery_env.battery_percentage = 50.0

    # 充電ステーション上で充電開始
    obs, reward, done, truncated, info = battery_env.step(3)
    assert battery_env.is_charging == True

    # 充電ステーションから移動
    battery_env.robot_x = 0
    battery_env.robot_y = 0

    obs, reward, done, truncated, info = battery_env.step(0)

    # 充電が停止
    assert battery_env.is_charging == False


def test_partial_charging_strategy(battery_env):
    """部分充電が可能であることを確認（100%まで充電不要）"""
    battery_env.reset()

    # バッテリーを30%に設定
    battery_env.battery_percentage = 30.0

    # 50ステップ充電
    for _ in range(50):
        obs, reward, done, truncated, info = battery_env.step(3)

    # 80%まで充電されている
    assert abs(battery_env.battery_percentage - 80.0) < 0.1

    # 充電ステーションから移動して警備再開
    battery_env.robot_x = 5
    battery_env.robot_y = 5

    obs, reward, done, truncated, info = battery_env.step(0)

    # 充電停止、バッテリーは80%のまま
    assert battery_env.is_charging == False
    assert 75.0 < battery_env.battery_percentage < 85.0


@pytest.mark.integration
def test_battery_full_episode(battery_env):
    """バッテリーシステムを含む完全なエピソードテスト"""
    obs, info = battery_env.reset()

    total_reward = 0.0
    steps = 0
    charging_events = 0
    max_steps = 10000

    while steps < max_steps:
        # ランダムアクション
        import random
        action = random.randint(0, 3)

        obs, reward, done, truncated, info = battery_env.step(action)
        total_reward += reward
        steps += 1

        if info['is_charging']:
            charging_events += 1

        if done:
            break

    # エピソード完了
    assert steps > 0
    # バッテリー切れか、最大ステップ到達
    assert done or steps >= max_steps


@pytest.mark.parametrize("initial_battery,expected_range", [
    (100.0, (99.0, 100.0)),
    (50.0, (49.0, 50.0)),
    (10.0, (9.0, 10.0)),
])
def test_battery_initialization_with_different_values(initial_battery, expected_range):
    """異なる初期バッテリー値でのテスト"""
    env = SecurityEnvironment(width=8, height=8)
    env.reset()

    # 初期バッテリーを設定
    env.battery_percentage = initial_battery

    # 充電ステーションから離れて1ステップ実行
    env.robot_x = 0
    env.robot_y = 0
    obs, reward, done, truncated, info = env.step(0)

    # バッテリーが微減している
    assert expected_range[0] <= info['battery_percentage'] <= expected_range[1]
```

### 2.5 ジョブマネージャーのセッションロック並行制御テスト

セッション粒度ロック導入後は、同一`session_id`に対する`stop`/`resume`呼び出しが厳密に直列化されることをユニットテストで担保する。ロック導入前は状態更新が辞書操作のみで原子的に近かったが、保持件数制御やTTLクリーンアップの追加で処理時間が伸びるため、テストで**順序保証**と**タイムスタンプ整合性**を明確にする。

#### フィクスチャ・計測戦略

- `JobManager`インスタンスをテストごとに生成し、`job_manager_module.utcnow`を`set_time_sequence`で制御してタイムスタンプ比較を容易にする。ロック計測用のイベントを待機するたびに`set_time_sequence`へ次のタイムスタンプを登録し、`utcnow()`呼び出しとロック解放順序が乖離しないよう同期をとる。
- セッションロック導入後は、`JobManager`内部で使用する`asyncio.Lock`をモンキーパッチして、`acquire`前後で`asyncio.Event`を発火させられる`InstrumentedLock`に差し替える。これにより、テスト側で`stop`/`resume`の同期待ち合わせポイントを制御し、意図した順序でタスクを実行できる。イベント解放のたびに`set_time_sequence`へ予定したタイムスタンプを積み増しし、非決定的な`utcnow()`順序を回避する。
- それぞれのAPI呼び出しは`asyncio.create_task`で並列起動し、`asyncio.wait_for`でタイムアウトを掛けることでデッドロックを検知する。

#### 並行シナリオと期待結果

| ケース | 制御した順序 | 期待する最終状態<br>(`JobManager.get` / `TrainingJob.status`) | 追加で確認するポイント |
|--------|---------------|------------------------------------------------------------|-------------------------|
| A | `stop`がロック取得 → メタデータ更新 → `resume`が待機後に実行 | `status="queued"` / `queued`、`resumed_at > stopped_at`、`forced is False` | `stop`呼び出しが返す辞書には`stopped_at`が含まれ、`resume`後に`stopped_at`がクリアされていること |
| B | `resume`が先にロック取得 → 待機中の`stop`が順次実行 | `status="stopped"` / `failed`、`resumed_at`が保持され`stopped_at > resumed_at`、`forced is False` | `stop`完了後でも`resume`で設定した`resumed_at`が消えず、`updated_at`が`stopped_at`と同一であること |
| C | `resume`完了後に`reason="revoked"`の`stop`が実行 | `status="revoked"` / `failed`、`resumed_at`保持、`revoked_at > resumed_at`、`forced is True` | `stop`戻り値に`forced=True`が反映され、履歴クリーンアップ後も`resumed_at`が失われないこと |

> **補足:** テーブルの`status`欄は左側がジョブキュー(`JobManager`)のステータス、右側がDBに永続化される`TrainingJob.status`を表す。`reason="stopped"`/`"revoked"`はキューメタデータへ直接書き込まれる一方、APIレイヤーでは停止後に`TrainingJobStatus.failed`を保存するため、テストでは両者の整合確認が必要になる。

- いずれのケースも`await asyncio.gather(stop_task, resume_task)`で両タスク完了を待ち、`JobManager.snapshot()`を用いて履歴エントリが一件のみであること、`updated_at`が最後に実行された操作のタイムスタンプと一致することを検証する。
- 追加で、異なる`session_id`に対する`stop`と`resume`を同時に起動し、両者が互いに待機しない(完了までの経過時間がロック待ちを伴わない)ことを`time.monotonic()`で測定し、セッション粒度ロックによって全体がシリアライズされていないことを確認する。

#### 実装メモ

- ロックのインスツルメンテーションは `asyncio.Lock` のサブクラスで `acquire()` をオーバーライドし、テストコードに渡された`before_acquire`/`after_release`イベントを操作する。
- タイムスタンプ検証は`set_time_sequence`で`stop`/`resume`ごとに異なる`utcnow()`値を供給し、比較のために`datetime`を固定する。
- 将来的に保持件数制御がエントリ削除を伴う場合に備え、ケースCでは`stop`完了直後に`job_manager.snapshot()`へ`len == 1`をアサートし、クリーンアップが並行実行でもエントリを誤削除しないことを保証する。

## 3. フロントエンド単体テスト設計

### 3.1 Vitest設定 (vitest.config.ts)

```typescript
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'coverage/**',
        'dist/**',
        '**/*.d.ts',
        '**/*{.,-}{test,spec}.?(c|m)[jt]s?(x)',
        '**/__tests__/**',
      ],
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 85,
          statements: 85
        }
      }
    }
  },
  resolve: {
    alias: {
      '~': resolve(__dirname),
      '@': resolve(__dirname)
    }
  }
})
```

### 3.2 Storeテスト

```typescript
// tests/stores/training.test.ts

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTrainingStore } from '~/stores/training'

// モックAPI
const mockApi = {
  get: vi.fn(),
  post: vi.fn()
}

vi.mock('#app', () => ({
  useNuxtApp: () => ({ $api: mockApi })
}))

describe('Training Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('fetchSessions', () => {
    it('should fetch and store training sessions', async () => {
      const mockSessions = [
        {
          id: 1,
          name: 'Session 1',
          algorithm: 'ppo',
          status: 'running'
        },
        {
          id: 2,
          name: 'Session 2',
          algorithm: 'a3c',
          status: 'completed'
        }
      ]

      mockApi.get.mockResolvedValue({ data: mockSessions })

      const store = useTrainingStore()
      await store.fetchSessions()

      expect(mockApi.get).toHaveBeenCalledWith('/training/sessions')
      expect(store.sessions).toEqual(mockSessions)
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should handle fetch error', async () => {
      mockApi.get.mockRejectedValue(new Error('Network error'))

      const store = useTrainingStore()
      await store.fetchSessions()

      expect(store.sessions).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBe('Failed to fetch training sessions')
    })
  })

  describe('createSession', () => {
    it('should create new training session', async () => {
      const newSession = {
        id: 1,
        name: 'New Session',
        algorithm: 'ppo',
        status: 'created'
      }

      const config = {
        name: 'New Session',
        algorithm: 'ppo',
        environment_type: 'standard',
        total_timesteps: 10000,
        env_width: 8,
        env_height: 8
      }

      mockApi.post.mockResolvedValue({ data: newSession })

      const store = useTrainingStore()
      const result = await store.createSession(config)

      expect(mockApi.post).toHaveBeenCalledWith('/training/start', config)
      expect(result).toEqual(newSession)
      expect(store.sessions).toContain(newSession)
      expect(store.currentSession).toEqual(newSession)
    })
  })

  describe('computed properties', () => {
    it('should filter active sessions', () => {
      const store = useTrainingStore()
      store.sessions = [
        { id: 1, status: 'running' },
        { id: 2, status: 'completed' },
        { id: 3, status: 'running' }
      ]

      expect(store.activeSessions).toHaveLength(2)
      expect(store.activeSessions.every(s => s.status === 'running')).toBe(true)
    })
  })
})
```

### 3.3 コンポーネントテスト

```typescript
// tests/components/training/TrainingControl.test.ts

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import TrainingControl from '~/components/training/TrainingControl.vue'
import { useTrainingStore } from '~/stores/training'

describe('TrainingControl Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('should render start training form when no current session', () => {
    const wrapper = mount(TrainingControl)

    expect(wrapper.find('.training-control__start-section').exists()).toBe(true)
    expect(wrapper.find('.training-control__session-control').exists()).toBe(false)
  })

  it('should render session control when current session exists', () => {
    const store = useTrainingStore()
    store.currentSession = {
      id: 1,
      name: 'Test Session',
      status: 'running',
      algorithm: 'ppo',
      progress: 50
    }

    const wrapper = mount(TrainingControl)

    expect(wrapper.find('.training-control__start-section').exists()).toBe(false)
    expect(wrapper.find('.training-control__session-control').exists()).toBe(true)
    expect(wrapper.text()).toContain('Test Session')
  })

  it('should call createSession when form is submitted', async () => {
    const store = useTrainingStore()
    const createSessionSpy = vi.spyOn(store, 'createSession').mockResolvedValue({
      id: 1,
      name: 'Test',
      status: 'created'
    })

    const wrapper = mount(TrainingControl)
    const component = wrapper.vm as any

    component.trainingConfig = {
      name: 'Test Session',
      algorithm: 'ppo',
      environment_type: 'standard',
      total_timesteps: 10000,
      env_width: 8,
      env_height: 8
    }

    await component.startTraining()

    expect(createSessionSpy).toHaveBeenCalledWith(component.trainingConfig)
  })
})
```

### 2.4 バックエンド統合テスト方針

バックエンド統合テストではFastAPIアプリをインメモリSQLiteと一時ストレージで起動し、HTTP層・DB層・ファイルシステムを横断した振る舞いを検証する。`pytest`マーカーは`@pytest.mark.integration`を付与し、CIでは統合テストステージで実行する。

#### 2.4.1 プレイバックAPI

- **対象モジュール:** `app/api/v1/endpoints/playback.py`, `app/services/playback_service.py`, `app/models/environment.py`
- **テストファイル:** `tests/integration/test_playback_endpoints_integration.py`
- **フィクスチャ構成:**
  - `create_app()`で本番と同じルーター構成を生成。
  - `create_async_engine('sqlite+aiosqlite:///:memory:')`でインメモリDBを作成し、`Base.metadata.create_all`を事前実行。
  - `app.dependency_overrides[get_db]`で`AsyncSession`を差し替え、テスト終了時にクリーンアップ。
- **主要シナリオ:**
  1. **セッション一覧のソートとページング**: 異なる`last_recorded_at`を持つジョブとフレームを投入し、`GET /api/v1/playback/sessions?page=1&page_size=10`が最新順(`last_recorded_at DESC`)に並ぶこと、合計件数と`frame_count`が正しいことを検証。
  2. **フレーム取得の順序と分割**: 同一セッションに複数エピソード/ステップを追加し、`GET /api/v1/playback/{session_id}/frames`が`episode ASC, step ASC, id ASC`で整列して返却されること、ページサイズ変更時(`page_size=5`)も空配列を返すことを確認。
  3. **存在しないセッションの404**: `session_id`に存在しない値を指定して404レスポンスとエラーメッセージ(`Training session {id} not found`)を検証。
- **拡張予定:** 録画保持ポリシー実装後は、保持閾値超過時のアーカイブ連携(例: 30日超過フレーム非表示、アーカイブ済みセッションIDの404応答)を追加予定。

#### 2.4.2 ファイル管理API

- **対象モジュール:** `app/api/v1/endpoints/files.py`, `app/core/files/storage.py`, `app/services/files_service.py`
- **テストファイル:** `tests/integration/test_file_management_endpoints.py`
- **フィクスチャ構成:**
  - プレイバックAPIと同様に`create_app()`でアプリを生成し、DBはインメモリSQLiteを使用。
  - `tmp_path`を`storage.STORAGE_ROOT`へモンキーパッチし、アップロードファイルをテスト専用ディレクトリに保存。
- **主要シナリオ:**
  1. **アップロード/ダウンロードの往復確認**: `POST /api/v1/files/`でバイナリデータをアップロードし、DBレコード・保存先パス・レスポンスのメタデータを検証した後、`GET /api/v1/files/{id}/download`で同一バイナリが取得できることを確認。
  2. **存在しないレコードの404**: 未登録IDでダウンロードを要求し、404と`detail`メッセージを検証。
  3. **欠損バイナリの検出**: アップロード後に保存ファイルを削除し、ダウンロード時に404と「missing」系メッセージが返ることを確認。ファイル整合性チェックの回帰テストとして扱う。
- **拡張予定:** 将来的にプレイバックアーカイブZIPを扱う際は、`playback_data/archives/`に生成されたファイルの登録・削除フロー、メタデータの暗号化/署名検証を統合テストでカバーする。

#### 2.4.3 環境セッション操作API

- **対象モジュール:** `app/api/v1/endpoints/environment.py`, `app/core/environment/service.py`
- **テストファイル(新規):** `tests/integration/test_environment_session_endpoints.py`
- **フィクスチャ構成:**
  - `create_app()`でFastAPIアプリを生成し、依存性の`environment_service`をテスト専用インスタンスへ差し替えるための`dependency_overrides`を用意。
  - `EnvironmentService(session_timeout_seconds=2)`のように短いタイムアウトを設定し、`asyncio.sleep`で期限切れ検証が可能なよう制御。
- **主要シナリオ:**
  1. **セッション生成〜操作のハッピーパス:** `POST /api/v1/environment/sessions`で生成したIDを用い、`/reset`・`/action`・`DELETE`が200/204で応答すること、レスポンスの`state.environment_id`と`session_id`が一致することを確認。
  2. **セッションロック直列化:** 同一`session_id`に対する`/reset`と`/action`を`asyncio.gather`で並列送信し、内部ロックにより1件ずつ処理されること(ステップ番号が単調増加、例外が発生しない)を検証。ログを`caplog`で確認し、ロック取得順序(グローバル→セッション)が崩れていないことをアサート。
  3. **タイムアウト自動クリーンアップ:** `session_timeout_seconds=1`でセッション生成後、`asyncio.sleep(1.5)`を挟んで`/action`にアクセスし404となることを確認。`EnvironmentService`の内部辞書からセッションが除去されているかも検証。
  4. **キャパシティ超過エラー:** `max_sessions=1`で2件同時作成を試み、2件目が503(`detail="Environment session capacity exceeded. Please try again later."`)になること、既存セッションが影響を受けないことを確認。
- **補強ポイント:**
  - 期限切れセッションに対する`/reset`/`/action`/`/delete`の404応答を統合テストで共通化し、JobManagerロック戦略との整合性(セッションIDごとの直列化)を設計書へ反映。
  - `EnvironmentService._cleanup_expired_sessions`のデッドロック防止策(グローバルロック→セッションロック順)を回帰テストに含めるため、テスト中に`caplog`や`asyncio.current_task()`を利用してロック順序の逆転が無いことを確認する。
  - 将来的にJobManagerと連携して環境セッションを強制終了するAPIが追加された際のテストテンプレートを流用できるよう、ヘルパー関数でセッション生成と破棄を共通化する。

## 4. E2Eテスト設計 (Playwright)

### 4.1 Playwright設定 (playwright.config.ts)

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }],
  ],

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
})
```

### 4.2 Page Object Pattern

```typescript
// tests/e2e/page-objects/TrainingPage.ts

import { Page, Locator } from '@playwright/test'

export class TrainingPage {
  readonly page: Page
  readonly sessionNameInput: Locator
  readonly algorithmSelect: Locator
  readonly startButton: Locator
  readonly stopButton: Locator

  constructor(page: Page) {
    this.page = page
    this.sessionNameInput = page.locator('[data-testid="session-name-input"]')
    this.algorithmSelect = page.locator('[data-testid="algorithm-select"]')
    this.startButton = page.locator('[data-testid="start-training-button"]')
    this.stopButton = page.locator('[data-testid="stop-training-button"]')
  }

  async goto() {
    await this.page.goto('/training')
  }

  async fillSessionConfig(config: {
    name: string
    algorithm: string
    totalTimesteps: number
  }) {
    await this.sessionNameInput.fill(config.name)
    await this.algorithmSelect.selectOption(config.algorithm)
    await this.page.locator('[data-testid="timesteps-input"]').fill(config.totalTimesteps.toString())
  }

  async clickStartTraining() {
    await this.startButton.click()
  }

  async getSessionName(): Promise<string> {
    return await this.page.locator('[data-testid="session-name"]').textContent() || ''
  }
}
```

### 4.3 E2Eテスト実装

```typescript
// tests/e2e/training-workflow.spec.ts

import { test, expect } from '@playwright/test'
import { TrainingPage } from './page-objects/TrainingPage'

test.describe('Training Workflow', () => {
  test('should create and start training session', async ({ page }) => {
    const trainingPage = new TrainingPage(page)

    await trainingPage.goto()

    await trainingPage.fillSessionConfig({
      name: 'E2E Test Session',
      algorithm: 'ppo',
      totalTimesteps: 10000
    })

    await trainingPage.clickStartTraining()

    await expect(page.locator('.el-message--success')).toBeVisible()
    expect(await trainingPage.getSessionName()).toBe('E2E Test Session')
  })
})
```

## 5. CI/CD統合

### 5.1 GitHub Actions設定

```yaml
# .github/workflows/tests.yml

name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        pip install uv
        uv sync

    - name: Run tests
      run: uv run pytest --cov --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '20'

    - name: Install dependencies
      run: npm ci

    - name: Run tests
      run: npm run test:coverage
```

この設計書により、初見の開発者でも包括的なテストスイートを実装できます。
