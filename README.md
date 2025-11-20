# セキュリティロボット強化学習バックエンド

このリポジトリは、セキュリティロボット強化学習システムのバックエンド(API・学習ジョブ管理・RL統合)を提供する FastAPI ベースのサービスです。設計書一式は `instructions/` 配下にまとまっており、この README では環境構築と開発フローを中心にまとめています。

## プロジェクトの特徴

- FastAPI と SQLAlchemy による REST / WebSocket API 実装
- Celery + Redis を想定した学習ジョブのバックグラウンド実行
- `rl/` 配下に配置された強化学習アルゴリズム・環境の統合
- uv による Python 仮想環境および依存関係の一元管理

## 前提条件

以下のツールがインストールされていることを確認してください。

| ツール | 推奨バージョン | 備考 |
|-------|----------------|------|
| Python | 3.11 系 | uv が利用する Python 実行環境です |
| uv | 最新版 | https://docs.astral.sh/uv/ |
| Docker / Docker Compose | Docker 25.x / Compose v2 | コンテナで実行する場合に使用します |
| Git | 最新版 | リポジトリの取得に使用します |

> **uv のインストール例**
>
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```
>
> インストール後に `uv --version` で動作を確認してください。

## クイックスタート (API サーバー起動)

```bash
git clone https://github.com/your-org/security-robot-be.git
cd security-robot-be

# 1. 仮想環境を作成
uv venv

# 2. 依存関係をインストール
uv pip install -r requirements.txt

# 3. API サーバーを起動
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# (任意) 4. ユニットテストを実行
uv run pytest tests/unit -q
```

デフォルトでは `http://127.0.0.1:8000` にて API が利用可能です。ホットリロードが有効なため、コード変更は即座に反映されます。

## uv を用いたローカル開発環境構築

`uv` コマンドを利用することで仮想環境の作成からスクリプト実行までを統一的に扱えます。上記クイックスタート以外に以下のような活用が可能です。

1. **仮想環境へ手動で入る (任意)**
   ```bash
   source .venv/bin/activate
   ```
   `uv run` を使う場合はアクティベート不要です。

2. **アプリケーションを指定ホスト・ポートで起動**
   ```bash
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. **pytest を用いたテスト**
   ```bash
   uv run pytest
   ```

### 既定の設定

- デフォルトでは SQLite (`security_robot.db`) を利用します。`.env` ファイルや環境変数で `DATABASE_URL` を上書きできます。
- Redis への接続先は `REDIS_URL` で制御します。ローカルで Redis を使用しない場合はモックに差し替えてください。

### GPU対応設定

強化学習のトレーニングは、GPU (CUDA) を使用することで大幅に高速化できます。環境変数 `TRAINING_DEVICE` でデバイスを制御します。

| 環境変数 | 設定値 | 動作 |
|---------|--------|------|
| `TRAINING_DEVICE` | `auto` (デフォルト) | CUDAが利用可能な場合は自動的にGPUを使用、そうでなければCPU |
| `TRAINING_DEVICE` | `cpu` | 常にCPUを使用 |
| `TRAINING_DEVICE` | `cuda` | デフォルトのCUDAデバイスを使用 (GPU 0) |
| `TRAINING_DEVICE` | `cuda:N` | 特定のCUDAデバイスNを使用 (例: `cuda:1`) |

**設定例:**

```bash
# GPUを強制的に使用
export TRAINING_DEVICE=cuda

# CPUを強制的に使用（GPUが利用可能でも）
export TRAINING_DEVICE=cpu

