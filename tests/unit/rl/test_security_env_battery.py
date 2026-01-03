"""Security environment battery system unit tests."""

import random

import numpy as np
import pytest

from rl.environments.security_env import SecurityEnvironment


@pytest.fixture
def battery_env():
  """バッテリーシステム有効化環境のフィクスチャ"""
  return SecurityEnvironment(width=10, height=10)


def test_battery_initialization(battery_env):
  """バッテリーが100%で初期化されることを確認"""
  obs, info = battery_env.reset()

  assert battery_env.battery_levels[0] == 100.0
  assert battery_env.is_charging_list[0] is False
  assert "battery_percentage" in info
  assert info["battery_percentage"] == 100.0


def test_battery_drain_rate(battery_env):
  """バッテリーが正しく消費されることを確認(1000ステップで1%)"""
  battery_env.reset()

  # 充電ステーションから離れる
  battery_env.robot_positions[0] = (0, 0)

  initial_battery = battery_env.battery_levels[0]

  # 1000ステップ実行
  for _ in range(1000):
    _obs, _reward, done, _truncated, _info = battery_env.step([0])
    if done:
      break

  # 1%消費されているはず(誤差0.1以内)
  assert abs(battery_env.battery_levels[0] - (initial_battery - 1.0)) < 0.1


def test_battery_charging_on_station(battery_env):
  """充電ステーション上でバッテリーが充電されることを確認"""
  obs, info = battery_env.reset()

  # リセット直後はロボットが充電ステーション上にいることを確認
  assert battery_env.robot_positions[0] in battery_env.charging_stations

  # バッテリーを50%に設定
  battery_env.battery_levels[0] = 50.0

  # 10ステップ実行（巡回アクションで充電ステーション上に留まる）
  for _ in range(10):
    _obs, _reward, _done, _truncated, _info = battery_env.step([3])

  # 10%充電されているはず
  assert abs(battery_env.battery_levels[0] - 60.0) < 0.1
  assert battery_env.is_charging_list[0] is True


def test_battery_depletion_penalty(battery_env):
  """バッテリー切れ時に特大ペナルティが付与されることを確認"""
  battery_env.reset()

  # バッテリーを強制的に0%に設定
  battery_env.battery_levels[0] = 0.001  # ほぼ0

  # 1ステップ実行してバッテリー切れを発生させる
  battery_env.robot_positions[0] = (0, 0)
  _obs, reward, done, _truncated, _info = battery_env.step([0])

  # バッテリー切れによる特大ペナルティ
  assert reward <= -100.0
  assert done is True


def test_observation_space_includes_battery(battery_env):
  """観測空間が5チャンネルであることを確認"""
  obs, _info = battery_env.reset()

  # 観測空間は(10, 10, 6) [Single Robot: 4 shared + 2 specific]
  assert battery_env.observation_space.shape == (10, 10, 6)
  assert len(obs) == 10
  assert len(obs[0]) == 10
  assert len(obs[0][0]) == 6


def test_charging_station_in_observation(battery_env):
  """観測空間に充電ステーション位置が含まれることを確認"""
  obs, _info = battery_env.reset()

  station_x, station_y = battery_env.charging_stations[0]

  # チャンネル3に充電ステーションが記録されている (Shifted from 2)
  assert obs[station_y][station_x][3] == 1.0

  # チャンネル5にバッテリー残量（正規化済み）が記録されている (Shifted from 4)
  assert obs[station_y][station_x][5] == 1.0  # 100% = 1.0


def test_battery_in_info_dict(battery_env):
  """info辞書にバッテリー情報が含まれることを確認"""
  _obs, info = battery_env.reset()

  assert "battery_percentage" in info
  assert "is_charging" in info
  # assert "distance_to_charging_station" in info # Removed in multi-agent
  # assert "charging_station_position" in info # Removed in multi-agent

  assert "battery_levels" in info
  assert "robot_positions" in info

  assert 0.0 <= info["battery_percentage"] <= 100.0
  assert isinstance(info["is_charging"], bool)
  # assert isinstance(info["distance_to_charging_station"], int | float) # Removed in multi-agent
  # assert isinstance(info["charging_station_position"], tuple) # Removed in multi-agent


def test_charging_stops_when_moving_away(battery_env):
  """充電ステーションから離れると充電が停止することを確認"""
  obs, info = battery_env.reset()

  # リセット直後はロボットが充電ステーション上にいることを確認
  assert battery_env.robot_positions[0] in battery_env.charging_stations

  # バッテリーを50%に設定
  battery_env.battery_levels[0] = 50.0

  # 充電ステーション上で充電開始
  _obs, _reward, _done, _truncated, _info = battery_env.step([3])
  assert battery_env.is_charging_list[0] is True

  # 充電ステーション周囲の障害物をクリア
  station_x, station_y = battery_env.charging_stations[0]
  for dx in [-1, 0, 1]:
    for dy in [-1, 0, 1]:
      x = station_x + dx
      y = station_y + dy
      if 0 <= x < battery_env.width and 0 <= y < battery_env.height:
        battery_env.obstacles[x][y] = False

  # 前進して充電ステーションから離れる
  _obs, _reward, _done, _truncated, _info = battery_env.step([0])

  # 充電ステーションから離れたか、障害物で移動できなかった場合は回転して移動
  if battery_env.robot_positions[0] == (station_x, station_y):
    _obs, _reward, _done, _truncated, _info = battery_env.step([1])  # 回転
    _obs, _reward, _done, _truncated, _info = battery_env.step([0])  # 前進

  # 充電ステーションから離れていれば充電が停止
  if battery_env.robot_positions[0] != (station_x, station_y):
    assert battery_env.is_charging_list[0] is False


