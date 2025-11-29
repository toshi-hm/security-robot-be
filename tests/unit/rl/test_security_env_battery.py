"""Security environment battery system unit tests."""

import random

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
  assert battery_env.robot_positions[0][0] == battery_env.charging_station_x
  assert battery_env.robot_positions[0][1] == battery_env.charging_station_y

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

  # 観測空間は(10, 10, 5)
  assert battery_env.observation_space.shape == (10, 10, 5)
  assert len(obs) == 10
  assert len(obs[0]) == 10
  assert len(obs[0][0]) == 5


def test_charging_station_in_observation(battery_env):
  """観測空間に充電ステーション位置が含まれることを確認"""
  obs, _info = battery_env.reset()

  station_x = battery_env.charging_station_x
  station_y = battery_env.charging_station_y

  # チャンネル2に充電ステーションが記録されている
  assert obs[station_y][station_x][2] == 1.0

  # チャンネル4にバッテリー残量（正規化済み）が記録されている
  assert obs[station_y][station_x][4] == 1.0  # 100% = 1.0


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
  assert battery_env.robot_positions[0][0] == battery_env.charging_station_x
  assert battery_env.robot_positions[0][1] == battery_env.charging_station_y

  # バッテリーを50%に設定
  battery_env.battery_levels[0] = 50.0

  # 充電ステーション上で充電開始
  _obs, _reward, _done, _truncated, _info = battery_env.step([3])
  assert battery_env.is_charging_list[0] is True

  # 充電ステーション周囲の障害物をクリア
  station_x = battery_env.charging_station_x
  station_y = battery_env.charging_station_y
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
  assert battery_env.robot_positions[0][0] == battery_env.charging_station_x
  assert battery_env.robot_positions[0][1] == battery_env.charging_station_y

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
  _obs, _reward, _done, _truncated, info = env.step([0])

  # バッテリーが微減している
  assert expected_range[0] <= info["battery_percentage"] <= expected_range[1]


def test_render_includes_battery_info(battery_env, capsys):
  """render()がバッテリー情報と充電ステーション位置を表示することを確認"""
  battery_env.reset()

  # バッテリーを減らしてから充電中状態をテスト
  battery_env.battery_levels[0] = 50.0

  # 充電ステーション上で1ステップ実行（充電が開始される）
  battery_env.step([3])  # patrol action on charging station

  # 充電中状態でレンダリング
  battery_env.render()
  captured = capsys.readouterr()

  # バッテリー残量が表示されている
  assert "Battery:" in captured.out
  assert "[CHARGING]" in captured.out

  # 充電ステーション位置が表示されている
  assert "Charging station:" in captured.out
  assert f"({battery_env.charging_station_x}, {battery_env.charging_station_y})" in captured.out

  # 充電ステーションから離れる
  battery_env.robot_positions[0] = (0, 0)
  battery_env.is_charging_list[0] = False

  # 再度レンダリング（充電中でない）
  battery_env.render()
  captured = capsys.readouterr()

  # バッテリー残量が表示されているが、充電中表示はない
  assert "Battery:" in captured.out
  assert "[CHARGING]" not in captured.out


# ============================================================
# 動的エピソードステップ上限のテスト
# ============================================================


def test_dynamic_max_steps_default_small_env():
  """小さい環境では従来互換の1000ステップがデフォルトになることを確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # 10x10 = 100 cells, 100 * 4 = 400 < 1000 → 1000
  assert calculate_dynamic_max_steps(10, 10) == 1000

  # 5x5 = 25 cells, 25 * 4 = 100 < 1000 → 1000
  assert calculate_dynamic_max_steps(5, 5) == 1000

  # 15x15 = 225 cells, 225 * 4 = 900 < 1000 → 1000
  assert calculate_dynamic_max_steps(15, 15) == 1000


def test_dynamic_max_steps_large_env():
  """大きい環境では動的に計算されたステップ上限が使われることを確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # 20x20 = 400 cells, 400 * 4 = 1600 > 1000 → 1600
  assert calculate_dynamic_max_steps(20, 20) == 1600

  # 30x30 = 900 cells, 900 * 4 = 3600 > 1000 → 3600
  assert calculate_dynamic_max_steps(30, 30) == 3600

  # 16x16 = 256 cells, 256 * 4 = 1024 > 1000 → 1024
  assert calculate_dynamic_max_steps(16, 16) == 1024


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

  # 大きい環境: 動的計算 (20x20 * 4 = 1600)
  large_env = SecurityEnvironment(width=20, height=20)
  assert large_env.max_episode_steps == 1600

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
    _obs, _reward, terminated, _truncated, _info = env.step([3])  # patrol
    steps += 1
    if terminated:
      break

  # 100ステップで終了するはず
  assert terminated
  assert steps == 100


def test_dynamic_max_steps_rectangular_env():
  """長方形環境での動的ステップ上限を確認"""
  from rl.environments.security_env import calculate_dynamic_max_steps

  # 10x40 = 400 cells, 400 * 4 = 1600 > 1000 → 1600
  assert calculate_dynamic_max_steps(10, 40) == 1600

  # 50x8 = 400 cells, 400 * 4 = 1600 > 1000 → 1600
  assert calculate_dynamic_max_steps(50, 8) == 1600

  # 非対称環境でも正しく計算される
  env = SecurityEnvironment(width=30, height=10)
  # 30 * 10 * 4 = 1200 > 1000 → 1200
  assert env.max_episode_steps == 1200
