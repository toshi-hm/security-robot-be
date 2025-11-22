# フロントエンド更新手順: 複雑な環境のサポート

このドキュメントでは、バックエンドの `feature/complex-environment` ブランチで導入された新しい複雑な環境機能をサポートするために、`security-robot-fe` コードベースに必要な変更について説明します。

## 目的

本機能拡張により、以下の実験・研究目標を達成します：

### 強化学習の観点
1. **汎化性能の評価**: エージェントが単純な障害物環境だけでなく、構造化された複雑な環境（迷路、部屋、洞窟）でも適切に動作できるかを検証します。
2. **探索戦略の比較**: 異なる地形タイプにおいて、各種アルゴリズム（PPO, DQN等）の探索効率や学習曲線を比較分析できるようにします。
3. **再現可能な実験**: シード値を指定することで、同じマップレイアウトでの実験再現が可能になり、アルゴリズム改善の効果を正確に測定できます。
4. **難易度の段階的制御**: Random（簡単）→ Room（中級）→ Maze/Cave（高難度）と、学習カリキュラムを設計できるようにします。

### セキュリティロボットの実用性
- 実際の警備環境（オフィスビル、工場、倉庫など）を模擬した環境でエージェントを訓練することで、実世界への適用可能性を高めます。
- 不規則な地形や予測困難な構造への対応能力を向上させます。

## コンテキスト
バックエンドでは、単純なランダムな障害物以外のマップレイアウトをサポートする新しい `MapGenerator` システムが導入されました。サポートされているマップタイプは以下の通りです：
- **Random** (Random Obstacles):
    - 従来通りの形式です。NxMの長方形の空間内に、指定された数の障害物（柱）がランダムに配置されます。
    - 比較的開けた空間が多く、単純な障害物回避の学習に適しています。
- **Maze** (Maze Layout):
    - 空間全体が入り組んだ迷路になります。
    - 壁が連続しており、行き止まりや長い迂回路が存在します。高度な経路計画能力が必要とされます。
- **Room** (Room Layout):
    - 複数の「部屋」が「廊下」で接続された、オフィスや屋内施設のようなレイアウトです。
    - 部屋と部屋の間の移動（ドア通過のような動作）や、区切られたエリアごとの探索が求められます。
- **Cave** (Cave Terrain):
    - セル・オートマトンによって生成される、自然の洞窟のような不規則な地形です。
    - 直線的な壁が少なく、有機的な形状の障害物が密集したり開けたりする、予測しにくい環境です。

## 要件

### 1. トレーニング設定 (`/training`)
「トレーニング開始 (Start Training)」フォームを更新し、ユーザーがマップ生成パラメータを設定できるようにします。

#### 新しいフィールド
- **マップタイプ** (`map_type`):
    - コンポーネント: ドロップダウン / セレクト
    - オプション:
        - `random` (ラベル: "Random Obstacles")
        - `maze` (ラベル: "Maze")
        - `room` (ラベル: "Room Layout")
        - `cave` (ラベル: "Cave / Terrain")
    - デフォルト: `random`

- **マップシード** (`seed`):
    - コンポーネント: 数値入力 (任意)
    - 説明: 再現可能なマップ生成のためのシード値。

#### 動的フィールド (マップタイプに基づく)
- **マップタイプが `cave` の場合**:
    - **初期壁確率** (`initial_wall_probability`):
        - コンポーネント: スライダー または 数値入力
        - 範囲: 0.0 ～ 1.0
        - デフォルト: 0.45
        - ステップ: 0.01

- **マップタイプが `random` の場合**:
    - **障害物数** (`count`):
        - コンポーネント: 数値入力 (任意)
        - 説明: 配置する障害物の数。

#### API 統合
トレーニングジョブを送信する際 (`POST /training/start`)、これらの新しいフィールドはペイロードの `config` オブジェクト内にネストする必要があります。

**ペイロード例:**
```json
{
  "name": "My Training Session",
  "algorithm": "ppo",
  "environment_type": "standard",
  "total_timesteps": 100000,
  "env_width": 20,
  "env_height": 20,
  "config": {
    "map_type": "cave",
    "seed": 12345,
    "initial_wall_probability": 0.45
  }
}
```

