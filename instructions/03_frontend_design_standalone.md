# フロントエンド詳細設計書 - セキュリティロボット強化学習システム

## 1. フロントエンド概要

### 1.1 プロジェクト目的

現在のFlask/Dash統合モノリスアプリケーション(2,600行)を、Vue.js 3 + Nuxt v4ベースのモダンなSPAに移行し、ユーザビリティ・保守性・開発効率を向上させます。

**重要**: ローカル環境での単独使用を想定し、ユーザー認証・ログイン機能は実装しません。研究者個人が使用するシンプルな構成を目指します。

### 1.2 技術スタック

**パッケージマネージャー**
- **pnpm 9.12.0**: 高速で効率的なディスク使用、厳格な依存関係管理

**バージョン管理方針**
- package.jsonでは`^`プレフィックスを使用してマイナー/パッチバージョンアップデートを許可
- 例: `^3.0.1`は`3.0.x`の最新バージョンに自動更新
- セキュリティパッチやバグフィックスを継続的に取り込む

#### コアフレームワーク
- **Vue.js ^3.5**: Composition API、Script Setup、Reactivityシステム
- **Nuxt ^4.1**: ファイルベースルーティング、SSR/SPA切替、Auto-import
- **TypeScript ^5.7**: 厳格な型チェック、型推論、インターフェース定義

#### UIフレームワーク
- **Element Plus ^1.0 (Nuxt統合)**: エンタープライズグレードのVue 3コンポーネントライブラリ
- **Nuxt UI ^4.0**: Nuxt専用UIコンポーネント
- **SCSS ^1.83**: ネスト、変数、ミックスインによる効率的なスタイリング
- **BEM記法**: block__element--modifier によるCSS命名規則

#### 状態管理・通信
- **Pinia ^3.0**: Vue 3公式状態管理、Composition API統合、TypeScript完全サポート
- **@pinia/nuxt ^0.10**: Pinia Nuxt統合
- **axios ^1.7**: HTTPクライアント
- **Socket.IO Client ^4.8**: WebSocketリアルタイム通信

#### 可視化
- **Chart.js ^4.5**: 軽量で高速なチャートライブラリ
- **vue-chartjs ^5.3**: Chart.jsのVue 3ラッパー
- **D3.js ^7.9**: 柔軟なデータ可視化(環境ヒートマップ等)

#### ビルド・開発ツール
- **Vite ^6.x**: 高速なHMR、最適化されたプロダクションビルド (Nuxtに統合)
- **Vitest ^3.0**: Vue 3対応の高速ユニットテストフレームワーク
- **Playwright ^1.49**: クロスブラウザE2Eテスト
- **ESLint ^9.37**: コード品質チェック
- **Stylelint ^16.25**: スタイルシート品質チェック
- **vue-tsc ^2.1**: Vue TypeScript型チェック

### 1.3 アーキテクチャパターン: DDD (Domain-Driven Design)

フロントエンドにDDDの原則を適用し、以下のレイヤー構造を採用します:

```
┌─────────────────────────────────────┐
│  Presentation Layer                 │
│  (Components/Pages)                 │
│  - UIコンポーネント                   │
│  - ユーザーインタラクション             │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  Application Layer                  │
│  (Composables)                      │
│  - ビジネスロジック調整                │
│  - Repository使用                   │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  Domain Layer                       │
│  (libs/domains)                     │
│  - ドメインモデル                      │
│  - ビジネスルール                      │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  Infrastructure Layer               │
│  (libs/repositories)                │
│  - データアクセス抽象化                 │
│  - API通信実装                        │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  External API                       │
│  (FastAPI Backend)                  │
└─────────────────────────────────────┘
```

#### DDDを採用する理由

1. **ビジネスロジックの明確化**: ドメインモデルに集約
2. **テスタビリティ**: Repositoryインターフェースによるモック化容易
3. **拡張性**: 新機能追加時のレイヤー明確化
4. **保守性**: 各レイヤーの責務が明確で変更影響を局所化
5. **チーム開発**: 役割分担が明確(ドメイン専門家、UI開発者など)

