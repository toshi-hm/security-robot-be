# セキュリティロボット強化学習システム - 実装進捗管理

**最終更新:** 2025-10-15 Session 40
## 📑 目次

- [全体進捗](#-全体進捗)
- [完了済み項目](#-完了済み項目)
  - [Phase 1: 依存関係管理・設計書更新](#phase-1-依存関係管理設計書更新-2025-10-06完了)
- [進行中の項目](#-進行中の項目)
  - [Phase 2: データベースモデル実装・拡張](#phase-2-データベースモデル実装拡張-2025-10-06完了)
  - [Phase 3: Pydanticスキーマ実装・拡張](#phase-3-pydanticスキーマ実装拡張-2025-10-06完了)
  - [Phase 4: APIエンドポイント実装・拡張](#phase-4-apiエンドポイント実装拡張)
  - [Phase 5: WebSocket・リアルタイム通信](#phase-5-websocketリアルタイム通信)
  - [Phase 6: Celeryバックグラウンドタスク](#phase-6-celeryバックグラウンドタスク-2025-10-06完了)
  - [Phase 7: RL統合](#phase-7-rl統合-2025-10-06完了)
- [未着手の項目](#-未着手の項目)
- [Phase 8: テスト実装](#phase-8-テスト実装-80)
  - [Phase 9: Docker環境構築](#phase-9-docker環境構築-40---検証必要)
- [既知の問題・課題](#️-既知の問題課題)
- [次のアクションアイテム](#-次のアクションアイテム-優先度順)
- [参考資料](#-参考資料)

---

## 📊 全体進捗

| フェーズ | ステータス | 進捗率 | 備考 |
|---------|----------|-------|------|
| Phase 1: 環境準備・確認 | ✅ 完了 | 100% | uv環境、依存関係更新完了 |
| Phase 2: データベースモデル | ✅ 完了 | 100% | 設計書に基づき全モデル拡張完了 |
| Phase 3: Pydanticスキーマ | ✅ 完了 | 100% | 全スキーマ拡張・バリデーション追加完了 |
| Phase 4: APIエンドポイント | 🔄 進行中 | 95% | トレーニング制御・ファイル管理APIに加え環境セッション操作を実装 (2025-10-12: 環境セッションサービスの型ヒントをPython 3.12に合わせて更新 / 2025-10-13: セッション単位ロックで高負荷時のスループット低下を防止 / 2025-10-13: Celery託送をAPI層から呼び出す経路を整備 / 2025-10-13: 学習停止・一時停止レスポンスでCelery/キュータスクIDを返却し、ジョブ監視APIからキュー状態を取得可能に更新 / 2025-10-13: トレーニングAPIでアルゴリズム種別をEnum化し、不正値は400で拒否) |
| Phase 5: WebSocket | ✅ 完了 | 100% | Redis連携と再接続制御まで完了 |
| Phase 6: Celeryタスク | ✅ 完了 | 100% | PPO学習タスク完全実装。ログ/モデル成果物アーカイブタスクを追加し、ファイル配布の自動化基盤を整備 |
| Phase 7: RL統合 | ✅ 完了 | 85% | PPOService + SB3統合完了、A3Cは未実装 |
| Phase 8: テスト | 🔄 進行中 | 80% | 学習メトリクスAPIとファイル管理APIの単体テストを整備し、ファイルダウンロード統合テストを追加。404レスポンス検証を防御的アサーションと診断メッセージで強化 (依存不足を解消済み) / 2025-10-13: トレーニング制御のCeleryタスクID返却とジョブキューAPIを検証する統合テストを追加 |
| Phase 9: Docker環境 | 🔄 進行中 | 40% | docker-compose.yml存在、要検証 |

**凡例:**
- ✅ 完了
- 🔄 進行中
- ⏳ 未着手
- ⚠️ 問題あり

---

## ✅ 完了済み項目

### Redis/Celery進捗パイプライン安定化 (2025-10-14更新)
- [x] Celeryトレーニングタスクの失敗時にセッションをロールバックせず同一インスタンスを更新し、`started_at` など既存のメタデータを保持。
- [x] `DatabaseMetricsCallback` 用に専用の同期セッションを割り当て、頻繁なコミットとジョブ状態更新を分離してトランザクション衝突を回避。
- [x] Redis通知ヘルパーと `RedisTrainingCallback` にクリティカルイベント用のリトライ処理と詳細ログを追加し、完了・エラー通知の信頼性を向上。
- [x] Redisコールバックでトレーニングジョブの状態をポーリングし、`paused` 指定時に協調停止させる仕組みを導入。停止要求をRedis通知とCeleryメタ情報の双方に反映。
- [x] Celeryワーカー用に独立した同期エンジンを構成し、SQLAlchemyの同期ファサード依存を排除して接続プール競合リスクを低減。
- [x] Redisトレーニングコールバックのステータス判定を `TrainingJobStatus` Enum 比較へ切り替え、型安全性と意図しない大文字小文字変換を排除。
- [x] Celery学習タスクの例外処理でロールバックとセッション終了を整理し、共通ヘルパーで失敗時の状態更新とリソースクリーンアップを一元化。

### ファイル成果物アーカイブ基盤 (2025-10-15更新)
- [x] `app/tasks/file_tasks.py` にログ/モデル成果物をZIP化するタスクを実装し、保存先をストレージ配下の `archives/` ディレクトリへ統一。ファイル/ディレクトリの入力検証とタイムスタンプ付き命名規則を整備。
- [x] `tests/unit/tasks/test_file_tasks.py` でアーカイブ生成とエラーハンドリングを確認し、テスト時にアーカイブ先を差し替えて孤立性を確保。

### ドキュメント日付調整 (2025-10-13更新)
- [x] `report/PROGRESS.md` と `report/DIARY02.md` の日付表記を 2025-10-13 に統一

### リポジトリクリーンアップ (2025-10-12更新)
- [x] ルートに `.gitignore` を追加し、バイナリ・ビルド成果物・IDE設定・ログ/DB などの不要ファイルを除外
- [x] `.gitignore` 運用方針を `report/DIARY.md` / `report/PROGRESS.md` に記録

### CI運用改善 (2025-10-12更新)
- [x] GitHub ActionsのClaude Codeレビュー出力言語を日本語に固定するプロンプトを追加
- [x] Codex PRレビュー用プロンプトを整備し、レビュー出力が日本語になるよう指示を明文化
- [x] Codex/Claude 向けエージェントガイド (`AGENTS.md`, `CLAUDE.md`) を英語化し、参照ドキュメント・TDD 手順を統一

### ローカル環境起動エラー解消 (2025-10-11更新)
- [x] `pyproject.toml` に `tool.setuptools.packages.find` を追加し、`app`/`rl` 配下のみをパッケージ対象に限定
- [x] `aiosqlite` を `project.dependencies` へ追加し、SQLite 非同期接続での `ModuleNotFoundError` を解消
- [x] `uv run uvicorn app.main:app --reload` を実行してサーバー起動を再検証 (手動停止)

### 環境セッション管理の改善 (2025-10-13更新)
- [x] セッションに `last_accessed` とタイムアウト秒数を導入し、期限切れセッションを自動でクリーンアップ
- [x] `execute_action`/`reset_session` をセッション単位ロックで保護し、同一セッションへの並行アクセス時の競合を防止しつつ他セッションのスループットを維持
- [x] セッション終了・クリーンアップ時に環境の `close()` を安全に呼び出す処理を共通化
- [x] `info` 辞書に非文字列キーが含まれる場合の変換ログを追加し、デバッグ容易性を向上
- [x] タイムアウト・並行アクセス・再利用性・情報辞書ログを検証するユニットテストを拡充
- [x] セッション容量超過時のAPIレスポンスを HTTP 503 へ変更し、ステータスコードの意味合いを統一
- [x] セッションタイムアウト既定値を `Settings` から読み込むよう外部化し、運用環境で柔軟に調整可能に
- [x] グローバルロックとセッションロックの取得順序ポリシーをコード内へ明示し、デッドロック懸念への対応を記録
- [x] 開発日記のセッションログを最新順に並べ替え、レビュー指摘に合わせてドキュメント運用を改善 (2025-10-13)

### Phase 1: 依存関係管理・設計書更新 (2025-10-06完了)
**コードベース実装 - 全マシン共通**

- [x] 依存関係の最新バージョン更新
  - FastAPI 0.115.0 → 0.115.6
  - Uvicorn 0.30.0 → 0.34.0
  - SQLAlchemy 2.0.34 → 2.0.36
  - Pydantic 2.8.2 → 2.10.3
  - Celery 5.4.0 → 5.5.0
  - Redis 5.0.8 → 5.2.1
  - Gymnasium 0.29.1 → 1.0.0
  - **新規追加:** Stable-Baselines3 2.4.0, PyTorch 2.5.1
- [x] requirements.txt更新
- [x] 設計書のバージョン情報更新
  - instructions/prompts/00_implementation_guide.md
  - instructions/README.md
  - instructions/02_backend_api_design_standalone.md
  - instructions/01_system_architecture_design_standalone.md

**プロジェクト構造確認 - 全マシン共通**
- [x] app/main.py - FastAPIアプリケーションエントリーポイント
- [x] app/core/ - コアサービス(environment, training, websocket, files)
- [x] app/api/v1/endpoints/ - APIエンドポイント
- [x] rl/environments/ - RL環境実装(security_env.py, enhanced_env.py)
- [x] rl/algorithms/ - RL アルゴリズム(PPO, A3C)

**ローカル環境セットアップ - マシン固有 (参考情報)**
- ✅ [Maya's PC] uv環境セットアップ完了 (2025-10-06)
- ✅ [Maya's PC] 仮想環境作成・依存関係インストール確認 (2025-10-06)
- ⏳ [本番サーバー] 環境セットアップ未実施
- ⏳ [開発サーバー] 環境セットアップ未実施

**注意:** 環境セットアップ手順は `CLAUDE.md` および `.serena` メモリの `suggested_commands.md` を参照

---

## 🔄 進行中の項目

### Phase 2: データベースモデル実装・拡張 (2025-10-06完了)
**進捗:** 100% ✅

#### 完了
- [x] app/models/training.py - TrainingJobモデル完全拡張
  - [x] TrainingJobStatus (created, queued, running, paused, completed, failed)
  - [x] 学習パラメータフィールド (total_timesteps, current_timestep, episodes_completed)
  - [x] 環境設定フィールド (env_width, env_height)
  - [x] 報酬パラメータフィールド (coverage_weight, exploration_weight, diversity_weight)
  - [x] 追加パラメータ (learning_rate, batch_size, num_workers)
  - [x] ファイルパスフィールド (model_path, log_path)
  - [x] 設定JSONB (config)
  - [x] 2025-10-13: `TrainingAlgorithm` Enum列を導入し、DBレイヤでサポート外アルゴリズムを拒否
- [x] app/models/training.py - TrainingMetricモデル完全拡張
  - [x] 環境固有メトリクス (coverage_ratio, exploration_score, threat_level_avg)
  - [x] 追加メトリクスJSON (additional_metrics)
  - [x] タイムスタンプフィールド
- [x] app/models/environment.py - EnvironmentStateモデル実装
  - [x] プレイバック用スナップショット機能
  - [x] ロボット状態 (robot_x, robot_y, robot_orientation)
  - [x] 環境状態JSON (threat_grid, coverage_map, suspicious_objects)
  - [x] アクション情報 (action_taken, reward_received)
- [x] app/models/files.py - FileMetadataモデル完全拡張
  - [x] ファイル情報フィールド (filename, original_filename, file_path, file_size)
  - [x] ファイルタイプ (file_type, content_type)
  - [x] トレーニングジョブ関連付け (training_job_id)
  - [x] メタデータJSON (metadata)
- [x] app/models/__init__.py - 全モデルのエクスポート追加

#### 残課題
- [ ] データベースマイグレーション設定 (Alembic) - 次回実装予定

### Phase 3: Pydanticスキーマ実装・拡張 (2025-10-06完了)
**進捗:** 100% ✅

#### 完了
- [x] app/schemas/training.py - 完全拡張
  - [x] TrainingSessionCreate - フィールドバリデーション強化
  - [x] TrainingSessionResponse - 計算プロパティ追加 (progress_percentage, is_running, duration_seconds)
  - [x] TrainingSessionUpdate - 更新スキーマ追加
  - [x] TrainingMetricCreate/Response - 環境固有メトリクス対応
  - [x] TrainingMetricsListResponse - ページネーション対応
  - [x] 2025-10-13: `TrainingAlgorithm` Enumでアルゴリズム入力を制限し、API層と整合
- [x] app/schemas/environment.py - 完全拡張
  - [x] EnvironmentStateCreate/Response - プレイバック用スキーマ
  - [x] EnvironmentStatesListResponse - ページネーション対応
  - [x] EnvironmentDefinitionCreate/Response
- [x] app/schemas/websocket.py - 完全実装
  - [x] TrainingProgressEvent - 学習進捗メッセージ
  - [x] TrainingStatusEvent - ステータス変更メッセージ
  - [x] TrainingErrorEvent - エラーメッセージ
  - [x] EnvironmentUpdateEvent - 環境更新メッセージ
  - [x] ConnectionAckMessage - 接続確認メッセージ
  - [x] PingMessage/PongMessage - ハートビート用
- [x] app/schemas/jobs.py - 拡張
  - [x] JobStatusResponse - Celeryジョブステータス
  - [x] JobListResponse - ジョブ一覧
  - [x] JobCancelRequest/Response - キャンセル機能
- [x] app/schemas/files.py - 新規作成
  - [x] FileUploadResponse - ファイルアップロード
  - [x] FileMetadataResponse - ファイルメタデータ
  - [x] FileListResponse - ファイル一覧
  - [x] ModelFileInfo - モデルファイル情報
- [x] app/schemas/common.py - 共通スキーマ拡張
  - [x] ErrorResponse - エラーレスポンス
  - [x] SuccessResponse - 成功レスポンス
  - [x] PaginationParams/PaginatedResponse - ページネーション共通

### Phase 4: APIエンドポイント実装・拡張
**進捗:** 95%

#### 完了
- [x] app/api/v1/endpoints/training.py - 基本エンドポイント
- [x] app/api/v1/endpoints/training.py - GET /sessions/{id}/metrics (ページネーション対応)
- [x] app/api/v1/endpoints/training.py - POST /start, /{id}/pause, /{id}/resume, /{id}/stop を実装
- [x] app/api/v1/endpoints/training.py - stopエンドポイントに`force`クエリを追加し、Celeryタスクのrevokeとキュー状態の強制停止フラグを連携 (2025-10-14追加)
- [x] app/api/v1/endpoints/training.py - GET /list と GET /{id}/status を実装
- [x] app/api/v1/endpoints/training.py - DELETE /{id} エンドポイントを実装
- [x] app/api/v1/endpoints/jobs.py - ジョブキュー状態一覧 API を実装
- [x] app/services/training_service.py - サービス層の新規実装
- [x] app/core/training/job_manager.py - ジョブ管理スタブの拡張
- [x] app/schemas/training.py - 制御レスポンス・リストレスポンスの追加
- [x] app/api/v1/endpoints/environment.py - 環境制御API
- [x] app/api/v1/endpoints/environment.py - 環境セッション作成/リセット/アクション/終了APIを追加
- [x] app/core/environment/service.py - セッション管理とアクション実行ロジックを実装
- [x] app/core/environment/service.py - セッション上限とinfoシリアライズ対策を追加 (2025-10-12)
- [x] app/schemas/environment.py - セッション操作用スキーマを定義
- [x] app/api/v1/endpoints/health.py - ヘルスチェック
- [x] app/api/v1/endpoints/files.py - ファイル管理API実装（アップロード/一覧/削除/ダウンロード）

### Phase 5: WebSocket・リアルタイム通信
**進捗:** 100%

#### 完了
- [x] app/core/websocket/manager.py - WebSocketManager基本実装
- [x] app/api/v1/endpoints/websocket.py - WebSocketエンドポイント
- [x] WebSocketメッセージ型定義 (Pydantic モデル共通化)
- [x] セッション別ブロードキャスト機能テスト (ユニットテスト追加)
- [x] 接続・切断エラーハンドリング強化 (送信失敗時の自動切断・メタデータ追跡)
- [x] Ping/Pongハートビート実装 (接続ごとの keep-alive)
- [x] ハートビート間隔の設定化 (`Settings.websocket_heartbeat_interval` で制御)
- [x] WebSocket接続拒否時のクローズ理由改善 (4404コード + JSON理由)
- [x] WebSocketManager のユニットテスト拡充 (mark_seen/heartbeat/broadcast_all/metadata)
- [x] Redis Pub/Sub ベースのトレーニング進捗フォワーダーを実装し、セッション別リスナー管理を導入
- [x] WebSocket エンドポイントでのリスナーライフサイクル制御と再接続対応
- [x] Redis フォワーダーのユニットテスト (セッション配信・リスナー再利用) を追加

### Phase 6: Celeryバックグラウンドタスク (2025-10-06完了)
**進捗:** 100% ✅

#### 完了
- [x] app/tasks/celery_app.py - Celery設定
- [x] app/tasks/training_tasks.py - 完全実装
  - [x] run_ppo_training_task - PPO学習タスク完全実装
    - [x] PPOServiceとの統合
    - [x] Redis Pub/Sub と Celery状態フックによる進捗通知
    - [x] データベース状態更新と同期セッション利用
    - [x] エラーハンドリング・通知 (Redis経由)
  - [x] run_a3c_training_task - A3C学習タスク (骨組み、未実装警告あり)
  - [x] stop_training_task - 学習停止タスク
- [x] app/tasks/file_tasks.py - ログ/モデルファイルのアーカイブタスクを実装し、ZIP出力とバリデーションを整備
- [x] app/services/training_dispatcher.py - Celeryタスクrevokeメソッドを追加し、強制停止パスから利用 (2025-10-14追加)
  

#### TODO
- [ ] A3C学習タスクの完全実装
- [x] CeleryリボークAPI連携など強制停止パスの整備 (協調停止は実装済み)

#### マシン固有 - 動作確認状況
- ⏳ Celeryワーカー起動確認 (各環境で実施が必要)
- ⏳ Redis接続確認 (各環境で実施が必要)

---

### Phase 7: RL統合 (2025-10-06完了)
**進捗:** 85% ✅

#### 完了
- [x] PPOServiceクラス実装 (app/core/training/ppo_service.py)
  - [x] Stable-Baselines3統合
  - [x] 環境作成機能 (standard/enhanced対応)
  - [x] モデル作成・設定 (ハイパーパラメータ対応)
  - [x] 学習実行機能 (非同期対応)
  - [x] モデル保存・ロード機能
  - [x] TensorBoardログ対応
- [x] rl/callbacks/websocket_callback.py - 完全実装
  - [x] WebSocketTrainingCallback - SB3互換コールバック
    - [x] リアルタイム進捗配信
    - [x] エピソード追跡
    - [x] ステータス通知
  - [x] DatabaseMetricsCallback - DB保存コールバック
    - [x] メトリクス自動保存
    - [x] エラーハンドリング
- [x] rl/environments/ - 既存環境確認
  - [x] SecurityEnvironment - Gymnasium互換確認
  - [x] EnhancedSecurityEnvironment - 動作確認予定

#### TODO
- [ ] A3CServiceクラス実装 (オプション)
  - [ ] カスタムPyTorch実装
  - [ ] マルチプロセス学習
- [ ] 学習実行・エンドツーエンド検証

#### マシン固有 - 動作確認状況
- ⏳ 学習実行テスト (各環境で実施が必要)
- ⏳ GPU動作確認 (GPUマシンで実施が必要)

---

## ⏳ 未着手の項目

### Phase 8: テスト実装 (80%)
- [x] pytest設定 (tests/conftest.py で共通パスを整備)
- [ ] APIテスト実装
  - [x] 学習制御APIテスト - メトリクス取得 (5ケース)
- [x] ファイル管理APIテスト - アップロード/一覧/削除/バリデーション (5ケース)
- [x] 学習制御APIテスト - その他エンドポイント
    - [x] start/pause/resume/stop/status/list/delete のユニットテスト追加 (JobManagerスタブ利用)
  - [x] FastAPIファイルアップロード依存 (`python-multipart`) と asyncioテスト依存 (`pytest-asyncio`) の不足を解消
  - [x] 環境セッションAPIテスト（作成/リセット/アクション/終了）
  - [x] 環境サービスのセッション管理ユニットテスト
- [x] WebSocketテスト (エンドポイントレベル)
- [x] WebSocket接続管理ユニットテスト (manager)
- [x] トレーニング制御API統合テスト - `/training/start` 正常系と `pause`/`resume` エラーハンドリングを検証 (2025-10-13追加)
- [x] トレーニング制御API統合テスト - `stop` 正常終了・`status`/`list`/`delete` エンドポイントの永続化連携を検証 (2025-10-13追加)
- [x] トレーニング制御API統合テスト - Celeryタスクディスパッチと停止リクエストの経路をスタブ検証 (2025-10-13追加)
- [x] トレーニング制御APIの単体テストでCeleryディスパッチャをスタブ化し、ユニットテストがRedisなしで実行できるよう修正 (2025-10-13追加)
- [x] `tests/integration/test_training_control_endpoints.py` へリネームし、ユニットテストとのモジュール名衝突を解消 (2025-10-13追加)
- [x] CeleryトレーニングタスクがRedis Pub/Subで進捗・完了イベントを発行し、Redisコールバックのユニットテストを追加 (2025-10-14追加)
- [ ] 統合テスト実装 (最低1つ) - ファイル管理APIのダウンロード統合テストを追加済み、トレーニング制御APIは start/pause/resume をカバー (Celery連携シナリオは未着手)
- [ ] カバレッジ70%以上達成
- [x] GitHub Actionsで単体テストを自動実行
- [x] CIでの `ModuleNotFoundError` 調査と解消 (tests/unit 全体を対象に実行可能に)

### Phase 9: Docker環境構築 (40% - 検証必要)
- [x] docker-compose.yml存在確認
- [x] Docker 利用手順を README に記載 (ローカル起動手順の明文化)
- [ ] Dockerfile作成・確認
- [ ] Docker環境起動テスト
- [ ] 全サービスヘルスチェック
- [ ] PostgreSQL接続確認
- [ ] Redis接続確認
- [ ] Celeryワーカー起動確認

---

## ⚠️ 既知の問題・課題

### 技術的課題
1. **非同期処理の一貫性**
   - FastAPIの非同期エンドポイントとCeleryタスクの連携方法
   - WebSocketブロードキャストの非同期実装

2. **データベース設計**
   - TrainingMetricsテーブルのデータ増大対策
   - 時系列データの効率的なクエリ方法

3. **RL統合**
   - Stable-Baselines3とカスタムA3C実装の共存方法
   - 学習中の中断・再開処理

4. **インタラクティブ環境セッションのリソース管理**
   - タイムアウトと定期クリーンアップは実装済み。運用ログを観測し、必要に応じてタイムアウト値やクリーンアップ頻度を調整する必要あり。
   - 長時間アイドルセッションの運用ポリシー（通知有無・延長手段）を整理する必要あり。

4. **日付時刻処理の更新** (2025-10-10 解消)
   - `app/utils/datetime.py` の `utcnow()` ユーティリティ導入済み。引き続きUTC表現の整合性を監視。

### 設計上の検討事項
1. **認証・認可**
   - 現状は実装なし、将来的に追加が必要か？

2. **スケーラビリティ**
   - 複数の学習セッションの同時実行
   - Celeryワーカーのスケーリング戦略

3. **モニタリング**
   - ログ収集・分析基盤
   - メトリクス可視化 (Prometheus + Grafana等)

---

## 📝 次のアクションアイテム (優先度順)

### 🔥 高優先度
1. **Phase 4/6フォロー**: CeleryリボークAPIなど強制停止パスの実証と、再開/再キューイング時の状態遷移設計
2. **Phase 5→6連携**: Redis転送とジョブマネージャー状態を同期させ、WebSocketブリッジの自動監視まで仕上げる
3. **Phase 8継続**: Celeryタスクとジョブキューのエラー時ロールバックシナリオを設計し、バックプレッシャー制御を検討

### 🌟 中優先度
4. **Phase 9完了**: Docker環境の完全検証
5. **ドキュメント整備**: APIドキュメント充実
6. **パフォーマンステスト**: 負荷テスト実施

### 📌 低優先度 (後回し可)
7. **運用監視**: ログ収集・分析基盤の具体化
8. **リポジトリ整備**: `.gitignore` の適用範囲を継続的に確認し、必要なら追加除外ルールを検討

---

## 📚 参考資料

- [設計書] `instructions/01_system_architecture_design_standalone.md`
- [API設計] `instructions/02_backend_api_design_standalone.md`
- [実装ガイド] `instructions/prompts/01_backend_implementation_guide.md`
- [プロジェクト指示] `CLAUDE.md`
- [日記] `report/DIARY.md`

---

**注意事項:**
- このファイルは実装進捗に応じて随時更新してください
- 新しい課題や問題が見つかった場合は「既知の問題・課題」に追記してください
- セッションごとの作業内容は `report/DIARY.md` に記録してください
