# 実験結果ログ (Experiment Result Log)

本ドキュメントは、マルチエージェント警備ロボットの強化学習実験の結果を記録するものです。

## 実験条件概要

- **環境**: Multi-Agent Security Grid (20x20)
- **エージェント数**: 3台
- **アルゴリズム**: PPO (Proximal Policy Optimization)
- **マップ**: Random Map (Seed固定: 42) - ウェイトの影響を比較するため同一シードを使用

## 実験履歴一覧

| Cycle | Job ID | Steps | Cov Weight | Exp Weight | Div Weight | Avg Reward | Final Coverage | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | 29 | 100k | 0.5 | 0.3 | 0.2 | 13030 | 0.54 | 完了 |
| **02** | 30 | 100k | 1.0 | 0.3 | 0.2 | 12550 | 0.65 | 完了 |
| **03** | 31 | 100k | 1.0 | 0.3 | 0.5 | 12790 | 0.67 | *無効(Std Env)* |
| **04** | 32 | 100k | 1.0 | 0.3 | 0.5 | 12383 | 0.69 | 完了 (Enhanced) |
| **05** | 33 | 100k | 2.0 | 0.3 | 0.5 | 12247 | 0.66 | 完了 (Enhanced) - 効果なし |
| **06** | 34 | 100k | 1.0 | 1.0 | 0.5 | 12873 | 0.67 | 完了 (Enhanced) - 報酬改善/Cov微増 |
| **07** | 35 | 100k | 1.0 | 1.0 | 1.0 | 12953 | 0.66 | 完了 (Enhanced) - 報酬最高/Cov低下 |
| **08** | 36 | 100k | 1.0 | 0.5 | 0.5 | 12763 | 0.73 | 完了 (Threat Penalty) |
| **09** | 39 | 100k | 1.0 | 0.5 | 0.5 | - | 0.60 | 完了 (High Drain) - 性能低下 |
| **10** | 46 | 100k | 1.0 | 0.5 | 0.5 | -2861 | TBD | 完了 (Strategic Init) - 報酬改善 |

---

## 詳細レポート

### Cycle 01: Initial Baseline

- **Job ID**: 29
- **実施日時**: 2025-12-07
- **目的**: ベースラインの確立
- **ハイパーパラメータ**:
    - `total_timesteps`: 100,000
    - `learning_rate`: 0.0003
    - `n_steps`: 2048 (default)
    - `batch_size`: 64
    - `gamma`: 0.99 (default)
    - `gae_lambda`: 0.95 (default)
    - `ent_coef`: 0.0 (default)
    - **Reward Weights**:
        - `coverage_weight`: 0.5
        - `exploration_weight`: 0.3
        - `diversity_weight`: 0.2
- **結果**:
    - **Average Reward**: 13030
    - **Final Coverage**: 0.54 (Max: 0.98, Low final indicates instability)
- **考察**:
    - 学習は収束傾向にあるが、エピソード終盤でのカバレッジ維持に課題がある可能性がある。
    - 報酬のカバレッジ重みが低いため、探索（移動）すること自体で得られる報酬（Exploration）や分散（Diversity）に最適化が偏った可能性がある。

### Cycle 02: Coverage Focus (完了)

- **Job ID**: 30
- **実施日時**: 2025-12-07
- **目的**: 報酬のカバレッジ重みを倍増させ、カバレッジ維持能力への影響を確認する。
- **ハイパーパラメータ**:
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: 1.0 (Increased from 0.5)
        - `exploration_weight`: 0.3
        - `diversity_weight`: 0.2
    - *Others same as Cycle 01*
- **結果**:
    - **Average Reward**: 12550 (Cycle 01: 13030)
    - **Final Coverage**: 0.65 (Cycle 01: 0.54)
