# GitHub Copilot Agent Guide

このドキュメントは GitHub Copilot を本リポジトリにおける補助エージェントとして活用する際の指針をまとめたものです。

## 📚 参照必須ドキュメント
- [プロジェクト概要](../instructions/00_SUMMARY.md)
- [システムアーキテクチャ設計](../instructions/01_system_architecture_design_standalone.md)
- [バックエンドAPI設計](../instructions/02_backend_api_design_standalone.md)
- [テスト計画](../instructions/04_test_design_standalone.md)
- [実装/レビュー用プロンプト](../instructions/prompts)
- [進捗管理レポート](../report/PROGRESS.md)
- [開発日記サマリー](../report/summary/DIARY*.md)
- [最新の開発日記](../report/DIARY06.md)

> **必須:** 上記ドキュメントとプロンプトを熟読し、現状の進捗・設計・実装方針を理解してからコード提案やレビュー支援を行ってください。

## ✅ ワークフロー指針
1. セッション開始時に必ず `report/PROGRESS.md`、`report/summary/DIARY*.md`、`report/DIARY06.md` を確認し、最新の課題や作業履歴を把握すること。
2. 実装やレビューを行う前に、関連する設計書 (`instructions/` 配下) とプロンプト (`instructions/prompts/` 配下) を参照し、受け入れ基準と制約条件を明確化すること。
3. 提案コードはテスト駆動開発を意識し、必要なテスト追加・更新を促すこと。`pytest` を主要な品質ゲートとして扱い、実行指示があればそれに従うこと。
4. 作業完了時には進捗と判断理由を `report/PROGRESS.md` および `report/DIARY06.md` へ反映するよう促し、ドキュメント整備を支援すること。

## 🔍 レビュー・出力スタイル
- Pull Request レビューやフィードバックを生成する場合は、**必ず日本語で記述**してください。
- レビューでは [`instructions/prompts`](../instructions/prompts) 内の該当プロンプト (特に [`02_codex_review_prompt.md`](../instructions/prompts/02_codex_review_prompt.md)) を参照し、既存のエージェントガイド (Codex/Claude) と整合性のある観点で指摘を行ってください。

## 🧪 テスト & 品質ゲート
- 変更提案では `pytest` の実行やテストケース追加を優先し、テストカバレッジ向上を支援する提案を行ってください。
- セキュリティ・性能・並行実行に関わる変更では、設計書に記載の追加検証手順を参照し、必要な確認事項をリマインドしてください。

## 🛠️ 開発環境メモ
- Python 仮想環境は `uv venv` で作成し、`uv pip install -r requirements.txt` で依存関係をインストールします。
- API サーバーは `uvicorn app.main:app --reload` (または `uv run uvicorn app.main:app --reload`) で起動します。
- Redis や Celery などの外部サービスが必要な場合は、`README.md` のセットアップガイドを参照してください。

上記方針に従うことで、GitHub Copilot が既存エージェント (Codex/Claude) と一貫性のあるワークフローおよび品質基準を維持しながら開発・レビュー支援を行えるようにします。