def test_partial_charging_strategy(battery_env):
  """部分充電が可能であることを確認（100%まで充電不要）"""
  obs, info = battery_env.reset()

  # リセット直後はロボットが充電ステーション上にいることを確認
  assert battery_env.robot_positions[0] in battery_env.charging_stations

  # バッテリーを30%に設定
  battery_env.battery_levels[0] = 30.0

  # 50ステップ充電（100%まで充電しない）
  for _ in range(50):
    _obs, _reward, _done, _truncated, _info = battery_env.step([3])

  # 80%まで充電されている（100%ではない）
  assert abs(battery_env.battery_levels[0] - 80.0) < 0.1
  assert battery_env.is_charging_list[0] is True
  assert battery_env.battery_levels[0] < 100.0

  # さらに10ステップ充電
  for _ in range(10):
    _obs, _reward, _done, _truncated, _info = battery_env.step([3])

  # 90%まで充電されている（依然として100%ではない）
  assert abs(battery_env.battery_levels[0] - 90.0) < 0.1
  assert battery_env.is_charging_list[0] is True
  assert battery_env.battery_levels[0] < 100.0

  # 部分充電で充電を中断できることを確認済み
  # (100%まで充電する必要がない)


@pytest.mark.integration
def test_battery_full_episode(battery_env):
  """バッテリーシステムを含む完全なエピソードテスト"""
  _obs, info = battery_env.reset()

  total_reward = 0.0
  steps = 0
  charging_events = 0
  max_steps = 10000

  while steps < max_steps:
    # ランダムアクション
    action = random.randint(0, 3)

    _obs, reward, done, _truncated, info = battery_env.step([action])
    total_reward += reward
    steps += 1

    if info["is_charging"]:
      charging_events += 1

    if done:
      break

  # エピソード完了
  assert steps > 0
  # バッテリー切れか、最大ステップ到達
  assert done or steps >= max_steps


@pytest.mark.parametrize(
  "initial_battery,expected_range",
  [
    (100.0, (99.0, 100.0)),
    (50.0, (49.0, 50.0)),
    (10.0, (9.0, 10.0)),
  ],
)
def test_battery_initialization_with_different_values(initial_battery, expected_range):
  """異なる初期バッテリー値でのテスト"""
  env = SecurityEnvironment(width=8, height=8)
  env.reset()

  # 初期バッテリーを設定
  env.battery_levels[0] = initial_battery

  # 充電ステーションから離れて1ステップ実行
  env.robot_positions[0] = (0, 0)
  _obs, _reward, _done, _truncated, info = env.step(np.array([0]))

  # バッテリーが微減している
  assert expected_range[0] <= info["battery_percentage"] <= expected_range[1]


def test_render_includes_battery_info(battery_env, capsys):
  """render()がバッテリー情報と充電ステーション位置を表示することを確認"""
  battery_env.reset()

  # バッテリーを減らしてから充電中状態をテスト
  battery_env.battery_levels[0] = 50.0

  # 充電ステーション上で1ステップ実行（充電が開始される）
  battery_env.step(np.array([3]))  # patrol action on charging station

  # 充電中状態でレンダリング
  battery_env.render()
  captured = capsys.readouterr()

  # バッテリー残量が表示されている
  assert "Battery:" in captured.out
  assert "[CHARGING]" in captured.out

  # 充電ステーション位置が表示されている
  assert "Charging stations:" in captured.out
  assert str(battery_env.charging_stations) in captured.out

  # 充電ステーションから離れる
  battery_env.robot_positions[0] = (0, 0)
  battery_env.is_charging_list[0] = False

  # 再度レンダリング（充電中でない）
  battery_env.render()
  captured = capsys.readouterr()

  # バッテリー残量が表示されているが、充電中表示はない
  assert "Battery:" in captured.out
  # バッテリー残量が表示されているが、充電中表示はない
  assert "Battery:" in captured.out
  assert "[CHARGING]" not in captured.out