- **考察**:
    - カバレッジ重みの増加により、最終的なカバレッジ性能が約11ポイント向上した。
    - 報酬総額は若干減少したが、これはカバレッジ（上限がある）により強く依存するようになったためか、あるいは多様性/探索報酬とのトレードオフによるものと推測される。
    - まだ0.65付近であり、完全なカバレッジには至っていない。さらに重みを上げるか、ロボット同士の協調（Diversity）を強化する必要があるかもしれない。

### Cycle 03: Diversity Optimization (完了)

- **Job ID**: 31
- **実施日時**: 2025-12-07
- **目的**: 多様性報酬（Diversity Weight）を強化し、エージェント間の協調（分散配置）を促進することでカバレッジ向上を図る。
- **ハイパーパラメータ**:
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: 1.0
        - `exploration_weight`: 0.3
        - `diversity_weight`: 0.5 (Increased from 0.2)
    - *Others same as Cycle 01*
- **結果**:
    - **Average Reward**: 12790 (Cycle 02: 12550) - 改善傾向
    - **Final Coverage**: 0.67 (Cycle 02: 0.65) - 微増
- **考察**:
    - 多様性報酬の増加は、報酬全体とカバレッジの両方をわずかに改善した。ロボット同士が離れることで、結果的にカバレッジが広がった可能性がある。
    - しかし、カバレッジの改善幅は小さい (0.65 -> 0.67)。
    - カバレッジを劇的に上げるには、カバレッジ報酬そのものを極端に大きくするか、マップ探索（Exploration）の要素を見直す必要があるかもしれない。
    - **追記**: 実験設定ミスによりStandard Envで実行されていたことが判明。Cycle 02/03の結果は無効（またはBaselineのバリエーション）として扱う。

### Cycle 04: Enhanced Environment Fix (実行中)

- **Job ID**: 32
- **実施日時**: 2025-12-07
- **目的**: 設定ミスを修正し、初めて有効な `EnhancedSecurityEnvironment` で学習を行う。
- **ハイパーパラメータ**:
    - `environment_type`: **enhanced** (Corrected)
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: 1.0
        - `exploration_weight`: 0.3
        - `diversity_weight`: 0.5
- **期待**:
    - 拡張報酬が正しく適用されるため、これまでとは明確に異なる挙動（カバレッジ向上、分散配置）が期待される。
- **結果**:
    - **Average Reward**: 12383
    - **Final Coverage**: 0.69 (Baseline Max: 0.67) - 微増
- **考察**:
    - `standard` 環境 (Cycle 03) と比較して、カバレッジが `0.67` -> `0.69` に向上した。
    - 劇的な変化ではないが、拡張報酬が機能し、カバレッジを押し上げていることは確認できた。
    - 次は、Coverage Weightを `2.0` に倍増させ、カバレッジへの選好をより明確にする実験 (Cycle 05) を行うべきである。

### Cycle 05: High Coverage Saturation (実行中)

- **Job ID**: 33
- **実施日時**: 2025-12-07
- **目的**: 拡張カバレッジ報酬の重みを倍増させ、カバレッジ性能の限界を探る。
- **ハイパーパラメータ**:
    - `environment_type`: **enhanced**
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: **2.0** (Increased from 1.0)
        - `exploration_weight`: 0.3
        - `diversity_weight`: 0.5
- **期待**:
    - 報酬最適化においてカバレッジの優先度が大幅に上がるため、Coverage > 0.75 を達成することが期待される。
- **結果**:
    - **Average Reward**: 12247
    - **Final Coverage**: 0.66 (Cycle 04: 0.69) - **低下**
- **考察**:
    - Coverage Weightを倍増させてもカバレッジは改善せず、むしろ悪化した。
    - 「カバレッジ報酬」は「新規マスを踏んだ瞬間」にしか発生しないスパース（疎）な報酬であり、これだけを強化してもエージェントはどう動けばいいか学習しにくい可能性がある。
    - カバレッジを上げるための直接的な行動である「探索（Exploration）」そのものを強化すべきではないか？
    - Cycle 06 では方針を転換し、**Exploration Weight** を大幅に強化する。

### Cycle 06: Exploration Focus (実行中)

