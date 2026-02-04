# scripts/

修士論文（Chapter 6）の実験データ生成・分析・可視化・DB 連携を行うスクリプト群。

すべてのスクリプトは **プロジェクトルート** (`security-robot-be/`) から実行する。

```bash
cd /path/to/security-robot-be
python scripts/<script_name>.py
```

---

## 実験実行スクリプト

### `run_thesis_experiments.py`

PPO アルゴリズムによる強化学習実験を実行する。ロボット台数 N を引数で指定し、20x20 グリッド上で 200,000 ステップの学習を行う。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/run_thesis_experiments.py --robots 1` |
| 入力 | なし（パラメータはスクリプト内で定義） |
| 出力 | `monitor_n{N}.monitor.csv`, `trajectory_n{N}.jsonl` |
| 乱数依存 | あり（PPO の重み初期化・サンプリング） |

環境パラメータ: `width=20, height=20, max_episode_steps=4000, revisit_window=100`

---

### `run_8x8_experiment.py`

8x8 グリッドでのシングルエージェント PPO 実験。`run_thesis_experiments.py` の 8x8 版。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/run_8x8_experiment.py` |
| 入力 | なし |
| 出力 | `monitor_8x8_ppo.monitor.csv`, `trajectory_8x8_ppo.jsonl` |
| 乱数依存 | あり（PPO の重み初期化・サンプリング） |

---

### `run_8x8_ppo_with_logging.py`

8x8 PPO 実験に加え、TensorBoard 用の損失ログ（`progress.csv`）とカバレッジ到達ステップ数（`coverage_metrics.csv`）を詳細に記録する。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/run_8x8_ppo_with_logging.py` |
| 入力 | なし |
| 出力 | `logs_8x8/monitor.monitor.csv`, `logs_8x8/progress.csv`, `logs_8x8/coverage_metrics.csv` |
| 乱数依存 | あり（PPO の重み初期化・サンプリング） |

SB3 の `configure()` で CSV ロガーを設定し、`CoverageMetricsCallback` でエピソードごとの 100% カバレッジ到達ステップを記録する。

---

### `run_8x8_baseline.py`

8x8 グリッドでジグザグ（`HorizontalScanAgent`）とスパイラル（`SpiralAgent`）のルールベースエージェントを 50 エピソード実行するベースライン実験。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/run_8x8_baseline.py` |
| 入力 | なし |
| 出力 | `trajectory_8x8_zigzag.jsonl`, `trajectory_8x8_spiral.jsonl`, `monitor_8x8_zigzag.csv`, `monitor_8x8_spiral.csv` |
| 乱数依存 | あり（`map_type="random"` により毎エピソード障害物配置が変わる） |

エージェント自体は決定論的だが、環境のランダムマップ生成により再現不可。

---

### `run_multi_agent_baseline.py`

4 体のロボット（N=4）によるマルチエージェント・ベースライン実験。ジグザグとスパイラルの各エージェントを 50 エピソード実行する。ロボット同士の衝突を回避するため、優先度ベースの逐次予約方式を採用。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/run_multi_agent_baseline.py` |
| 入力 | なし |
| 出力 | `trajectory_multi_zigzag.jsonl`, `trajectory_multi_spiral.jsonl`, `monitor_multi_zigzag.csv`, `monitor_multi_spiral.csv` |
| 乱数依存 | あり（`map_type="random"`） |

`FixedStartSecurityEnvironment` により初期配置を四隅（TL, BR, TR, BL）に固定しているが、障害物配置は毎回ランダム。

---

## 分析・可視化スクリプト

### `analyze_thesis_data.py`

論文 Chapter 6 の統計データ（平均報酬・カバレッジ・脅威度、相関係数など）を算出し、標準出力に表示する。また、初期配置ヒートマップ画像を生成する。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/analyze_thesis_data.py` |
| 入力 | `monitor_n{1,2,3,4}.monitor.csv`, `trajectory_n{1,2,3,4}.jsonl` |
| 出力 | `report/result/thesis_experiment/figures/placement_heatmaps.png`, 標準出力 |
| 乱数依存 | なし（入力データに対して決定論的） |

---

### `analyze_8x8_results.py`

8x8 実験の PPO とベースライン（ジグザグ・スパイラル）を比較し、報酬・脅威推移のグラフと比較表を出力する。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/analyze_8x8_results.py` |
| 入力 | `monitor_8x8_ppo.monitor.csv`, `monitor_8x8_zigzag.csv`, `monitor_8x8_spiral.csv` |
| 出力 | `analysis_8x8_transition.png`, 標準出力 |
| 乱数依存 | なし（入力データに対して決定論的） |

---

### `plot_playback_charts.py`

学習ログ（monitor CSV）から、論文掲載用のカバレッジ・報酬・脅威度の学習曲線グラフ（SVG/PNG）を生成する。シングルエージェント（N=1）とマルチエージェント（N=2,3,4）の両方に対応。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/plot_playback_charts.py` |
| 入力 | `monitor_n{1,2,3,4}.monitor.csv` |
| 出力 | `report/result/thesis_experiment/figures/thesis_single_*.png/svg`, `report/result/thesis_experiment/figures/thesis_multi_*.png/svg` |
| 乱数依存 | なし（入力データに対して決定論的） |

---

### `plot_trajectory_charts.py`

