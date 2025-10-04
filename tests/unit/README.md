# Unit Tests

フォルダー構成は `report/prompt/03_unit_testing_prompt.md` の指針に合わせており、API、サービス、RLアルゴリズム、コア設定、ユーティリティの各レイヤーを個別に検証できるように分類しています。

```
unit/
├── api/              # FastAPIエンドポイントのテスト
├── services/         # ドメインサービスのテスト
├── ml/               # 強化学習アルゴリズムのテスト
├── core/             # 設定・DB・Redisユーティリティのテスト
└── utils/            # 例外やヘルパー関数のテスト
```

各ディレクトリには `.gitkeep` を配置しており、今後の実装時にpytestテストモジュールを追加できます。
