# セキュリティロボット強化学習システム - 開発日記 (DIARY06)

このファイルは最新のセッションログを記録します。作業前に `report/summary/DIARY05_SUMMARY.md`、`report/PROGRESS.md` を確認してください。

## 📑 目次
- [2025-12-19 セッション08](#2025-12-19-セッション08)
- [2025-12-19 セッション07](#2025-12-19-セッション07)
- [2025-12-19 セッション06](#2025-12-19-セッション06)
- [2025-12-19 セッション05](#2025-12-19-セッション05)
- [2025-11-23 セッション01](#2025-11-23-セッション01)
- [2025-11-26 セッション02](#2025-11-26-セッション02)
- [2025-12-05 セッション03](#2025-12-05-セッション03)
- [2025-12-06 セッション04](#2025-12-06-セッション04)

---

## テンプレート

### 🎯 セッション目標
-

### ✅ 実施内容
-

### 📊 成果物
-

### 🧠 学んだこと・課題
1.

### ⏭️ 次回セッションの予定
1.

### 🔗 関連コミット
-

## 2025-12-19 セッション08

### 🎯 セッション目標
- バックアップ取り込み時の重複エラーを解消する

### ✅ 実施内容
1. `trainingmetric` の主キー衝突を回避するため、メトリクス挿入時に `id` を付与しないよう修正
2. 既存データとの重複を避けるため、`(timestep, episode)` の既存ペアをデフォルトでスキップする挙動へ変更

### 📊 成果物
- `scripts/import_backup_trainingdata.py`: 重複スキップの既定化と `id` 省略

### 🧠 学んだこと・課題
1. バックアップ取り込み時は主キーをそのまま使うと衝突しやすく、自然キーでの重複判定が安全

### ⏭️ 次回セッションの予定
1. 取り込みスクリプトを再実行して結果を確認する

### 🔗 関連コミット
- なし

---

## 2025-12-19 セッション07

### 🎯 セッション目標
- バックアップ内の training data を PostgreSQL に登録する手順を整備する

### ✅ 実施内容
1. `backup/security_robot_backup_20251213_141144.tar.gz` を展開し、`db_export.json` の内容を確認
2. PostgreSQL 取り込み用に `scripts/import_backup_trainingdata.py` を追加し、ジョブ/メトリクスの投入処理を実装
3. PROGRESS の次アクションに取り込み実行の項目を追加

### 📊 成果物
- `scripts/import_backup_trainingdata.py`: `db_export.json` の読み込みと DB 取り込みスクリプト
- `report/PROGRESS.md`: 取り込み実行のアクション追加

### 🧠 学んだこと・課題
1. `Settings` は `.env` を自動読み込みしないため、`DATABASE_URL` は引数または環境変数で指定する必要がある

### ⏭️ 次回セッションの予定
1. PostgreSQL 接続情報を確認し、取り込みスクリプトを実行する

### 🔗 関連コミット
- なし

---

## 2025-12-19 セッション06

### 🎯 セッション目標
- GPU 必須構成に戻し、Compose 起動時に必ず GPU を使う状態へ戻す

### ✅ 実施内容
1. `docker/docker-compose.yml` で CUDA ベースイメージを既定化し、`gpus: all` と `privileged: true` を付与
2. `docker/Dockerfile` の `BASE_IMAGE` 既定を CUDA に戻す
3. GPU オーバーライド Compose を削除し、README と docker/README を GPU 前提に更新

### 📊 成果物
- `docker/docker-compose.yml`: GPU必須の構成に戻し、`gpus: all` を追加
- `docker/Dockerfile`: CUDA ベースイメージを既定化
- `README.md`, `docker/README.md`: GPU前提の手順に更新
- `.env.example`: GPU向けのベースイメージ注釈へ更新

### 🧠 学んだこと・課題
1. Compose 側で `gpus: all` を明示しないと GPU 利用が有効化されない

### ⏭️ 次回セッションの予定
1. `docker compose up --build` で GPU が認識されることを確認する

### 🔗 関連コミット
- なし

---

## 2025-12-19 セッション05

### 🎯 セッション目標
- Docker Compose 起動エラーの原因を特定し、CPU環境でも起動できるように改善する

### ✅ 実施内容
1. GPU前提の Compose 設定が CPU 環境で失敗する前提を整理し、CPU/GPU の切り替えを明示化
2. `docker/Dockerfile` にベースイメージ切替用のビルド引数を追加し、CPU向けを既定化
3. GPU用の `docker/docker-compose.gpu.yml` を追加し、GPU時のみCUDAベースイメージとデバイス予約を適用
4. README と docker/README で起動手順を更新

### 📊 成果物
- `docker/Dockerfile`: `BASE_IMAGE` のビルド引数化と Python 解決の柔軟化
- `docker/docker-compose.yml`: CPU向け既定の Compose 設定に変更
- `docker/docker-compose.gpu.yml`: GPU向けオーバーライド追加
- `README.md`, `docker/README.md`, `.env.example`: 起動手順と補足の更新

### 🧠 学んだこと・課題
1. GPU前提の Compose 設定は CUDA 非対応環境で起動を阻害するため、オーバーライド分離が安全

### ⏭️ 次回セッションの予定
1. 実機で `docker compose up` / GPU オーバーライドの双方を確認

### 🔗 関連コミット
- なし

---

### 2025-11-23 セッション01

### 🎯 セッション目標
- `rl/environments/map_generator.py` のコンフリクト解消とインデックス修正確認

### ✅ 実施内容
- `_force_connectivity` のコンフリクトを解消し、`obstacles[y][x]` の行優先インデックスに統一
- コンフリクトマーカーを除去し、接続強制処理の経路開放方向を確認

### 📊 成果物
- `rl/environments/map_generator.py` のコンフリクト解消 (行優先のインデックス計算を維持)

### 🧠 学んだこと・課題
1. 生成マップは行(y)/列(x)のインデックスで保持しているため、経路開放時も同じ軸で扱う必要がある

### ⏭️ 次回セッションの予定
1. 必要に応じて関連テストを実行し、環境生成の回帰がないか確認する

### 🔗 関連コミット
- なし

---

## 2025-11-26 セッション02

### 🎯 セッション目標
- Room環境での訓練エラー (`PlaybackRecordingWrapper` がGymnasium環境として認識されない問題) を解消する

### ✅ 実施内容
1. **エラー原因の特定**
   - Celeryワーカーログから `ValueError: The environment is of type <class 'app.core.training.playback_recorder.PlaybackRecordingWrapper'>, not a Gymnasium environment` を確認
   - `PlaybackRecordingWrapper` が `gymnasium.Wrapper` を継承していないことが原因と判明
   - `DummyVecEnv` が内部で `_patch_env` を呼び出し、Gymnasium/Gym環境チェックを行うため失敗

2. **修正実装**
   - `app/core/training/playback_recorder.py`:
     - `gymnasium as gym` をインポート
     - `PlaybackRecordingWrapper` を `gym.Wrapper` から継承
     - `super().__init__(env)` で親クラスを初期化
     - 手動で管理していた `action_space`, `observation_space`, `metadata` の初期化を削除(親クラスが処理)
     - 型ヒントを `Any` から `gym.Env` に変更

3. **テスト修正**
   - `tests/unit/training/test_playback_recorder.py`:
     - `from __future__ import annotations` をファイル先頭に移動(構文エラー解消)
     - テスト用ダミー環境 (`_DummyEnv`, `MinimalEnv`, `EnvWithMetadata`) を `gym.Env` から継承
     - `action_space` と `observation_space` を適切に初期化
     - `test_wrapper_copies_metadata` を `test_wrapper_preserves_metadata_reference` にリネーム
     - Gymnasium標準の挙動(メタデータ参照共有)に合わせてテストを更新
   - `tests/integration/test_playback_endpoints_integration.py`:
     - `from __future__ import annotations` をファイル先頭に移動

4. **追加エラーへの対応**
   - Docker環境で新たなエラー発生: `SecurityEnvironment` が `gymnasium.Env` を継承していないためアサーションエラー
   - `rl/environments/security_env.py`:
     - `from rl._gym_compat import gym` を追加
     - `SecurityEnvironment` を `gym.Env` から継承
     - `super().__init__()` で親クラスを初期化
     - 手動で設定していた `action_space`, `observation_space`, `metadata` の初期化を削除(親クラスが処理)
   - `EnhancedSecurityEnvironment` は `SecurityEnvironment` を継承しているため自動的に対応

5. **検証**
   - プレイバック録画ユニットテスト: 7件全てパス
   - 全体テストスイート: 261件パス、2件スキップ

### 📊 成果物
- `app/core/training/playback_recorder.py`: Gymnasium互換性確保
- `rl/environments/security_env.py`: `SecurityEnvironment` を `gym.Env` から継承
- `tests/unit/training/test_playback_recorder.py`: テスト環境をGymnasium準拠に更新
- `tests/integration/test_playback_endpoints_integration.py`: 構文エラー修正

### 🧠 学んだこと・課題
1. **Stable-Baselines3の環境要件**
   - `DummyVecEnv` は環境がGymnasium互換であることを厳密にチェックする
   - カスタムラッパーだけでなく、**ベース環境自体も** `gymnasium.Env` を継承する必要がある
   - `_gym_compat` を使っている場合、Gymnasiumがインストールされている環境では本物の `gym.Env` が使われる

2. **Gymnasium Wrapperの挙動**
   - `gymnasium.Wrapper` はメタデータ参照を共有する(コピーしない)
   - これは標準的な挙動であり、テストもそれに合わせるべき

3. **Python構文**
   - `from __future__ import annotations` は必ずファイルの最初(docstringの後、他のimportの前)に配置する必要がある

4. **テスト戦略**
   - ダミー環境を作成する場合も、実際のフレームワークAPI(Gymnasium)に準拠させることで、本番との互換性を保てる

5. **エラー対応の連鎖**
   - ラッパーを修正しても、ベース環境が非互換だと別のエラーが発生する
   - Gymnasium互換性は環境のクラス階層全体で保証する必要がある

### ⏭️ 次回セッションの予定
1. Docker環境でCeleryを起動し、実際のRoom訓練が成功することを確認
2. テストカバレッジが80%以上維持されているか確認
3. 必要に応じてPROGRESS.mdを更新

### 🔗 関連コミット
- (コミット予定)

### 2025-12-05 セッション03

### 🎯 セッション目標
- DockerコンテナからのGPUアクセスを確立し、`security-robot-be` での学習ジョブを実行可能にする

### ✅ 実施内容
1.  **Docker環境の修正**
    - `Dockerfile` のベースイメージを `nvidia/cuda:12.6.0-base-ubuntu24.04` に変更し、ホストのドライバーバージョン (570.xx) との互換性を確保。
    - `docker-compose.yml` (および `.prod.yml`) の `api` と `celery-worker` サービスに `privileged: true` を追加。これにより、コンテナ内での NVML 初期化エラー (`Unknown Error`) が解消された。

2.  **Celeryワーカーの設定変更**
    - デフォルトの `prefork` プールでは CUDA 初期化時に `RuntimeError: Cannot re-initialize CUDA in forked subprocess` が発生するため、実行モードを `pool=solo` (単一プロセス) に変更。
    - これにより、Celeryタスク内から正常にGPUを利用した学習 (`PPO`) が開始できることを確認。

3.  **Frontend接続修正**
    - リモート環境での開発において、Browserが `ws://localhost:8000` に接続しようとしてエラーになっていたため、`security-robot-fe/.env` に `NUXT_PUBLIC_WS_URL` を追加し、APIサーバーのIPアドレスを指定するように修正。

### 📊 成果物
- `Dockerfile`: CUDA 12.6 / Ubuntu 24.04 対応版
- `docker-compose.yml`: `privileged: true`, `command: ... -P solo` 追加版
- `security-robot-fe/.env`: WebSocket URL 設定追加

### 🧠 学んだこと・課題
1.  **新しいNVIDIAドライバーとDocker**: ホストのドライバーバージョンが新しい場合、古いCUDAベースイメージや非特権コンテナでは `NVML: Unknown Error` が発生することがある。`privileged` モードが有効だが、本番環境ではセキュリティ要件との兼ね合いを考慮する必要がある。
2.  **PyTorchとMultiprocessing**: CUDAコンテキストは `fork` されたプロセスに引き継げない。Celeryのデフォルトは `prefork` なので、GPUを使う場合は `spawn` 方式にするか、シンプルに `solo` (プロセスプールを使わない) にする必要がある。

### ⏭️ 次回セッションの予定
1.  GPUの並列計算能力を活かすため、環境の並列化 (Vectorized Environments) と CNN ポリシーの導入を計画・実装する。

### 🔗 関連コミット
- (未コミット)

---

### 2025-12-06 セッション04

### 🎯 セッション目標
- GPU最適化と高度な強化学習（Parallel Training / CNN）の設計を行う

### ✅ 実施内容
1.  **現状分析**
    - セッション03でGPU学習に成功したが、FPSがCPU版より低い（~250 vs ~500）ことを確認。
    - 原因は、小規模なグリッド環境と軽量なMLPモデルでは、GPUへのデータ転送オーバーヘッドが計算時間を上回るためと特定。

2.  **最適化計画の策定**
    - **並列環境 (Parallel envs)**: `SubprocVecEnv` を導入し、16〜32環境を同時実行することでバッチサイズを稼ぎ、GPU効率を高める。
    - **CNNポリシー**: グリッドを画像として扱うモデルを導入し、計算密度を高めるとともに表現力を向上させる。

3.  **ドキュメント作成**
    - `instructions/07_gpu_optimization_design.md` を新規作成し、Backend/Frontendの改修仕様を定義。

### 📊 成果物
- `instructions/07_gpu_optimization_design.md`: GPU最適化設計書
- `report/PROGRESS.md`: Phase 9完了、Phase 10追加

### 🧠 学んだこと・課題
1.  **GPU活用の条件**: 単にGPUを使えば速くなるわけではなく、十分な計算負荷（バッチサイズやモデルの複雑さ）が必要。強化学習では並列環境実行が常套手段。

### ⏭️ 次回セッションの予定
1.  設計書に基づき、Backend (`TrainingSessionCreate`, `PPOService`) の改修
2.  Frontend (`TrainingForm`) への詳細設定追加
3.  並列学習の実行とFPS向上確認

### 🔗 関連コミット
- (未コミット)