## 2. ディレクトリ構造と設計原則

### 2.1 完全なディレクトリ構造

```
security-robot-rl-frontend/
├── nuxt.config.ts                 # Nuxt v4設定
├── package.json
├── tsconfig.json
├──
├── configs/                       # 設定層
│   ├── api.ts                    # APIエンドポイント定義
│   ├── constants.ts              # 定数定義
│   └── environment.ts            # 環境変数設定
│
├── libs/                         # DDDコアレイヤー
│   ├── domains/                  # ドメイン層
│   │   ├── training/
│   │   │   ├── TrainingSession.ts
│   │   │   ├── TrainingMetrics.ts
│   │   │   └── TrainingConfig.ts
│   │   ├── environment/
│   │   │   ├── Environment.ts
│   │   │   ├── RobotState.ts
│   │   │   └── ThreatLevel.ts
│   │   ├── playback/
│   │   │   ├── PlaybackSession.ts
│   │   │   └── PlaybackFrame.ts
│   │   └── model/
│   │       ├── Model.ts
│   │       └── ModelMetadata.ts
│   ├── entities/                 # エンティティ層
│   │   ├── training/
│   │   │   ├── TrainingSessionEntity.ts
│   │   │   └── TrainingMetricsEntity.ts
│   │   ├── environment/
│   │   │   └── EnvironmentStateEntity.ts
│   │   └── model/
│   │       └── ModelEntity.ts
│   └── repositories/             # リポジトリ層
│       ├── training/
│       │   ├── TrainingRepository.ts
│       │   └── TrainingRepositoryImpl.ts
│       ├── environment/
│       │   ├── EnvironmentRepository.ts
│       │   └── EnvironmentRepositoryImpl.ts
│       ├── playback/
│       │   ├── PlaybackRepository.ts
│       │   └── PlaybackRepositoryImpl.ts
│       └── model/
│           ├── ModelRepository.ts
│           └── ModelRepositoryImpl.ts
│
├── components/                    # プレゼンテーション層
│   ├── common/
│   │   ├── AppHeader.vue
│   │   ├── AppSidebar.vue
│   │   ├── LoadingSpinner.vue
│   │   └── ErrorAlert.vue
│   ├── training/
│   │   ├── TrainingControl.vue
│   │   ├── TrainingProgress.vue
│   │   ├── TrainingMetrics.vue
│   │   └── ConfigurationPanel.vue
│   ├── environment/
│   │   ├── EnvironmentVisualization.vue
│   │   ├── RobotPositionDisplay.vue
│   │   ├── ThreatLevelMap.vue
│   │   └── CoverageMap.vue
│   ├── visualization/
│   │   ├── RewardChart.vue
│   │   ├── LossChart.vue
│   │   ├── CoverageChart.vue
│   │   └── ExplorationChart.vue
│   └── playback/
│       ├── PlaybackControl.vue
│       ├── PlaybackTimeline.vue
│       └── PlaybackSpeed.vue
│
├── composables/                  # アプリケーション層
│   ├── useWebSocket.ts          # WebSocket管理
│   ├── useTraining.ts           # 学習管理（Repository使用）
│   ├── useEnvironment.ts        # 環境管理（Repository使用）
│   ├── usePlayback.ts           # プレイバック管理（Repository使用）
│   └── useChart.ts              # チャート管理
│
├── layouts/                     # レイアウト
│   ├── default.vue             # デフォルトレイアウト
│   └── fullscreen.vue          # フルスクリーンレイアウト
│
├── pages/                      # ページコンポーネント
│   ├── index.vue              # ダッシュボード（認証なし直接アクセス）
│   ├── training/
│   │   ├── index.vue         # 学習メイン画面
│   │   └── [sessionId]/
│   │       ├── index.vue     # セッション詳細
│   │       └── metrics.vue   # メトリクス詳細
│   ├── playback/
│   │   ├── index.vue         # プレイバック一覧
│   │   └── [sessionId].vue   # プレイバック再生
│   ├── models/
│   │   ├── index.vue         # モデル管理
│   │   └── [modelId].vue     # モデル詳細
│   └── settings/
│       ├── index.vue         # 設定
│       ├── environment.vue   # 環境設定
│       └── training.vue      # 学習設定
│
├── stores/                    # グローバル状態管理
│   ├── training.ts           # 学習状態（Composables使用）
│   ├── environment.ts        # 環境状態
│   ├── playback.ts          # プレイバック状態
│   ├── models.ts            # モデル状態
│   ├── websocket.ts         # WebSocket状態
│   └── ui.ts                # UI状態
│
├── types/                    # 型定義（レガシー互換）
│   ├── api.ts
│   ├── training.ts
│   ├── environment.ts
│   └── websocket.ts
│
├── utils/                   # ユーティリティ
│   ├── constants.ts         # 定数定義
│   ├── formatters.ts        # データフォーマット
│   └── validators.ts        # バリデーション
│
└── plugins/                # プラグイン
    ├── element-plus.client.ts
    ├── chart.client.ts
    └── socket.client.ts
```