def test_visit_history_channel(battery_env):
  """訪問履歴チャンネル(Ch 2)の動作確認"""
  obs, info = battery_env.reset()

  # Force safe position
  battery_env.robot_positions[0] = (5, 5)
  # Clear obstacles around
  for dx in range(-1, 2):
    for dy in range(-1, 2):
      battery_env.obstacles[5 + dy][5 + dx] = False

  # Manually update history for new forced position
  # Reset everything to -1000
  battery_env.visit_history_map = battery_env._build_grid(-1000.0)
  # Mark current pos
  battery_env.visit_history_map[5][5] = 0.0

  obs = battery_env._get_observation()

  # 初期状態: ロボットの初期位置は訪問済み (1.0)
  # それ以外は未訪問 (0.0)
  rx, ry = 5, 5
  assert obs[ry, rx, 2] == 1.0

  # Check a different spot is 0.0
  if ry + 2 < battery_env.height:
    assert obs[ry + 2, rx, 2] == 0.0

  # Step 1: Stay or move. Let's patrol (stay) to mark current spot
  obs, _, _, _, _ = battery_env.step([3])

  # Now (rx, ry) should be marked as visited at time_step=1
  # _get_observation uses current time_step (1).
  # last_patrolled was updated to 1.
  # diff = 0 -> val = 1.0
  assert obs[ry, rx, 2] == 1.0

  # Other places 0.0
  # Other places 0.0 (Vision range is 2, so +1 and +2 are visited)
  if ry + 3 < battery_env.height:
    assert obs[ry + 3, rx, 2] == 0.0

  # Step 2: Move away (Action 0 = North = y-1)
  # From (5,5) to (5,4)
  obs, _, _, _, _ = battery_env.step([0])

  # Previous spot (5,5) should decay
  # diff = 2 - 1 = 1
  # val = 1.0 - 1/500 = 0.998
  assert abs(obs[ry, rx, 2] - (1.0 - 1.0 / 500.0)) < 1e-6

  # New spot (5,4) should be 1.0 (Recently visited)
  new_ry = 4
  assert obs[new_ry, rx, 2] == 1.0


# ============================================================
# 動的エピソードステップ上限のテスト
# ============================================================


def test_dynamic_max_steps_default_small_env():
  """小さい環境では従来互換の1000ステップがデフォルトになることを確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # 10x10 = 100 cells, 100 * 10 = 1000 → 1000
  assert calculate_dynamic_max_steps(10, 10) == 1000

  # 5x5 = 25 cells, 25 * 10 = 250 < 1000 → 1000
  assert calculate_dynamic_max_steps(5, 5) == 1000

  # 9x9 = 81 cells, 81 * 10 = 810 < 1000 → 1000
  assert calculate_dynamic_max_steps(9, 9) == 1000


def test_dynamic_max_steps_large_env():
  """大きい環境では動的に計算されたステップ上限が使われることを確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # 20x20 = 400 cells, 400 * 10 = 4000 > 1000 → 4000
  assert calculate_dynamic_max_steps(20, 20) == 4000

  # 30x30 = 900 cells, 900 * 10 = 9000 > 1000 → 9000
  assert calculate_dynamic_max_steps(30, 30) == 9000

  # 15x15 = 225 cells, 225 * 10 = 2250 > 1000 → 2250
  assert calculate_dynamic_max_steps(15, 15) == 2250


def test_dynamic_max_steps_custom_coefficient():
  """カスタム係数が正しく適用されることを確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # coefficient=2: 20x20 = 400 * 2 = 800 < 1000 → 1000
  assert calculate_dynamic_max_steps(20, 20, coefficient=2) == 1000

  # coefficient=6: 20x20 = 400 * 6 = 2400 > 1000 → 2400
  assert calculate_dynamic_max_steps(20, 20, coefficient=6) == 2400


def test_environment_uses_dynamic_max_steps():
  """環境が動的に計算されたステップ上限を使用することを確認"""
  # 小さい環境: デフォルト1000
  small_env = SecurityEnvironment(width=10, height=10)
  assert small_env.max_episode_steps == 1000

  # 大きい環境: 動的計算 (20x20 * 10 = 4000)
  large_env = SecurityEnvironment(width=20, height=20)
  assert large_env.max_episode_steps == 4000

  # 明示的に指定: 500
  custom_env = SecurityEnvironment(width=20, height=20, max_episode_steps=500)
  assert custom_env.max_episode_steps == 500


def test_episode_terminates_at_dynamic_max_steps():
  """エピソードが動的上限で終了することを確認"""
  # 小さい環境でステップ上限を100に明示設定
  env = SecurityEnvironment(width=5, height=5, max_episode_steps=100)
  env.reset()

  # 充電ステーションから離れる（バッテリー切れを避けるため短いエピソード）
  env.robot_positions[0] = (0, 0)

  terminated = False
  steps = 0
  for _ in range(200):  # 100を超えるステップを試行
    _obs, _reward, terminated, _truncated, _info = env.step(np.array([3]))  # patrol
    steps += 1
    if terminated:
      break

  # 100ステップで終了するはず
  assert terminated
  assert steps == 100


def test_dynamic_max_steps_rectangular_env():
  """長方形環境での動的ステップ上限を確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # 10x40 = 400 cells, 400 * 10 = 4000 > 1000 → 4000
  assert calculate_dynamic_max_steps(10, 40) == 4000

  # 50x8 = 400 cells, 400 * 10 = 4000 > 1000 → 4000
  assert calculate_dynamic_max_steps(50, 8) == 4000

  # 非対称環境でも正しく計算される
  env = SecurityEnvironment(width=30, height=10)
  # 30 * 10 * 10 = 3000 > 1000 → 3000
  assert env.max_episode_steps == 3000