### 2. インタラクティブ環境 (`/environment`)
「新規セッション (New Session)」ダイアログ/フォームを更新し、上記と同じマップ設定フィールドを含めます。

#### API 統合
新規セッションを作成する際 (`POST /environment/sessions`) のペイロード構造は以下の通りです：

```json
{
  "environment_id": "security-v1",
  "seed": 12345,
  "config": {
    "map_type": "maze",
    "width": 20,
    "height": 20
    // ... その他のマップ設定パラメータ
  }
}
```
*注: `width` と `height` はトップレベルの設定または環境定義の一部である可能性がありますが、`map_type` と特定のジェネレータパラメータは `config` に入ります。*

### 3. Playback画面での対応

トレーニング済みエージェントの動作を再生するPlayback機能において、複雑な地形を正しく表示する必要があります。

#### 要件
1. **エピソードデータの取得**:
   - `GET /training/{job_id}/episodes/{episode_id}` からエピソードデータを取得する際、レスポンスに含まれる各ステップの `state.obstacles` を利用します。
   - `obstacles` は2次元のブール配列で、各ステップごとに提供されます（地形は固定ですが、データ構造上は各ステップに含まれます）。

2. **マップタイプの表示**:
   - Playback画面のヘッダーまたはメタデータセクションに、使用されたマップタイプ（`map_type`）を表示します。
   - 例: 「Map Type: Maze」「Seed: 12345」などの情報をバッジまたはラベルで表示。

3. **地形のレンダリング**:
   - **初回ロード時**: 最初のステップの `obstacles` 配列を使用して地形全体を描画します。
   - **再生中**: エージェントの位置やゴールは動的に更新されますが、障害物レイヤーは静的に保持します（パフォーマンス最適化）。
   - **視覚的区別**:
     - Random: 個別の柱/障害物として表示（例: 灰色の正方形）
     - Maze: 連続した壁として表示（例: 濃い灰色、石壁テクスチャ）
     - Room: 部屋の境界と廊下を視覚的に区別（例: 壁は濃い灰色、床は明るい灰色）
     - Cave: 有機的な形状の壁として表示（例: 茶色や土色、不規則なパターン）

4. **UI/UX の推奨事項**:
   - 再生速度コントロール（0.5x, 1x, 2x）を提供し、複雑な地形での動作を詳細に観察できるようにします。
   - ステップバイステップでのナビゲーション（前のステップ、次のステップボタン）を実装します。
   - グリッドオーバーレイのオン/オフ切り替えを提供し、座標確認を容易にします。

5. **パフォーマンス考慮事項**:
   - 大きなマップ（例: 50x50以上）の場合、Canvas描画を使用してDOMノード数を削減します。
   - 障害物レイヤーは一度だけ描画し、エージェント/ゴールレイヤーのみを更新します。

### 4. 視覚化 (Visualization)
環境視覚化コンポーネント（Grid または Canvas）が `obstacles` レイヤーを正しくレンダリングすることを確認してください。
- バックエンドは `EnvironmentState` 内で `obstacles` を2次元のブール配列として返します。
- `True` は壁/障害物を示します。
- `False` は通行可能なスペースを示します。
- 壁が視覚的に区別できるようにしてください（例：濃い灰色やブロックテクスチャ）。

## 実装ステップ
1.  **型/インターフェースの更新**: フロントエンドの型定義に `MapType` と `MapConfig` インターフェースを追加します。
2.  **フォームの更新**: トレーニングおよび環境作成フォームを変更し、新しいフィールドを含めます。
3.  **動的ロジックの実装**: 選択された `MapType` に基づいてフィールドの表示/非表示を切り替えます。
4.  **API 呼び出しの更新**: リクエストを送信する前に `config` オブジェクトが正しく構築されていることを確認します。
5.  **視覚化の検証**: 新しいマップタイプ（特に Maze と Cave）が正しくレンダリングされることを確認します。
6.  **Playback機能の拡張**: エピソード再生画面にマップタイプ情報の表示と地形レンダリングを実装します。

---

## API 差分仕様書

このセクションでは、`feature/complex-environment` ブランチで導入された API の変更点を詳細に記述します。

### 1. トレーニング開始 API

**エンドポイント**: `POST /training/start`

#### 変更内容
トレーニングジョブ作成時のリクエストボディに `config` オブジェクトが拡張されました。