### 2.2 各レイヤーの責務

#### configs/ - 設定層
- **役割**: APIエンドポイントURLと定数を一元管理
- **ルール**: すべてのAPI URLはここで定義、他のファイルで直接URLを書かない

#### libs/domains/ - ドメイン層
- **役割**: ビジネスロジックとドメインモデルを定義
- **ルール**: 外部依存(API、Store等)を持たない純粋なビジネスロジック

#### libs/entities/ - エンティティ層
- **役割**: API DTOとドメインモデルの変換
- **ルール**: `toDomain()`, `fromDomain()` メソッドで相互変換

#### libs/repositories/ - リポジトリ層
- **役割**: データアクセスとAPI通信の抽象化
- **ルール**: インターフェースと実装を分離、テスト時にモック可能

#### composables/ - アプリケーション層
- **役割**: リポジトリを使用したビジネスロジックの調整
- **ルール**: Repositoryのみを使用、直接$fetchは禁止

#### components/ - プレゼンテーション層
- **役割**: UIコンポーネント（表示のみ）
- **ルール**: ロジックはcomposables/storesに委譲、コンポーネントは薄く

### 2.3 Nuxt設定 (nuxt.config.ts)

```typescript
// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  // Nuxt 4互換モード
  future: {
    compatibilityVersion: 4,
  },

  devtools: { enabled: true },
  ssr: false, // SPA mode

  css: ['~/assets/css/main.css'],

  modules: [
    '@nuxt/ui',
    '@element-plus/nuxt',
    '@pinia/nuxt',
    '@vueuse/nuxt',
    '@vee-validate/nuxt',
    '@nuxt/eslint'
  ],

  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.API_BASE_URL || 'http://localhost:8000',
      wsUrl: process.env.WS_URL || 'ws://localhost:8000',
    }
  },

  typescript: {
    strict: true,
    typeCheck: true,
    shim: false
  },

  vite: {
    define: {
      global: 'globalThis',
    }
  },

  elementPlus: {
    icon: 'ElIcon',
    importStyle: 'scss',
    themes: ['dark']
  },

  compatibilityDate: '2025-01-01'
})
```

## 3. ドメイン層設計 (libs/domains/)

### 3.1 TrainingSession ドメインモデル