- **Job ID**: 34
- **実施日時**: 2025-12-07
- **目的**: カバレッジ報酬の代わりに探索報酬を強化し、「未踏破エリアへの移動」を動機づけることで間接的にカバレッジを向上させる。
- **ハイパーパラメータ**:
    - `environment_type`: **enhanced**
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: **1.0** (Reverted to baseline)
        - `exploration_weight`: **1.0** (Increased from 0.3)
        - `diversity_weight`: 0.5
- **期待**:
    - エージェントが積極的に新しい場所を探すようになり、結果としてカバレッジ率が向上する。
- **結果**:
    - **Average Reward**: 12873 (最高値を更新)
    - **Final Coverage**: 0.67 (Cycle 05: 0.66, Cycle 04: 0.69)
- **考察**:
    - 探索報酬の強化により、エージェントは「動くこと」で多くの報酬を得るようになった（Avg Reward改善）。
    - しかし、最終カバレッジは `0.67` コースに戻ってしまい、Cycle 04 (0.69) に届かず。

### Cycle 07: Balanced Synergy (実行中)

- **Job ID**: 35
- **実施日時**: 2025-12-07
- **目的**: 探索報酬と多様性報酬を同時に強化し、エージェントが「活動的」かつ「分散的」に動くことでカバレッジの壁を突破する。
- **ハイパーパラメータ**:
    - `environment_type`: **enhanced**
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: 1.0
        - `exploration_weight`: **1.0** (High)
        - `diversity_weight`: **1.0** (Increased from 0.5)
- **期待**:
    - 分散配置が促され、重複探索が減少することで、同じ活動量でもより広い範囲をカバーできるはずである。
- **結果**:
    - **Average Reward**: 12953 (記録更新!)
    - **Final Coverage**: 0.66 (Cycle 04: 0.69, Cycle 06: 0.67) - 低下
- **考察**:
    - 報酬総額は最高を記録した。つまりエージェントは「最も効率よく稼ぐ」行動を見つけた。
    - しかしカバレッジは低下した。これは、カバレッジ（新規開拓）よりも、既存の探索・分散報酬を稼ぎ続ける方が（局所的に）有利だった可能性がある。
    - **結論**: カバレッジ最大化には「Cycle 04 (Cov 1.0, Exp 0.3, Div 0.5)」のバランスが今のところ最適。過度なExploration/Diversityは逆効果。

### Cycle 08: Threat Maintenance (実行中)

- **Job ID**: 36
- **実施日時**: 2025-12-07
- **目的**: 平均脅威度 (Average Threat Level) に対するペナルティ導入により、「事後除去」だけでなく「脅威抑制」行動を学習させる。
- **ハイパーパラメータ**:
    - `environment_type`: **enhanced**
    - `total_timesteps`: 100,000
    - **Reward Weights**:
        - `coverage_weight`: 1.0
        - `exploration_weight`: 0.5
        - `diversity_weight`: 0.5
        - **`threat_penalty_weight`: 50.0** (New)
- **期待**:
    - これまで評価対象外だった「平均脅威度」が低下する (抑制される) ことを期待する。
    - 副次的に、脅威の発生を予防するために広範囲を早期に巡回するようになり、カバレッジも向上する可能性がある。
- **結果**:
    - **Threat Level**: 0.6011 (Cycle 07: 0.6266) - 脅威度の低下を確認 (改善)
    - **Final Coverage**: **0.73** (Cycle 07: 0.66, Best: 0.69) - **大幅改善 (記録更新)**
    - **Reward**: 12763 (Cycle 07: 12953) - ペナルティ分だけ減少したが、健全な範囲。
- **考察**:
    - 「脅威度ペナルティ」が極めて有効に機能した。
    - 脅威度を低く保つためには、エージェントは「脅威が発生しそうな場所（未訪問エリアや時間が経過したエリア）」を先回りして巡回し続ける必要がある。
    - この「メンテナンス行動」が結果として、マップ全体をくまなくカバーする行動に繋がり、カバレッジ0.70の壁を突破した。
    - ユーザーのゴールである「環境全体の脅威度が常に低く、警備が行き渡っている」状態に最も近づいた。