#### リクエストボディ（変更前）
```json
{
  "name": "string",
  "algorithm": "ppo | dqn",
  "environment_type": "standard",
  "total_timesteps": 100000,
  "env_width": 20,
  "env_height": 20
}
```

#### リクエストボディ（変更後）
```json
{
  "name": "string",
  "algorithm": "ppo | dqn",
  "environment_type": "standard",
  "total_timesteps": 100000,
  "env_width": 20,
  "env_height": 20,
  "config": {
    "map_type": "random | maze | room | cave",
    "seed": 12345,  // optional
    "count": 10,    // required only when map_type == "random"
    "initial_wall_probability": 0.45  // required only when map_type == "cave"
  }
}
```

#### 新規フィールド詳細

| フィールド名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| `config.map_type` | `string` | No | `"random"` | マップ生成タイプ。`random`, `maze`, `room`, `cave` のいずれか |
| `config.seed` | `integer` | No | `null` | マップ生成のシード値。再現可能な実験に使用 |
| `config.count` | `integer` | Conditional | - | `map_type == "random"` の場合のみ必須。障害物の数 |
| `config.initial_wall_probability` | `float` | Conditional | `0.45` | `map_type == "cave"` の場合のみ使用。初期壁生成確率（0.0 ～ 1.0） |

#### レスポンス
変更なし。従来通り `TrainingJob` オブジェクトが返されます。

#### バリデーション
- `map_type` が `"random"` の場合、`count` が未指定だとエラー（400 Bad Request）
- `map_type` が `"cave"` の場合、`initial_wall_probability` は 0.0 ～ 1.0 の範囲内である必要があります
- `env_width` と `env_height` は最低 5 以上である必要があります（複雑な地形生成の制約）

---

### 2. インタラクティブ環境セッション作成 API

**エンドポイント**: `POST /environment/sessions`

#### 変更内容
セッション作成時のリクエストボディに `config` オブジェクトが拡張されました。

#### リクエストボディ（変更前）
```json
{
  "environment_id": "security-v1",
  "seed": 12345,
  "config": {
    "width": 20,
    "height": 20
  }
}
```

#### リクエストボディ（変更後）
```json
{
  "environment_id": "security-v1",
  "seed": 12345,
  "config": {
    "width": 20,
    "height": 20,
    "map_type": "random | maze | room | cave",
    "count": 10,  // map_type == "random" の場合のみ
    "initial_wall_probability": 0.45  // map_type == "cave" の場合のみ
  }
}
```

#### 新規フィールド詳細

| フィールド名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| `config.map_type` | `string` | No | `"random"` | マップ生成タイプ |
| `config.count` | `integer` | Conditional | - | `map_type == "random"` の場合のみ必須 |
| `config.initial_wall_probability` | `float` | Conditional | `0.45` | `map_type == "cave"` の場合のみ使用 |

**注**: `seed` はトップレベルのフィールドとして既に存在しており、マップ生成にも使用されます。

#### レスポンス
変更なし。`EnvironmentSession` オブジェクトが返されます。

---

### 3. 環境状態取得 API

**エンドポイント**: `GET /environment/sessions/{session_id}/state`

#### 変更内容
レスポンス内の `EnvironmentState` オブジェクトに `obstacles` フィールドが含まれるようになりました（既存の仕様ですが、明示的に文書化）。

#### レスポンス
```json
{
  "agent_position": [5, 10],
  "goal_position": [15, 15],
  "obstacles": [
    [false, false, true, false, ...],
    [false, true, true, false, ...],
    ...
  ],
  "width": 20,
  "height": 20,
  "done": false,
  "reward": 0.0
}
```

#### フィールド詳細

| フィールド名 | 型 | 説明 |
|-------------|-----|------|
| `obstacles` | `boolean[][]` | 2次元配列。`obstacles[y][x]` が `true` の場合、座標 (x, y) は障害物/壁 |
| `width` | `integer` | マップの幅 |
| `height` | `integer` | マップの高さ |

---

### 4. トレーニングジョブ詳細取得 API

**エンドポイント**: `GET /training/{job_id}`

#### 変更内容
レスポンスの `TrainingJob` オブジェクトに `config` が含まれるようになりました。