```typescript
// libs/domains/training/TrainingSession.ts

/**
 * 学習セッションドメインモデル
 *
 * ビジネスルール:
 * - statusが'running'の場合のみ進捗更新可能
 * - totalTimestepsに達したら自動的に'completed'に遷移
 * - 進捗率は常に0-100の範囲
 */
export class TrainingSession {
  constructor(
    public readonly id: number,
    public readonly name: string,
    public readonly algorithm: 'ppo' | 'a3c',
    public readonly environmentType: 'standard' | 'enhanced',
    public readonly status: 'created' | 'running' | 'paused' | 'completed' | 'failed',
    public readonly totalTimesteps: number,
    public readonly currentTimestep: number,
    public readonly episodesCompleted: number,
    public readonly envWidth: number,
    public readonly envHeight: number,
    public readonly coverageWeight: number,
    public readonly explorationWeight: number,
    public readonly diversityWeight: number,
    public readonly modelPath?: string,
    public readonly config?: Record<string, any>,
    public readonly createdAt?: Date,
    public readonly startedAt?: Date,
    public readonly completedAt?: Date
  ) {
    this.validateTimesteps()
    this.validateEnvironmentSize()
    this.validateWeights()
  }

  /**
   * 学習が進行中かどうか
   */
  get isRunning(): boolean {
    return this.status === 'running'
  }

  /**
   * 学習が完了したかどうか
   */
  get isCompleted(): boolean {
    return this.status === 'completed'
  }

  /**
   * 進捗率を取得 (0-100)
   */
  get progress(): number {
    if (this.totalTimesteps === 0) return 0
    return Math.round((this.currentTimestep / this.totalTimesteps) * 100)
  }

  /**
   * 学習時間を取得 (ミリ秒)
   */
  get duration(): number | null {
    if (!this.startedAt) return null
    const endTime = this.completedAt || new Date()
    return endTime.getTime() - this.startedAt.getTime()
  }

  /**
   * アルゴリズム表示名
   */
  get algorithmDisplayName(): string {
    return this.algorithm.toUpperCase()
  }

  /**
   * 環境タイプ表示名
   */
  get environmentTypeDisplayName(): string {
    return this.environmentType === 'enhanced' ? '拡張環境' : '標準環境'
  }

  private validateTimesteps(): void {
    if (this.totalTimesteps < 1000) {
      throw new Error('Total timesteps must be at least 1000')
    }
    if (this.currentTimestep < 0 || this.currentTimestep > this.totalTimesteps) {
      throw new Error('Current timestep out of range')
    }
  }

  private validateEnvironmentSize(): void {
    if (this.envWidth < 5 || this.envWidth > 50) {
      throw new Error('Environment width must be between 5 and 50')
    }
    if (this.envHeight < 5 || this.envHeight > 50) {
      throw new Error('Environment height must be between 5 and 50')
    }
  }

  private validateWeights(): void {
    if (this.coverageWeight < 0 || this.coverageWeight > 10) {
      throw new Error('Coverage weight must be between 0 and 10')
    }
    if (this.explorationWeight < 0 || this.explorationWeight > 10) {
      throw new Error('Exploration weight must be between 0 and 10')
    }
    if (this.diversityWeight < 0 || this.diversityWeight > 10) {
      throw new Error('Diversity weight must be between 0 and 10')
    }
  }
}
```

### 3.2 Environment ドメインモデル

