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




