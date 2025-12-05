# GPU最適化と高度な強化学習機能 設計書

## 1. 概要
本ドキュメントは、GPUリソースを最大限に活用し、学習の高速化とモデルの高度化（CNNポリシー）を実現するための設計を定義します。

## 2. 目的
- **GPU使用率の向上**: 現在の単一環境・MLPモデルではGPU負荷が低く、CPUオーバーヘッドがボトルネックとなっているため、並列環境（Vectorized Environments）を導入してバッチサイズを増やし、GPUスループットを向上させます。
- **モデル表現力の向上**: グリッドマップを画像として扱う Convolutional Neural Network (CNN) ポリシーを導入し、より複雑なパターン認識を可能にします。

## 3. 並列環境 (Vectorized Environments)設計

### 3.1 Backend実装 (`app/core/training/ppo_service.py`)

Stable-Baselines3 の `make_vec_env` と `SubprocVecEnv` を使用して、マルチプロセスでの環境実行を実装します。

- **入力パラメータ**:
  - `num_envs` (int): 並列環境数 (デフォルト: 1, 推奨: コア数に合わせて 8-16)
- **環境生成ロジック**:
  ```python
  if num_envs > 1:
      # SubprocVecEnv: 別プロセスで環境を実行（GIL回避、マルチコア活用）
      env = make_vec_env(lambda: self.create_environment(config), n_envs=num_envs, vec_env_cls=SubprocVecEnv)
  else:
      # DummyVecEnv: 同一プロセスで実行（デバッグ用、低オーバーヘッド）
      env = DummyVecEnv([lambda: self.create_environment(config)])
  ```
- **注意点**:
  - `SubprocVecEnv` はメモリ消費が増加します（プロセス数分だけ環境が複製される）。
  - `SecurityEnvironment` インスタンスが Pickle 可能であることを確認済みです。

### 3.2 APIスキーマ変更 (`app/schemas/training.py`)

`TrainingSessionCreate` および `TrainingSessionResponse` を拡張せず、既存の柔軟な `config` JSONカラムを活用しますが、検証ロジックで以下のキーをサポートします。

- `config["num_envs"]`: `int` (1 <= n <= 32)
- `config["policy_type"]`: `str` ("MlpPolicy" | "CnnPolicy")

## 4. CNNポリシー設計

### 4.1 概要
現在の `MlpPolicy` (全結合層) は、グリッド情報をフラットなベクトルとして扱いますが、`CnnPolicy` は2次元の畳み込み層を使用し、空間的な構造（壁の配置、隣接関係）をより効率的に学習します。

### 4.2 実装方針
`PPO` クラスの初期化時に `policy` 引数を動的に切り替えます。

```python
policy_type = config.get("policy_type", "MlpPolicy")
model = PPO(policy=policy_type, ...)
```

- **MlpPolicy**: 従来通り。軽量、CPUでも高速。
- **CnnPolicy**: 新規。GPU計算リソースを大量に消費するが、複雑なマップでの性能向上が期待される。

## 5. Frontend設計 (`security-robot-fe`)

### 5.1 トレーニング設定フォーム (`TrainingForm.vue`)
「詳細設定 (Advanced Settings)」セクションを追加し、以下の項目を設定可能にします。

1.  **並列環境数 (Parallel Environments)**
    - UI: スライダー または 数値入力
    - 範囲: 1 〜 32 (デフォルト: 1)
    - 説明: "並列数を増やすと学習速度が向上しますが、メモリ消費が増えます。"

2.  **ポリシーモデル (Policy Model)**
    - UI: ラジオボタン または セレクトボックス
    - 選択肢:
        - `MlpPolicy` (Standard / Fast)
        - `CnnPolicy` (Advanced / GPU Optimized)

## 6. 検証計画

### 6.1 性能比較
以下の条件で学習を実行し、FPS (Frames Per Second) と GPU使用率 (`nvidia-smi`) を比較します。

| ケース | 環境数 | ポリシー | 期待されるFPS | GPU負荷 |
|:---|:---:|:---:|:---:|:---:|
| Baseline | 1 | MLP | ~500 (CPU bound) | 低 |
| Parallel | 16 | MLP | > 1000 | 中 |
| CNN | 16 | CNN | (モデル依存) | 高 |

### 6.2 リソース監視
- `htop`: CPUコア使用率が均等に分散することを確認 (SubprocVecEnv)
- `nvidia-smi`: Volatile GPU-Util が上昇することを確認