```typescript
// libs/domains/environment/Environment.ts

/**
 * 環境状態ドメインモデル
 *
 * 表現するもの:
 * - ロボットの現在位置と向き
 * - グリッド上の脅威レベル分布
 * - カバレッジマップ(どこを巡回済みか)
 * - 不審物の位置と脅威度
 */
export class Environment {
  constructor(
    public readonly width: number,
    public readonly height: number,
    public readonly robotX: number,
    public readonly robotY: number,
    public readonly robotOrientation: number, // 0=北, 1=東, 2=南, 3=西
    public readonly threatGrid: number[][], // [y][x] = 0.0-1.0
    public readonly coverageMap: boolean[][], // [y][x] = visited
    public readonly suspiciousObjects: SuspiciousObject[]
  ) {
    this.validateRobotPosition()
    this.validateGridDimensions()
  }

  /**
   * ロボットの向き(テキスト)
   */
  get orientationText(): string {
    const directions = ['北', '東', '南', '西']
    return directions[this.robotOrientation] || '不明'
  }

  /**
   * 平均脅威レベル
   */
  get averageThreatLevel(): number {
    const total = this.threatGrid.flat().reduce((sum, val) => sum + val, 0)
    return total / (this.width * this.height)
  }

  /**
   * カバレッジ率 (0.0-1.0)
   */
  get coverageRatio(): number {
    const covered = this.coverageMap.flat().filter(v => v).length
    return covered / (this.width * this.height)
  }

  /**
   * 不審物数
   */
  get suspiciousObjectCount(): number {
    return this.suspiciousObjects.length
  }

  /**
   * 指定座標の脅威レベルを取得
   */
  getThreatLevelAt(x: number, y: number): number {
    if (x < 0 || x >= this.width || y < 0 || y >= this.height) {
      return 0
    }
    return this.threatGrid[y][x]
  }

  /**
   * 指定座標がカバー済みか
   */
  isCovered(x: number, y: number): boolean {
    if (x < 0 || x >= this.width || y < 0 || y >= this.height) {
      return false
    }
    return this.coverageMap[y][x]
  }

  private validateRobotPosition(): void {
    if (this.robotX < 0 || this.robotX >= this.width) {
      throw new Error(`Robot X position ${this.robotX} out of bounds`)
    }
    if (this.robotY < 0 || this.robotY >= this.height) {
      throw new Error(`Robot Y position ${this.robotY} out of bounds`)
    }
    if (this.robotOrientation < 0 || this.robotOrientation > 3) {
      throw new Error(`Invalid robot orientation ${this.robotOrientation}`)
    }
  }

  private validateGridDimensions(): void {
    if (this.threatGrid.length !== this.height) {
      throw new Error('Threat grid height mismatch')
    }
    if (this.threatGrid[0]?.length !== this.width) {
      throw new Error('Threat grid width mismatch')
    }
    if (this.coverageMap.length !== this.height) {
      throw new Error('Coverage map height mismatch')
    }
    if (this.coverageMap[0]?.length !== this.width) {
      throw new Error('Coverage map width mismatch')
    }
  }
}

/**
 * 不審物
 */
export interface SuspiciousObject {
  id: number
  x: number
  y: number
  threatLevel: number
  detectedAt?: Date
}
```

## 4. リポジトリ層設計 (libs/repositories/)

### 4.1 configs/api.ts - エンドポイント定義

```typescript
/**
 * APIエンドポイント定義
 * すべてのAPIエンドポイントURLをここで一元管理
 */

const API_BASE_URL = process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export const API_ENDPOINTS = {
  // Training API
  training: {
    sessions: `${API_BASE_URL}/api/v1/training/sessions`,
    start: `${API_BASE_URL}/api/v1/training/start`,
    stop: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/stop`,
    status: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/status`,
    metrics: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/metrics`,
    configure: (id: number) => `${API_BASE_URL}/api/v1/training/${id}/configure`,
  },

  // Environment API
  environment: {
    state: `${API_BASE_URL}/api/v1/environment/state`,
    config: `${API_BASE_URL}/api/v1/environment/config`,
    reset: `${API_BASE_URL}/api/v1/environment/reset`,
    action: `${API_BASE_URL}/api/v1/environment/action`,
  },

  // Playback API
  playback: {
    sessions: `${API_BASE_URL}/api/v1/playback/sessions`,
    data: (id: number) => `${API_BASE_URL}/api/v1/playback/${id}/data`,
  },

  // Model API
  models: {
    list: `${API_BASE_URL}/api/v1/models`,
    upload: `${API_BASE_URL}/api/v1/models/upload`,
    download: (filename: string) => `${API_BASE_URL}/api/v1/models/${filename}`,
  }
} as const

export const WS_URL = process.env.NUXT_PUBLIC_WS_URL || 'ws://localhost:8000'
```

### 4.2 TrainingRepository インターフェースと実装

```typescript
// libs/repositories/training/TrainingRepository.ts

import type { TrainingSession } from '~/libs/domains/training/TrainingSession'
import type { TrainingMetrics } from '~/libs/domains/training/TrainingMetrics'

/**
 * 学習リポジトリインターフェース
 *
 * データアクセスを抽象化し、テスト時にモック可能にする
 */
export interface TrainingRepository {
  /**
   * 全ての学習セッションを取得
   */
  findAll(): Promise<TrainingSession[]>

  /**
   * IDで学習セッションを取得
   */
  findById(id: number): Promise<TrainingSession | null>

