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

## リポジトリ取得

```bash
git clone https://github.com/your-org/security-robot-be.git
cd security-robot-be
```

## uv を用いたローカル開発環境構築

1. **仮想環境の作成**
   ```bash
   uv venv
   ```
   `.venv/` 配下に仮想環境が作成されます。

2. **依存関係のインストール**
   ```bash
   uv pip install -r requirements.txt
   ```
   `pyproject.toml` に記載された依存関係も同時に解決されます。

3. **仮想環境への入る (任意)**
   ```bash
   source .venv/bin/activate
   ```
   `uv run` を使う場合はアクティベート不要です。

4. **アプリケーションの起動**
   ```bash
   uv run uvicorn app.main:app --reload
   ```
   デフォルトでは `http://127.0.0.1:8000` で API が待ち受けます。

5. **テストの実行 (任意)**
   ```bash
   uv run pytest tests/unit -q
   ```

### 既定の設定

- デフォルトでは SQLite (`security_robot.db`) を利用します。`.env` ファイルや環境変数で `DATABASE_URL` を上書きできます。
- Redis への接続先は `REDIS_URL` で制御します。ローカルで Redis を使用しない場合はモックに差し替えてください。

## Docker を利用した実行

ローカルに Docker と Docker Compose を導入済みであれば、以下の手順でバックエンドと Redis をまとめて起動できます。

```bash
cd docker
docker compose up --build
```

- API: http://localhost:8000
- Redis: localhost:6379
- ボリューム: `models/`, `logs/`, `playback_data/` がホスト側にマウントされます。

停止する場合は `Ctrl + C` でコンテナを停止し、`docker compose down` を実行してください。

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
