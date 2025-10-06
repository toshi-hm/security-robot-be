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