  /**
   * 新しい学習セッションを作成
   */
  create(config: TrainingConfig): Promise<TrainingSession>

  /**
   * 学習セッションを停止
   */
  stop(id: number): Promise<boolean>

  /**
   * 学習セッションのメトリクスを取得
   */
  getMetrics(id: number, limit?: number): Promise<TrainingMetrics[]>
}

export interface TrainingConfig {
  name: string
  algorithm: 'ppo' | 'a3c'
  environmentType: 'standard' | 'enhanced'
  totalTimesteps: number
  envWidth: number
  envHeight: number
  coverageWeight: number
  explorationWeight: number
  diversityWeight: number
}
```

```typescript
// libs/repositories/training/TrainingRepositoryImpl.ts

import type { TrainingRepository, TrainingConfig } from './TrainingRepository'
import type { TrainingSession } from '~/libs/domains/training/TrainingSession'
import type { TrainingMetrics } from '~/libs/domains/training/TrainingMetrics'
import { TrainingSessionEntity, type TrainingSessionDTO } from '~/libs/entities/training/TrainingSessionEntity'
import { API_ENDPOINTS } from '~/configs/api'

/**
 * 学習リポジトリ実装
 *
 * 実際のAPI通信を行う
 */
export class TrainingRepositoryImpl implements TrainingRepository {
  async findAll(): Promise<TrainingSession[]> {
    try {
      const response = await $fetch<TrainingSessionDTO[]>(API_ENDPOINTS.training.sessions)
      return response.map(dto => TrainingSessionEntity.toDomain(dto))
    } catch (error) {
      console.error('Failed to fetch training sessions:', error)
      throw error
    }
  }

  async findById(id: number): Promise<TrainingSession | null> {
    try {
      const response = await $fetch<TrainingSessionDTO>(API_ENDPOINTS.training.status(id))
      return TrainingSessionEntity.toDomain(response)
    } catch (error) {
      console.error(`Failed to fetch training session ${id}:`, error)
      return null
    }
  }

  async create(config: TrainingConfig): Promise<TrainingSession> {
    try {
      const response = await $fetch<TrainingSessionDTO>(API_ENDPOINTS.training.start, {
        method: 'POST',
        body: config,
      })
      return TrainingSessionEntity.toDomain(response)
    } catch (error) {
      console.error('Failed to create training session:', error)
      throw error
    }
  }

  async stop(id: number): Promise<boolean> {
    try {
      await $fetch(API_ENDPOINTS.training.stop(id), {
        method: 'POST',
      })
      return true
    } catch (error) {
      console.error(`Failed to stop training session ${id}:`, error)
      return false
    }
  }

  async getMetrics(id: number, limit: number = 100): Promise<TrainingMetrics[]> {
    try {
      const response = await $fetch<any[]>(API_ENDPOINTS.training.metrics(id), {
        params: { limit },
      })
      // TrainingMetrics変換処理
      return response.map(dto => new TrainingMetrics(
        dto.id,
        dto.session_id,
        dto.timestep,
        dto.episode,
        dto.reward,
        dto.loss,
        dto.coverage_ratio,
        dto.exploration_score,
        dto.timestamp ? new Date(dto.timestamp) : undefined
      ))
    } catch (error) {
      console.error(`Failed to fetch metrics for session ${id}:`, error)
      throw error
    }
  }
}
```

## 5. アプリケーション層設計 (composables/)

### 5.1 useTraining Composable

```typescript
// composables/useTraining.ts

import { ref, computed } from 'vue'
import type { TrainingSession } from '~/libs/domains/training/TrainingSession'
import type { TrainingMetrics } from '~/libs/domains/training/TrainingMetrics'
import { TrainingRepositoryImpl } from '~/libs/repositories/training/TrainingRepositoryImpl'
import type { TrainingConfig } from '~/libs/repositories/training/TrainingRepository'

/**
 * 学習管理Composable
 *
 * リポジトリを使用してビジネスロジックを実装
 * 直接$fetchは使用せず、必ずRepository経由
 */
