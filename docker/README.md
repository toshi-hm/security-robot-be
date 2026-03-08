# Docker ディレクトリ概要

このディレクトリにはローカル開発および検証用の Dockerfile と Compose 設定が格納されています。ここでは `docker/docker-compose.yml` のビルド構成で有効化している `network: host` 設定について補足します。

## GPU 前提の構成

この Compose 構成は GPU 利用を前提にしています。NVIDIA Container Toolkit を導入した上で実行してください。

## `network: host` をビルド時に使用する理由

- ベースイメージは Debian 系 (python:3.12-slim) であり、`build-essential` 等の APT パッケージをビルドプロセス中にインストールします。
- 企業ネットワークなどで外部 DNS が制限されている場合、Docker のデフォルトネットワークから `deb.debian.org` へ名前解決できず、`apt-get update` が失敗します。
- Compose の `build` セクションで `network: host` を指定することで、ビルド時のみホストマシンのネットワークスタックを利用し、DNS 制限を回避します。

## セキュリティへの影響

- `network: host` は **ビルドステージでのみ** 有効です。`docker compose up` 実行時のランタイムコンテナは従来どおりのブリッジネットワーク上で起動するため、ホストネットワーク上でサービスが公開されることはありません。
- ホストの DNS 設定をそのまま利用するため、ビルド時にホストが信頼する名前解決サーバーへ問い合わせが送られます。社内ネットワークポリシー上問題がないか事前に確認してください。

## 代替手段

ホストネットワークの利用が許容されない環境では、以下のいずれかを検討してください。

1. **HTTP/HTTPS プロキシを利用**: `docker build` 時に `http_proxy` / `https_proxy` / `no_proxy` 環境変数を設定し、社内プロキシ経由で APT ミラーへアクセスする。
2. **Docker デーモンの DNS 設定を明示**: `/etc/docker/daemon.json` に `"dns": ["<社内DNS>"]` を追加し、Docker デフォルトネットワークからも社内 DNS へ到達できるようにする。
3. **社内 APT ミラーを利用**: `Dockerfile` の `sources.list` を差し替え、到達可能な社内ミラーからパッケージを取得する。

いずれの場合も、`docker/docker-compose.yml` の `network: host` 行を削除またはコメントアウトし、ビルドが成功することを確認してください。

## 参考

- [Docker ドキュメント: Use host networking](https://docs.docker.com/network/host/)
- [Docker Compose file reference: build.network](https://docs.docker.com/compose/compose-file/build/#network)