軌跡ログ（JSONL）から、ロボットの移動軌跡図とエピソード内の脅威度推移グラフを生成する。特定のエピソード（初期・中期・後期）を抽出して可視化する。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/plot_trajectory_charts.py` |
| 入力 | `trajectory_n1.jsonl`, `trajectory_n4.jsonl` |
| 出力 | `report/result/thesis_experiment/figures/thesis_single_trajectories.png/svg`, `report/result/thesis_experiment/figures/thesis_multi_trajectories.png/svg`, `report/result/thesis_experiment/figures/thesis_single_threat_transition.png/svg` |
| 乱数依存 | なし（入力データに対して決定論的） |

---

### `plot_8x8_detail_charts.py`

`logs_8x8/` 配下の詳細ログ（monitor, progress, coverage_metrics）から、8x8 PPO 実験用の論文品質グラフを生成する。脅威度・報酬・カバレッジ・100% 到達ステップ・各種損失関数の推移を個別に出力。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/plot_8x8_detail_charts.py` |
| 入力 | `logs_8x8/monitor.monitor.csv`, `logs_8x8/progress.csv`, `logs_8x8/coverage_metrics.csv` |
| 出力 | `report/result/thesis_experiment/figures/8x8_ppo_threat.png`, `8x8_ppo_reward.png`, `8x8_ppo_coverage.png`, `8x8_ppo_loss_*.png` |
| 乱数依存 | なし（入力データに対して決定論的） |

---

## DB 連携スクリプト

### `import_monitor_to_db.py`

実験結果の CSV/JSONL をバックエンドの PostgreSQL にインポートする。フロントエンドの Playback 機能や学習曲線表示のために必要。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/import_monitor_to_db.py` （全 N）または `python scripts/import_monitor_to_db.py 1` （N=1 のみ） |
| 入力 | `monitor_n{N}.monitor.csv`, `trajectory_n{N}.jsonl` |
| 出力 | DB テーブル: `trainingjob`, `trainingmetric`, `environmentstate` |
| 前提条件 | PostgreSQL が稼働中であること |

---

### `import_playback.py`

ベースライン実験（Spiral/Zigzag のシングル・マルチ）の軌跡データを DB にインポートする。5000 行の上限付き。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/import_playback.py` |
| 入力 | `trajectory_spiral.jsonl`, `trajectory_zigzag.jsonl`, `trajectory_multi_spiral.jsonl`, `trajectory_multi_zigzag.jsonl` |
| 出力 | DB テーブル: `trainingjob`, `environmentstate` |
| 前提条件 | PostgreSQL が稼働中であること |

---

### `import_8x8_playback.py`

8x8 PPO 実験の軌跡データ（Episode 50 のみ）を DB にインポートする。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/import_8x8_playback.py` |
| 入力 | `trajectory_8x8_ppo.jsonl` |
| 出力 | DB テーブル: `trainingjob`, `environmentstate` |
| 前提条件 | PostgreSQL が稼働中であること |

---

## ユーティリティ

### `create_backup.py`

API 経由で DB データをエクスポートし、ローカルのモデル・ログファイルと合わせて tar.gz アーカイブを作成する。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/create_backup.py` |
| 入力 | API (`http://localhost:8000/api/v1/training/...`), `models/*.pth`, `report/result/*.jsonl` |
| 出力 | `backups/security_robot_backup_{timestamp}.tar.gz` |
| 前提条件 | API サーバーが稼働中であること |

---

### `verify_collisions.py`

マルチエージェント実験の軌跡データを読み込み、静的障害物との衝突およびロボット同士の衝突が発生していないかを検証する。

| 項目 | 内容 |
|---|---|
| コマンド | `python scripts/verify_collisions.py` |
| 入力 | `trajectory_multi_zigzag.jsonl`, `trajectory_multi_spiral.jsonl` |
| 出力 | 標準出力（衝突件数のサマリ） |

---

## スクリプト間の依存関係

```
実験実行                       分析・可視化                   DB連携
──────────                     ──────────                     ──────

run_thesis_experiments.py      plot_playback_charts.py        import_monitor_to_db.py
  ├→ monitor_n{N}.csv    ───→   ├→ thesis_single_*.png  ───→   └→ DB (trainingmetric,
  └→ trajectory_n{N}.jsonl ─→   └→ thesis_multi_*.png           environmentstate)
                            │
                            ├─ plot_trajectory_charts.py
                            │    ├→ thesis_*_trajectories.png
                            │    └→ thesis_*_threat_transition.png
                            │
                            └─ analyze_thesis_data.py
                                 ├→ placement_heatmaps.png
                                 └→ 統計値 (stdout)

run_8x8_experiment.py          analyze_8x8_results.py
  ├→ monitor_8x8_ppo.csv  ───→   └→ analysis_8x8_transition.png
  └→ trajectory_8x8_ppo.jsonl

run_8x8_baseline.py                                           import_8x8_playback.py
  ├→ monitor_8x8_zigzag.csv ──→ analyze_8x8_results.py  ───→   └→ DB (environmentstate)
  └→ monitor_8x8_spiral.csv

run_8x8_ppo_with_logging.py   plot_8x8_detail_charts.py
  └→ logs_8x8/           ───→   └→ 8x8_ppo_*.png

run_multi_agent_baseline.py    verify_collisions.py           import_playback.py
  ├→ trajectory_multi_*.jsonl ─→  └→ 衝突検証 (stdout)   ───→   └→ DB (environmentstate)
  └→ monitor_multi_*.csv
```