#### レスポンス
```json
{
  "id": "uuid-string",
  "name": "My Training Session",
  "algorithm": "ppo",
  "status": "running",
  "total_timesteps": 100000,
  "current_timestep": 50000,
  "env_width": 20,
  "env_height": 20,
  "config": {
    "map_type": "maze",
    "seed": 12345,
    "count": null,
    "initial_wall_probability": null
  },
  "created_at": "2025-11-22T10:00:00Z",
  "updated_at": "2025-11-22T11:30:00Z"
}
```

#### 新規フィールド詳細

| フィールド名 | 型 | 説明 |
|-------------|-----|------|
| `config` | `object` | トレーニング時に使用されたマップ設定 |
| `config.map_type` | `string` | 使用されたマップタイプ |
| `config.seed` | `integer \| null` | 使用されたシード値（未指定の場合は `null`） |
| `config.count` | `integer \| null` | Random マップの障害物数（該当しない場合は `null`） |
| `config.initial_wall_probability` | `float \| null` | Cave マップの初期壁確率（該当しない場合は `null`） |

---

### 5. エピソードデータ取得 API

**エンドポイント**: `GET /training/{job_id}/episodes/{episode_id}`

#### 変更内容
各ステップの `state` オブジェクトに `obstacles` が含まれます（既存の仕様ですが、複雑な地形では重要性が増すため明示化）。

#### レスポンス
```json
{
  "episode_id": "episode-uuid",
  "job_id": "job-uuid",
  "steps": [
    {
      "step": 0,
      "state": {
        "agent_position": [5, 5],
        "goal_position": [15, 15],
        "obstacles": [
          [false, true, true, ...],
          [false, false, true, ...],
          ...
        ],
        "width": 20,
        "height": 20
      },
      "action": 0,
      "reward": -0.01,
      "done": false
    },
    ...
  ],
  "total_reward": 10.5,
  "episode_length": 120,
  "metadata": {
    "map_type": "maze",
    "seed": 12345
  }
}
```

#### 新規フィールド詳細

| フィールド名 | 型 | 説明 |
|-------------|-----|------|
| `metadata.map_type` | `string` | このエピソードで使用されたマップタイプ |
| `metadata.seed` | `integer \| null` | このエピソードで使用されたシード値 |

**注**: 各ステップの `obstacles` は同一ですが、データ構造の一貫性のため各ステップに含まれます。フロントエンド側で最適化してキャッシュすることを推奨します。

---

### 6. TypeScript型定義の推奨例

```typescript
// マップタイプの列挙
export type MapType = 'random' | 'maze' | 'room' | 'cave';

// マップ設定インターフェース
export interface MapConfig {
  map_type?: MapType;
  seed?: number;
  count?: number;  // random用
  initial_wall_probability?: number;  // cave用
}

// トレーニング開始リクエスト
export interface TrainingStartRequest {
  name: string;
  algorithm: 'ppo' | 'dqn';
  environment_type: string;
  total_timesteps: number;
  env_width: number;
  env_height: number;
  config?: MapConfig;
}

// 環境状態
export interface EnvironmentState {
  agent_position: [number, number];
  goal_position: [number, number];
  obstacles: boolean[][];
  width: number;
  height: number;
  done: boolean;
  reward: number;
}

// トレーニングジョブ
export interface TrainingJob {
  id: string;
  name: string;
  algorithm: string;
  status: string;
  total_timesteps: number;
  current_timestep: number;
  env_width: number;
  env_height: number;
  config?: MapConfig;
  created_at: string;
  updated_at: string;
}

// エピソードメタデータ
export interface EpisodeMetadata {
  map_type: MapType;
  seed?: number;
}

// エピソードステップ
export interface EpisodeStep {
  step: number;
  state: EnvironmentState;
  action: number;
  reward: number;
  done: boolean;
}

// エピソードデータ
export interface Episode {
  episode_id: string;
  job_id: string;
  steps: EpisodeStep[];
  total_reward: number;
  episode_length: number;
  metadata: EpisodeMetadata;
}
```

---

## 備考

- バックエンドのマップ生成ロジャーは `app/services/map_generator.py` に実装されています。
- 各マップタイプのアルゴリズム詳細については、バックエンドのドキュメント（`../security-robot-be/  instructions/` 配下）を参照してください。
- フロントエンド実装時の質問や不明点はUserに尋ねてください