# 特定のGPUを指定（複数GPU環境）
export TRAINING_DEVICE=cuda:1
```

**注意事項:**
- A3Cアルゴリズムは、CUDA使用時は `num_workers=1` に制限されます（PyTorchのマルチスレッド制約）
- PPOアルゴリズムは制限なくGPUを使用できます
- CUDA利用可能性は起動時に自動検証され、利用不可能な場合はエラーが発生します

## Docker を利用した実行

ローカルに Docker と Docker Compose を導入済みであれば、以下の手順でバックエンド / Celery ワーカー / PostgreSQL / Redis をまとめて起動できます。

> **注意**: Compose のビルド設定では `network: host` を指定しています。DNS 制限のあるネットワーク環境でも APT パッケージの取得が成功するようにするためで、ビルド完了後のランタイム通信には影響しません。ホストネットワーク利用を避けたい場合は、企業プロキシの設定や Docker デーモンの DNS 設定など代替手段を検討してください。

1. ルートディレクトリで `.env.example` をコピーし、機密値 (特に `POSTGRES_PASSWORD`) を書き換えて `.env` を作成します。
   ```bash
   cp .env.example .env
   # エディタでPOSTGRES_PASSWORDなどを編集
   ```
   Docker Compose はこのファイルを自動的に読み込み、サービス間で共有する環境変数を設定します。

```bash
cd docker
docker compose up --build
```

- API: http://localhost:8000 (`/api/v1/health` でヘルスチェック)
- PostgreSQL: localhost:5432 (`${POSTGRES_USER}` / `${POSTGRES_PASSWORD}`)
- Redis: localhost:6379
- Celery ワーカー: `docker compose logs -f celery-worker` で状態確認
- Celery 並列度: `.env` の `CELERY_WORKER_CONCURRENCY` で調整可能 (デフォルト 2)
- ボリューム: `models/`, `logs/`, `playback_data/`, `postgres_data/`

起動後は `docker compose ps` で全サービスが `healthy` になっていることを確認してください。ヘルスチェックは API / Celery ワーカー / PostgreSQL / Redis の 4 サービスに設定されています。

停止する場合は `Ctrl + C` でコンテナを停止し、`docker compose down` を実行してください。

本番用イメージをビルドする際は、ホストの UID/GID に合わせて `APP_UID` / `APP_GID` を指定できます。

```bash
docker build -f docker/Dockerfile --target production \
  --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g) \
  -t security-robot-rl/api:latest .
```

## API ドキュメント (GitHub Pages 公開)

`docs/` ディレクトリに配置された Swagger UI を GitHub Pages (Pages → Branch: `main`, Folder: `/docs`) として公開することで、ブラウザから API 仕様を閲覧できます。OpenAPI スキーマは FastAPI アプリケーションから自動生成され、Swagger UI が `openapi.json` を読み込んでレンダリングします。

### スキーマの再生成手順

API スキーマに変更が生じた場合は、以下のコマンドで `docs/openapi.json` を更新してください。

```bash
uv run python scripts/export_openapi.py
```

コマンド実行後に `docs/index.html` と同じディレクトリへ `openapi.json` が出力されます。ローカルで Swagger UI を確認する場合は、任意の静的ファイルサーバーを起動して `docs/` を公開してください。

```bash
python -m http.server 8001 --directory docs
# ブラウザで http://127.0.0.1:8001/ を開く
```

## リポジトリ構成

- `app/` – FastAPI アプリケーション本体 (ルーター、サービス、モデル、スキーマ等)
- `rl/` – 強化学習環境・アルゴリズム・コールバック
- `tests/` – ユニットテスト・統合テストの雛形
- `scripts/` – メンテナンス用スクリプト
- `docker/` – Dockerfile と docker-compose 設定
- `instructions/` – システム全体の設計書および実装ガイド
- `report/` – 開発日記や進捗管理ドキュメント

## 参考ドキュメント

詳細な設計・実装方針は以下のドキュメントを参照してください。

- `instructions/01_system_architecture_design_standalone.md`
- `instructions/02_backend_api_design_standalone.md`
- `instructions/prompts/01_backend_implementation_guide.md`

開発セッションのログや進捗は `report/summary/DIARY01.md`、`report/summary/DIARY02.md`、`report/DIARY03.md`、`report/PROGRESS.md` で管理されています。