### Cycle 09-C: Battery Pressure & Real Test (完了)

- **Job ID**: 39
- **実施日時**: 2025-12-08
- **目的**: バッテリー消費率を上げ、充電行動の強制によってパフォーマンスにどのような影響が出るかを検証する。将来的に「最適な充電ステーション位置」を分析するためのデータ収集も兼ねる。
- **ハイパーパラメータ**:
    - `battery_drain_rate`: **0.1** (Conventional: 0.001) - 非常に高い消費率。
    - `threat_penalty_weight`: 50.0 (Cycle 08 Best)
- **結果**:
    - **Final Coverage**: 0.60 (Cycle 08: 0.73) - **大幅低下**
    - **Threat Level**: 0.72 (Cycle 08: 0.60) - **悪化**
- **考察**:
    - バッテリー消費が激しすぎるため、ロボットは充電ステーションへの往復に時間の大半を費やしてしまった（ピストン輸送状態）。
    - その結果、警備活動（カバレッジ、脅威抑制）に割ける時間が減少し、パフォーマンスが大幅に低下した。
    - この結果は「バッテリー制約が厳しい場合、効率的な初期配置や充電戦略が不可欠である」ことを示唆している。
    - また、この過酷な条件下で記録されたエピソードログ（初期位置 vs 成績）は、次サイクルのヒートマップ分析において非常に価値が高い（強い選択圧がかかっているため）。

### Cycle 10-A: Heatmap Data Collection & Strategic Init (完了)

- **Job ID**: 45, 46
- **実施日時**: 2025-12-09
- **目的**:
    1.  本番ログ基盤の修正を確認し、ヒートマップ生成用のデータを収集する。
    2.  生成されたヒートマップを基に「戦略的初期配置 (Strategic Initialization)」を実装し、その効果を検証する。
- **ハイパーパラメータ (Job 46)**:
    - `strategic_init_mode`: **True** (New Feature)
    - `battery_drain_rate`: 0.001 (Standard)
    - `threat_penalty_weight`: 50.0
- **プロセス**:
    1.  Job 45 (100k steps) を実行し、ログを収集。
    2.  `scripts/generate_heatmap.py` で分析し、最適初期位置 `(17,14)`, `(5,9)` 等を特定。
    3.  Job 46 で `strategic_init_mode=True` を有効化して学習。
- **結果**:
    - **Average Reward**: -2861 (vs Baseline -4627) - **劇的改善**
    - **Threat Level**: 0.65 (vs Baseline 0.71) - 改善
    - **Final Coverage**: データ収集中 (Playbackでの目視では良好)
- **考察**:
    - 戦略的初期配置により、強化学習の「初期の探査効率」が大幅に向上した。
    - ランダム配置では「充電ステーションから遠い」「袋小路」などで無駄になるエピソードがあったが、最適位置（ステーションへのアクセスが良く、マップ全体に展開しやすい場所）から開始することで、学習の立ち上がりが早くなった。
    - これにより、バッテリー制約がある環境下でも安定して高いパフォーマンスを出せる基盤が整った。

---

## 次の方針 (Next Steps)

### Cycle 11: Multi-Agent Coordination
- **課題**: 現在のロボットは他者の行動を知る手段がなく、脅威度の変化で間接的に推測しているだけである。そのため、重複巡回（無駄足）が発生しやすい。
- **解決策**: 観測空間に **Visit History Map (訪問履歴マップ)** を追加する。
    - いわゆる「フェロモン」のように、「いつそこが訪問されたか」を可視化する。
    - 直近に訪問された場所 (値が高い) を避け、訪問から時間が経過した場所 (値が低い) へ向かう行動を学習させる。
- **期待**: 重複が減ることで実効的な探索範囲が広がり、カバレッジがさらに向上する (Target > 0.75)。
