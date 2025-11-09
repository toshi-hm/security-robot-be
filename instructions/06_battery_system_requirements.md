# バッテリーシステム要件定義書

**作成日:** 2025-11-09
**バージョン:** 1.0
**対象システム:** セキュリティロボット強化学習システム

## 📋 目次

1. [概要](#1-概要)
2. [システム目的](#2-システム目的)
3. [機能要件](#3-機能要件)
4. [強化学習との統合](#4-強化学習との統合)
5. [技術仕様](#5-技術仕様)
6. [実装範囲](#6-実装範囲)
7. [テスト要件](#7-テスト要件)
8. [制約事項](#8-制約事項)

---

## 1. 概要

### 1.1 背景

警備ロボットの実運用では、バッテリー残量の管理が重要な課題となります。現実的な警備シナリオでは、ロボットは限られたエネルギーで効率的に警備を行い、適切なタイミングで充電ステーションに戻る必要があります。

### 1.2 スコープ

本要件定義書は、警備ロボット強化学習システムにバッテリー管理機能を追加することを目的としています。バッテリーシステムは以下を実現します：

- リアルタイムのバッテリー残量管理
- 充電ステーションによる自動充電
- バッテリー切れ時のペナルティ機構
- 強化学習による充電タイミングの最適化

---

## 2. システム目的

### 2.1 主要目的

1. **現実的な制約の導入**: 実際の警備ロボットが直面するエネルギー制約をシミュレーション
2. **戦略的意思決定**: 警備継続と充電のトレードオフを強化学習で最適化
3. **運用効率の向上**: 限られたエネルギーで最大の警備効果を実現
4. **リスク管理**: バッテリー切れによる警備中断リスクを学習

### 2.2 期待される効果

- **効率的な警備経路**: バッテリー残量を考慮した最適な巡回経路の学習
- **適応的な充電戦略**: 環境の脅威レベルに応じた柔軟な充電判断
- **長期的な計画能力**: 将来のバッテリー消費を予測した行動選択

---

## 3. 機能要件

### 3.1 バッテリー管理

#### 3.1.1 バッテリー残量

**要件ID: BAT-001**

- **初期状態**: 警備開始時、バッテリー残量は100%
- **減少率**: 1000ステップごとに1%減少
  - 1ステップあたり: 0.001%減少
  - 例: 10,000ステップで10%減少
- **最小値**: 0%（この時点で警備不能）
- **最大値**: 100%

```python
# 計算式
battery_percentage = initial_battery - (timestep / 1000.0)
battery_percentage = max(0.0, min(100.0, battery_percentage))
```

#### 3.1.2 バッテリー切れ時の挙動

**要件ID: BAT-002**

バッテリーが0%に達した場合：
- ロボットは全ての警備活動を停止
- 移動不可（充電ステーションへの移動も不可）
- 脅威検知・除去不可
- 特大ペナルティを付与: **-100.0ポイント**

### 3.2 充電ステーション

#### 3.2.1 配置仕様

**要件ID: CHG-001**

- **位置**: マップ内のランダムな座標に1箇所配置（エピソードごとに変更）
- **初期位置**: ロボットのスタート地点と同一
- **配置制約**:
  - 障害物のないセルに配置
  - マップの境界から最低1セル離れた位置
  - エピソードごとに異なる位置に配置
- **強化学習での最適化**:
  - エージェントは観測空間（チャンネル3）から充電ステーション位置を認識
  - 様々な充電ステーション位置で学習することで、適応的な警備戦略を獲得
  - 充電ステーション位置に応じた最適な充電タイミングと経路を学習

#### 3.2.2 充電メカニズム

**要件ID: CHG-002**

- **充電条件**: ロボットが充電ステーションの座標に位置する
- **充電速度**: 1ステップごとに1%上昇
- **充電中の制約**:
  - 警備活動不可（脅威検知・除去なし）
  - 移動可能（充電を中断して移動可）
- **充電の開始**: 充電ステーション上に移動することで自動開始
- **充電の終了**: 充電ステーションから離れることで自動終了

```python
# 充電処理の擬似コード
if (robot_x, robot_y) == charging_station_position:
    if battery_percentage < 100.0:
        battery_percentage = min(100.0, battery_percentage + 1.0)
        is_charging = True
        # 充電中は警備活動を実施しない
    else:
        is_charging = False
else:
    is_charging = False
```

### 3.3 充電戦略の最適化

#### 3.3.1 部分充電の許容

**要件ID: CHG-003**

- ロボットは100%まで充電する必要はない
- 環境の脅威レベルや位置に応じて、途中で充電を中断可能
- 充電継続 vs 警備再開の判断は強化学習で最適化

**例:**
```
シナリオ1: 脅威レベルが全体的に低い場合
→ 100%まで充電してから警備を再開

シナリオ2: 高脅威エリアが検出された場合
→ 50%程度で充電を中断し、即座に対応

シナリオ3: バッテリー残量が30%で、充電ステーションから遠い場合
→ 早めに充電ステーションへ戻る判断を学習
```

#### 3.3.2 バッテリー切れ回避

**要件ID: CHG-004**

- **最重要制約**: 充電ステーションに戻れる十分なバッテリーを確保
- **失敗時のペナルティ**: 充電ステーションに戻る前にバッテリーが0%になった場合
  - 特大ペナルティ: **-100.0ポイント**
  - エピソード終了（terminated = True）

**距離とバッテリー計算:**
```python
# 充電ステーションまでのマンハッタン距離
distance_to_station = abs(robot_x - station_x) + abs(robot_y - station_y)

# 必要な最低バッテリー残量（安全マージン込み）
# 1ステップあたり0.001%消費、移動アクションのみと仮定
required_battery = (distance_to_station * 0.001) * 1.5  # 1.5倍の安全マージン
```

---

## 4. 強化学習との統合

### 4.1 観測空間の拡張

**要件ID: OBS-001**

現在の観測空間 `(width, height, 3)` を `(width, height, 5)` に拡張：

```python
# チャンネル0: 脅威レベルマップ (0.0-1.0)
# チャンネル1: 障害物マップ (0.0 or 1.0)
# チャンネル2: ロボット位置・向きエンコーディング (0.0-1.0)
# チャンネル3: 充電ステーション位置マップ (0.0 or 1.0)  ← 新規
# チャンネル4: バッテリー残量（全セルで同一値） (0.0-1.0)  ← 新規

observation[station_x][station_y][3] = 1.0  # 充電ステーション位置
observation[:, :, 4] = battery_percentage / 100.0  # 正規化されたバッテリー残量
```

### 4.2 行動空間

**要件ID: ACT-001**

現在の行動空間は変更なし（Discrete(4)を維持）:
- 0: 前進
- 1: 左回転
- 2: 右回転
- 3: 巡回（その場で警備活動）

**理由:**
- 充電は充電ステーション上に移動することで自動的に開始
- 充電の終了は移動アクションで自動的に実行
- 明示的な「充電開始」「充電終了」アクションは不要

### 4.3 報酬関数の拡張

**要件ID: REW-001**

#### 4.3.1 基本報酬の修正

```python
# 既存の報酬
R_base = R_threat + R_suspicious + w_cov × R_coverage + w_exp × R_exploration + w_div × R_diversity - C_movement

# バッテリーペナルティを追加
R_total = R_base + R_battery_penalty + R_charging_efficiency
```

#### 4.3.2 バッテリーペナルティ

```python
# バッテリー切れペナルティ
if battery_percentage <= 0.0:
    R_battery_penalty = -100.0  # 特大ペナルティ
    terminated = True

# バッテリー低下警告（段階的ペナルティ）
elif battery_percentage < 20.0:
    # 20%未満で小ペナルティを付与（充電を促す）
    R_battery_penalty = -0.5 * (20.0 - battery_percentage) / 20.0
    # 例: 10%の場合、-0.25ポイント

elif battery_percentage < 10.0:
    # 10%未満で中ペナルティ（緊急充電を促す）
    R_battery_penalty = -1.0 * (10.0 - battery_percentage) / 10.0
    # 例: 5%の場合、-0.5ポイント

else:
    R_battery_penalty = 0.0
```

#### 4.3.3 充電効率報酬

```python
# 充電中の機会損失コスト
if is_charging:
    # 充電中は警備できないため、環境の平均脅威レベルに応じたコストを付与
    avg_threat = sum(sum(row) for row in threat_levels) / (width * height)
    R_charging_efficiency = -0.1 * avg_threat
    # 脅威レベルが高いほど、充電中のコストが大きい

    # ただし、バッテリーが極端に低い場合はコストを減免（充電が必要）
    if battery_percentage < 30.0:
        R_charging_efficiency *= 0.5  # コストを半減

else:
    R_charging_efficiency = 0.0
```

#### 4.3.4 充電ステーションからの距離ペナルティ

```python
# バッテリー残量が少ない時、充電ステーションから離れるペナルティ
if battery_percentage < 30.0:
    distance_to_station = abs(robot_x - station_x) + abs(robot_y - station_y)
    max_distance = width + height

    # 距離が遠く、バッテリーが少ないほどペナルティ
    R_distance_penalty = -0.2 * (distance_to_station / max_distance) * (1.0 - battery_percentage / 30.0)
    # 例: バッテリー15%, 距離20/40の場合、-0.05ポイント
else:
    R_distance_penalty = 0.0

R_total += R_distance_penalty
```

### 4.4 Info辞書の拡張

**要件ID: INFO-001**

`step()` メソッドの `info` 辞書に以下を追加:

```python
info = {
    # 既存のキー
    'coverage_ratio': coverage_ratio,
    'visited_cells': visited_count,
    'exploration_reward': exploration_reward,

    # バッテリー関連の新規キー
    'battery_percentage': battery_percentage,
    'is_charging': is_charging,
    'distance_to_charging_station': distance_to_station,
    'charging_station_position': (station_x, station_y),
}
```

---

## 5. 技術仕様

### 5.1 環境クラスの変更

#### 5.1.1 SecurityEnvironment

**ファイル:** `rl/environments/security_env.py`

**新規属性:**
```python
class SecurityEnvironment(gym.Env):
    def __init__(self, ...):
        # 既存の属性
        self.width = width
        self.height = height
        ...

        # バッテリー関連の新規属性
        self.initial_battery = 100.0
        self.battery_percentage = 100.0
        self.battery_drain_rate = 0.001  # 1ステップあたり0.001%
        self.battery_charge_rate = 1.0   # 1ステップあたり1%
        self.charging_station_x = width // 2
        self.charging_station_y = height // 2
        self.is_charging = False

        # 観測空間を拡張
        self.observation_space = spaces.Box(
            low=0,
            high=1,
            shape=(width, height, 5),  # 3 → 5に変更
        )
```

**reset()メソッドの変更:**
```python
def reset(self, *, seed=None, options=None):
    super().reset(seed=seed)

    # 既存の初期化
    self.threat_levels = self._build_grid(0.0)
    ...

    # バッテリーの初期化
    self.battery_percentage = self.initial_battery
    self.is_charging = False

    # ロボットを充電ステーション上に配置
    self.robot_x = self.charging_station_x
    self.robot_y = self.charging_station_y
    self.robot_direction = 0

    return self._get_observation(), {}
```

**step()メソッドの変更:**
```python
def step(self, action):
    self.time_step += 1

    # バッテリー消費
    self._update_battery()

    # バッテリー切れチェック
    if self.battery_percentage <= 0.0:
        # 特大ペナルティとエピソード終了
        reward = -100.0
        terminated = True
        return self._get_observation(), reward, terminated, False, self._get_info()

    # 既存の処理
    self._update_threat_levels()
    self._add_suspicious_objects()

    # 充電中は警備活動を制限
    if self.is_charging:
        reward = self._calculate_charging_reward()
    else:
        reward = self._execute_action(action)

    # バッテリー関連の報酬調整
    reward += self._calculate_battery_penalty()

    terminated = self.time_step >= 1000

    return self._get_observation(), reward, terminated, False, self._get_info()
```

**新規メソッド:**
```python
def _update_battery(self):
    """バッテリー残量を更新"""
    # 充電ステーション上にいる場合
    if (self.robot_x == self.charging_station_x and
        self.robot_y == self.charging_station_y):
        # 充電
        if self.battery_percentage < 100.0:
            self.battery_percentage = min(100.0,
                self.battery_percentage + self.battery_charge_rate)
            self.is_charging = True
        else:
            self.is_charging = False
    else:
        # 充電ステーション外では消費
        self.battery_percentage -= self.battery_drain_rate
        self.battery_percentage = max(0.0, self.battery_percentage)
        self.is_charging = False

def _calculate_battery_penalty(self):
    """バッテリー関連のペナルティを計算"""
    penalty = 0.0

    # バッテリー低下警告
    if self.battery_percentage < 20.0:
        penalty -= 0.5 * (20.0 - self.battery_percentage) / 20.0

    if self.battery_percentage < 10.0:
        penalty -= 1.0 * (10.0 - self.battery_percentage) / 10.0

    # 充電ステーションからの距離ペナルティ
    if self.battery_percentage < 30.0:
        distance = abs(self.robot_x - self.charging_station_x) + \
                   abs(self.robot_y - self.charging_station_y)
        max_distance = self.width + self.height
        penalty -= 0.2 * (distance / max_distance) * \
                   (1.0 - self.battery_percentage / 30.0)

    return penalty

def _calculate_charging_reward(self):
    """充電中の報酬を計算"""
    # 平均脅威レベルに応じた機会損失コスト
    avg_threat = sum(sum(row) for row in self.threat_levels) / \
                 (self.width * self.height)
    reward = -0.1 * avg_threat

    # バッテリーが低い場合はコスト減免
    if self.battery_percentage < 30.0:
        reward *= 0.5

    return reward

def _get_info(self):
    """Info辞書を生成"""
    distance_to_station = abs(self.robot_x - self.charging_station_x) + \
                          abs(self.robot_y - self.charging_station_y)

    return {
        'battery_percentage': self.battery_percentage,
        'is_charging': self.is_charging,
        'distance_to_charging_station': distance_to_station,
        'charging_station_position': (self.charging_station_x,
                                      self.charging_station_y),
    }
```

**_get_observation()メソッドの変更:**
```python
def _get_observation(self):
    """観測空間を生成（5チャンネル）"""
    observation = [[[0.0] * 5 for _ in range(self.height)]
                   for _ in range(self.width)]

    for x in range(self.width):
        for y in range(self.height):
            # チャンネル0: 脅威レベル
            observation[x][y][0] = float(self.threat_levels[x][y])

            # チャンネル1: 障害物
            observation[x][y][1] = 1.0 if self.obstacles[x][y] else 0.0

            # チャンネル3: 充電ステーション
            if x == self.charging_station_x and y == self.charging_station_y:
                observation[x][y][3] = 1.0

            # チャンネル4: バッテリー残量（正規化）
            observation[x][y][4] = self.battery_percentage / 100.0

    # チャンネル2: ロボット位置・向き
    observation[self.robot_x][self.robot_y][2] = (self.robot_direction + 1) / 4.0

    return observation
```

#### 5.1.2 EnhancedSecurityEnvironment

**ファイル:** `rl/environments/enhanced_env.py`

EnhancedSecurityEnvironmentは基本的にSecurityEnvironmentを継承しているため、最小限の変更で対応可能：

```python
class EnhancedSecurityEnvironment(SecurityEnvironment):
    def __init__(self, ..., **kwargs):
        # 親クラスの初期化（バッテリーシステム含む）
        super().__init__(**kwargs)

        # 拡張環境固有の初期化
        self.coverage_weight = coverage_weight
        ...
```

### 5.2 データベースモデルの拡張

#### 5.2.1 EnvironmentState

**ファイル:** `app/models/environment.py`

プレイバック用のEnvironmentStateモデルにバッテリー情報を追加:

```python
class EnvironmentState(Base):
    __tablename__ = "environment_states"

    # 既存のカラム
    id = Column(Integer, primary_key=True)
    session_id = Column(String, index=True)
    timestep = Column(Integer)
    robot_x = Column(Integer)
    robot_y = Column(Integer)
    robot_orientation = Column(Integer)

    # バッテリー関連の新規カラム
    battery_percentage = Column(Float, nullable=False, default=100.0)
    is_charging = Column(Boolean, nullable=False, default=False)
    charging_station_x = Column(Integer, nullable=True)
    charging_station_y = Column(Integer, nullable=True)

    # 既存のJSON カラム
    threat_grid = Column(JSONB)
    coverage_map = Column(JSONB)
    suspicious_objects = Column(JSONB)
    action_taken = Column(Integer)
    reward_received = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

#### 5.2.2 TrainingMetric

**ファイル:** `app/models/training.py`

学習メトリクスにバッテリー関連情報を追加:

```python
class TrainingMetric(Base):
    __tablename__ = "training_metrics"

    # 既存のカラム
    ...

    # additional_metricsにバッテリー情報を含める
    # additional_metrics JSONBカラムの例:
    # {
    #   "battery_percentage": 75.5,
    #   "charging_events": 3,
    #   "battery_depleted": false,
    #   "avg_battery": 65.2
    # }
```

### 5.3 Pydanticスキーマの拡張

#### 5.3.1 EnvironmentStateResponse

**ファイル:** `app/schemas/environment.py`

```python
class EnvironmentStateResponse(BaseModel):
    session_id: str
    timestep: int
    robot_x: int
    robot_y: int
    robot_orientation: int

    # バッテリー関連フィールド
    battery_percentage: float
    is_charging: bool
    charging_station_x: int | None = None
    charging_station_y: int | None = None

    threat_grid: list[list[float]]
    coverage_map: list[list[bool]] | None = None
    suspicious_objects: list[dict] | None = None
    action_taken: int | None = None
    reward_received: float | None = None
    created_at: datetime
```

---

## 6. 実装範囲

### 6.1 Phase 1: 環境実装（優先度: 高）

**期間:** 1-2日

- [ ] `rl/environments/security_env.py` の修正
  - [ ] バッテリー属性の追加
  - [ ] `reset()` メソッドの更新
  - [ ] `step()` メソッドの更新
  - [ ] バッテリー管理メソッドの実装
  - [ ] 観測空間の拡張（5チャンネル）
  - [ ] 報酬関数の調整

- [ ] `rl/environments/enhanced_env.py` の動作確認
  - [ ] 親クラス変更の反映確認
  - [ ] 拡張報酬関数との整合性確認

### 6.2 Phase 2: テスト実装（優先度: 高）

**期間:** 1日

- [ ] `tests/unit/rl/test_security_env.py` の追加
  - [ ] バッテリー初期化テスト
  - [ ] バッテリー消費テスト
  - [ ] 充電メカニズムテスト
  - [ ] バッテリー切れペナルティテスト
  - [ ] 観測空間形状テスト
  - [ ] Info辞書テスト

- [ ] `tests/integration/test_battery_training.py` の追加
  - [ ] PPOトレーニングとの統合テスト
  - [ ] バッテリー管理の学習確認

### 6.3 Phase 3: データベース・API実装（優先度: 中）

**期間:** 1日

- [ ] データベースマイグレーション
  - [ ] `alembic` マイグレーションスクリプトの作成
  - [ ] `environment_states` テーブルの更新

- [ ] Pydanticスキーマの更新
  - [ ] `EnvironmentStateResponse` の拡張
  - [ ] バリデーション追加

- [ ] APIエンドポイントの確認
  - [ ] プレイバックAPIでのバッテリー情報の表示確認
  - [ ] WebSocket通知へのバッテリー情報追加

### 6.4 Phase 4: ドキュメント更新（優先度: 中）

**期間:** 半日

- [ ] 設計書の更新
  - [ ] `01_system_architecture_design_standalone.md` の更新
  - [ ] `02_backend_api_design_standalone.md` の更新
  - [ ] `04_test_design_standalone.md` の更新

- [ ] プロジェクト進捗の更新
  - [ ] `report/PROGRESS.md` の更新
  - [ ] `report/DIARY05.md` の新規セッション記録

---

## 7. テスト要件

### 7.1 ユニットテスト

#### 7.1.1 バッテリー管理テスト

```python
def test_battery_initialization():
    """バッテリーが100%で初期化されることを確認"""
    env = SecurityEnvironment(width=10, height=10)
    obs, info = env.reset()
    assert env.battery_percentage == 100.0
    assert env.is_charging == False

def test_battery_drain():
    """バッテリーが正しく消費されることを確認"""
    env = SecurityEnvironment(width=10, height=10)
    env.reset()

    # 充電ステーションから離れる
    env.robot_x = 0
    env.robot_y = 0

    # 1000ステップ実行
    for _ in range(1000):
        obs, reward, done, truncated, info = env.step(0)

    # 1%消費されているはず
    assert abs(env.battery_percentage - 99.0) < 0.1

def test_battery_charging():
    """充電ステーションでバッテリーが充電されることを確認"""
    env = SecurityEnvironment(width=10, height=10)
    env.reset()

    # バッテリーを50%に設定
    env.battery_percentage = 50.0

    # 充電ステーション上で10ステップ実行
    for _ in range(10):
        obs, reward, done, truncated, info = env.step(3)  # 巡回アクション

    # 10%充電されているはず
    assert abs(env.battery_percentage - 60.0) < 0.1
    assert env.is_charging == True

def test_battery_depletion_penalty():
    """バッテリー切れ時に特大ペナルティが付与されることを確認"""
    env = SecurityEnvironment(width=10, height=10)
    env.reset()

    # バッテリーを強制的に0にする
    env.battery_percentage = 0.0

    obs, reward, done, truncated, info = env.step(0)

    assert reward == -100.0
    assert done == True

def test_observation_space_shape():
    """観測空間が5チャンネルであることを確認"""
    env = SecurityEnvironment(width=10, height=10)
    obs, info = env.reset()

    assert env.observation_space.shape == (10, 10, 5)
    assert len(obs) == 10
    assert len(obs[0]) == 10
    assert len(obs[0][0]) == 5

def test_charging_station_in_observation():
    """観測空間に充電ステーション位置が含まれることを確認"""
    env = SecurityEnvironment(width=10, height=10)
    obs, info = env.reset()

    station_x = env.charging_station_x
    station_y = env.charging_station_y

    # チャンネル3に充電ステーションが記録されているはず
    assert obs[station_x][station_y][3] == 1.0
```

### 7.2 統合テスト

#### 7.2.1 学習統合テスト

```python
def test_ppo_training_with_battery():
    """PPOトレーニングがバッテリーシステムと統合されることを確認"""
    from stable_baselines3 import PPO

    env = SecurityEnvironment(width=8, height=8)
    model = PPO("MlpPolicy", env, verbose=0)

    # 短時間学習
    model.learn(total_timesteps=1000)

    # 推論実行
    obs, info = env.reset()
    for _ in range(100):
        action, _states = model.predict(obs)
        obs, reward, done, truncated, info = env.step(action)

        # バッテリー情報が正しく返されることを確認
        assert 'battery_percentage' in info
        assert 'is_charging' in info
        assert 0.0 <= info['battery_percentage'] <= 100.0

        if done:
            break
```

### 7.3 受け入れテスト

#### 7.3.1 シナリオテスト

**シナリオ1: 正常な充電サイクル**
1. ロボットが警備を開始（バッテリー100%）
2. 5000ステップ警備（バッテリー95%に低下）
3. 充電ステーションに戻る
4. 100%まで充電
5. 再度警備を開始

**シナリオ2: 部分充電での警備再開**
1. ロボットが警備開始（バッテリー100%）
2. 30000ステップ警備（バッテリー70%に低下）
3. 高脅威エリアが検出される
4. 充電ステーションで50%まで充電（80%に回復）
5. 高脅威エリアに対応

**シナリオ3: バッテリー切れ回避の学習**
1. 初期エピソード: バッテリー切れでペナルティ
2. 学習後: バッテリー残量を考慮した早期帰還
3. 充電ステーションに戻れる範囲での警備

---

## 8. 制約事項

### 8.1 技術的制約

1. **観測空間の拡張**: 既存の3チャンネルから5チャンネルへの変更により、学習済みモデルとの互換性なし
2. **学習時間の増加**: 観測空間の拡大により、学習収束時間が増加する可能性
3. **メモリ使用量**: バッテリー情報の記録により、データベース使用量が増加

### 8.2 設計上の制約

1. **充電ステーション数**: 現バージョンでは1箇所のみ（将来的に複数配置可能に設計）
2. **バッテリー消費率**: 全アクションで一律（将来的にアクション別の消費率設定可能）
3. **充電速度**: 固定値（環境パラメータとして調整可能に設計）

### 8.3 互換性

1. **既存モデル**: バッテリーシステム導入前の学習済みモデルは使用不可
2. **データベース**: マイグレーションが必要
3. **フロントエンド**: バッテリー情報の表示機能は別途開発が必要

---

## 9. 付録

### 9.1 用語集

| 用語 | 説明 |
|------|------|
| バッテリー残量 | ロボットの現在のエネルギー残量（0-100%） |
| 充電ステーション | ロボットが充電を行う固定位置 |
| 充電率 | 1ステップあたりの充電量（既定値: 1%/step） |
| 消費率 | 1ステップあたりのバッテリー消費量（既定値: 0.001%/step） |
| 部分充電 | 100%未満で充電を中断すること |
| バッテリー切れペナルティ | バッテリーが0%になった際の負の報酬（-100.0） |

### 9.2 参照ドキュメント

- `instructions/01_system_architecture_design_standalone.md` - システムアーキテクチャ設計書
- `instructions/02_backend_api_design_standalone.md` - バックエンドAPI設計書
- `instructions/04_test_design_standalone.md` - テスト設計書
- `report/PROGRESS.md` - プロジェクト進捗管理

### 9.3 改訂履歴

| バージョン | 日付 | 変更内容 | 作成者 |
|-----------|------|---------|--------|
| 1.0 | 2025-11-09 | 初版作成 | Claude |

---

**承認:**

本要件定義書の内容を確認し、実装を開始することを承認します。

**次のステップ:**
1. 本要件定義書のレビューと承認
2. Phase 1（環境実装）の開始
3. Phase 2（テスト実装）の実施
4. 設計書の更新とドキュメント整備