export const useTraining = () => {
  const repository = new TrainingRepositoryImpl()

  const sessions = ref<TrainingSession[]>([])
  const currentSession = ref<TrainingSession | null>(null)
  const metrics = ref<TrainingMetrics[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const activeSessions = computed(() =>
    sessions.value.filter(s => s.isRunning)
  )

  const completedSessions = computed(() =>
    sessions.value.filter(s => s.isCompleted)
  )

  // Methods
  const fetchSessions = async () => {
    isLoading.value = true
    error.value = null

    try {
      sessions.value = await repository.findAll()
    } catch (err) {
      error.value = 'Failed to fetch training sessions'
      console.error(err)
    } finally {
      isLoading.value = false
    }
  }

  const createSession = async (config: TrainingConfig): Promise<TrainingSession | null> => {
    isLoading.value = true
    error.value = null

    try {
      const newSession = await repository.create(config)
      sessions.value.push(newSession)
      currentSession.value = newSession
      return newSession
    } catch (err) {
      error.value = 'Failed to create training session'
      console.error(err)
      return null
    } finally {
      isLoading.value = false
    }
  }

  const stopSession = async (id: number): Promise<boolean> => {
    try {
      const success = await repository.stop(id)
      if (success) {
        await fetchSessions() // Refresh sessions
      }
      return success
    } catch (err) {
      error.value = 'Failed to stop training session'
      console.error(err)
      return false
    }
  }

  const fetchMetrics = async (sessionId: number) => {
    try {
      metrics.value = await repository.getMetrics(sessionId)
    } catch (err) {
      error.value = 'Failed to fetch metrics'
      console.error(err)
    }
  }

  return {
    // State
    sessions,
    currentSession,
    metrics,
    isLoading,
    error,

    // Computed
    activeSessions,
    completedSessions,

    // Methods
    fetchSessions,
    createSession,
    stopSession,
    fetchMetrics,
  }
}
```

### 5.2 useWebSocket Composable

```typescript
// composables/useWebSocket.ts

import { io, Socket } from 'socket.io-client'
import type { WebSocketMessage, TrainingProgressMessage, EnvironmentUpdateMessage } from '~/types/websocket'

/**
 * WebSocket管理Composable
 *
 * Socket.IOを使用してリアルタイム通信を管理
 */
export const useWebSocket = () => {
  const socket = ref<Socket | null>(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5

  const config = useRuntimeConfig()
  const trainingStore = useTrainingStore()
  const environmentStore = useEnvironmentStore()

  const connect = () => {
    if (socket.value?.connected) return

    socket.value = io(config.public.wsUrl, {
      transports: ['websocket'],
      timeout: 5000,
      reconnection: true,
      reconnectionAttempts: maxReconnectAttempts,
      reconnectionDelay: 1000
    })

    // Connection events
    socket.value.on('connect', () => {
      isConnected.value = true
      reconnectAttempts.value = 0
      console.log('WebSocket connected')
    })

    socket.value.on('disconnect', () => {
      isConnected.value = false
      console.log('WebSocket disconnected')
    })

    socket.value.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed')
    })

    // 学習進捗メッセージ
    socket.value.on('training_progress', (message: TrainingProgressMessage) => {
      trainingStore.updateSessionProgress(message.session_id!, {
        currentTimestep: message.data.timestep,
        episodesCompleted: message.data.episode
      })

      trainingStore.addMetric({
        id: Date.now(),
        sessionId: message.session_id!,
        timestep: message.data.timestep,
        episode: message.data.episode,
        reward: message.data.reward,
        loss: message.data.loss,
        coverageRatio: message.data.coverage_ratio,
        explorationScore: message.data.exploration_score,
        timestamp: new Date(message.timestamp)
      })
    })

    // 環境更新メッセージ
    socket.value.on('environment_update', (message: EnvironmentUpdateMessage) => {
      environmentStore.updateState(message.data)
    })
  }

  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
      isConnected.value = false
    }
  }

  const subscribeToSession = (sessionId: number) => {
    if (socket.value?.connected) {
      socket.value.emit('subscribe_session', { session_id: sessionId })
    }
  }

  const unsubscribeFromSession = (sessionId: number) => {
    if (socket.value?.connected) {
      socket.value.emit('unsubscribe_session', { session_id: sessionId })
    }
  }

  // Auto connect/disconnect
  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket: readonly(socket),
    isConnected: readonly(isConnected),
    connect,
    disconnect,
    subscribeToSession,
    unsubscribeFromSession
  }
}
```

## 6. プレゼンテーション層設計 (components/)

### 6.1 コーディング規約

#### Vueファイル構造（必須）
すべてのVueコンポーネントは以下の順序で記述:

1. **Script**: `<script setup lang="ts">`
2. **Template**: `<template>`
3. **Style**: `<style lang="scss" scoped>`

#### BEM記法（必須）
クラス名: `block__element--modifier` の形式

例: `training-control__button--primary`

### 6.2 TrainingControl コンポーネント実装

```vue
<!-- components/training/TrainingControl.vue -->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { TrainingConfig } from '~/types/training'
import type { FormInstance } from 'element-plus'

