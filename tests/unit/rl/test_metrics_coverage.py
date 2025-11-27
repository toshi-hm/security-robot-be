import pytest

from rl.environments.enhanced_env import EnhancedSecurityEnvironment
from rl.environments.security_env import SecurityEnvironment


def test_security_env_metrics():
  """基本的な指標の存在と初期値を検証"""
  env = SecurityEnvironment(width=10, height=10)
  obs, info = env.reset()

  # 初期状態の検証
  assert "coverage_ratio" in info
  assert "exploration_score" in info
  assert info["coverage_ratio"] == 1.0 / 100.0  # 開始位置の1セル
  assert info["exploration_score"] == 1.0

  # 1ステップ実行して指標が更新されることを確認
  # (実際の移動成功は環境のテストで保証されるべき)
  obs, reward, term, trunc, info = env.step(0)

  assert "coverage_ratio" in info
  assert "exploration_score" in info
  assert 0.0 <= info["coverage_ratio"] <= 1.0
  assert info["exploration_score"] >= 1.0


def test_security_env_metrics_update_after_movement():
  """移動後に訪問セル数が増加することを検証"""
  env = SecurityEnvironment(width=5, height=5, count=0)  # 障害物なし
  env.reset()

  initial_score = env._get_info()["exploration_score"]

  # 4方向に移動試行(いずれかは成功するはず)
  for _ in range(4):
    obs, _, _, _, info = env.step(0)  # 前進
    if info["exploration_score"] > initial_score:
      # 移動成功を確認
      assert info["coverage_ratio"] > 1.0 / 25.0
      return
    env.step(2)  # 右回転

  pytest.fail("4方向すべてで移動できませんでした(環境生成の問題)")


def test_enhanced_env_metrics_compatibility():
  env = EnhancedSecurityEnvironment(width=10, height=10)
  obs, info = env.reset()

  assert "coverage_ratio" in info
  assert "exploration_score" in info
  # Enhanced env might have different logic, but base metrics should be consistent
  assert info["coverage_ratio"] == 1.0 / 100.0
  assert info["exploration_score"] == 1.0

  # Check if visited_cells is working as set
  assert isinstance(env.visited_cells, set)
  assert (env.robot_x, env.robot_y) in env.visited_cells