// Composables
const { createSession, stopSession, currentSession, isLoading } = useTraining()
const { subscribeToSession, unsubscribeFromSession } = useWebSocket()

// Form data
const formRef = ref<FormInstance>()
const trainingConfig = ref<TrainingConfig>({
  name: '',
  algorithm: 'ppo',
  environmentType: 'standard',
  totalTimesteps: 10000,
  envWidth: 8,
  envHeight: 8,
  coverageWeight: 1.5,
  explorationWeight: 3.0,
  diversityWeight: 2.0
})

// Computed
const statusText = computed(() => {
  switch (currentSession.value?.status) {
    case 'running': return '実行中'
    case 'paused': return '一時停止'
    case 'completed': return '完了'
    case 'failed': return '失敗'
    default: return '未開始'
  }
})

// Methods
const startTraining = async () => {
  if (!formRef.value) return

  const isValid = await formRef.value.validate()
  if (!isValid) return

  const session = await createSession(trainingConfig.value)
  if (session) {
    ElMessage.success('学習を開始しました')
    subscribeToSession(session.id)
  }
}

const stopTraining = async () => {
  if (!currentSession.value) return

  const success = await stopSession(currentSession.value.id)
  if (success) {
    ElMessage.success('学習を停止しました')
    unsubscribeFromSession(currentSession.value.id)
  }
}
</script>

<template>
  <el-card class="training-control">
    <template #header>
      <div class="training-control__header">
        <span>学習制御</span>
        <el-tag :type="statusTagType">{{ statusText }}</el-tag>
      </div>
    </template>

    <!-- 新規学習開始フォーム -->
    <div v-if="!currentSession" class="training-control__start-section">
      <el-form
        ref="formRef"
        :model="trainingConfig"
        label-width="120px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="セッション名" prop="name">
              <el-input v-model="trainingConfig.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="アルゴリズム">
              <el-select v-model="trainingConfig.algorithm">
                <el-option label="PPO" value="ppo" />
                <el-option label="A3C" value="a3c" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button
            type="primary"
            :loading="isLoading"
            @click="startTraining"
          >
            学習開始
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 実行中セッション制御 -->
    <div v-else class="training-control__session-control">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="セッション名">
          {{ currentSession.name }}
        </el-descriptions-item>
        <el-descriptions-item label="進捗">
          {{ currentSession.progress }}%
        </el-descriptions-item>
      </el-descriptions>

      <div class="training-control__control-buttons">
        <el-button
          type="danger"
          @click="stopTraining"
          :loading="isLoading"
        >
          停止
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<style lang="scss" scoped>
.training-control {
  margin-bottom: 20px;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  &__start-section {
    padding: 20px 0;
  }

  &__session-control {
    padding: 20px 0;
  }

  &__control-buttons {
    margin-top: 20px;
    display: flex;
    gap: 10px;
  }
}
</style>
```

このドキュメントは、リポジトリを知らない開発者がフロントエンドを実装できる詳細レベルで記載しています。
