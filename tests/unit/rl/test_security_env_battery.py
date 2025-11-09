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

    assert battery_env.battery_percentage == 100.0
    assert battery_env.is_charging is False
    assert "battery_percentage" in info
    assert info["battery_percentage"] == 100.0


def test_battery_drain_rate(battery_env):
    """バッテリーが正しく消費されることを確認(1000ステップで1%)"""
    battery_env.reset()

    # 充電ステーションから離れる
    battery_env.robot_x = 0
    battery_env.robot_y = 0

    initial_battery = battery_env.battery_percentage

    # 1000ステップ実行
    for _ in range(1000):
        _obs, _reward, done, _truncated, _info = battery_env.step(0)
        if done:
            break

    # 1%消費されているはず(誤差0.1以内)
    assert abs(battery_env.battery_percentage - (initial_battery - 1.0)) < 0.1


def test_battery_charging_on_station(battery_env):
    """充電ステーション上でバッテリーが充電されることを確認"""
    battery_env.reset()

    # バッテリーを50%に設定
    battery_env.battery_percentage = 50.0

    # 充電ステーション上に配置（既にリセット時に配置されている）
    assert battery_env.robot_x == battery_env.charging_station_x
    assert battery_env.robot_y == battery_env.charging_station_y

    # 10ステップ実行（巡回アクションで充電ステーション上に留まる）
    for _ in range(10):
        _obs, _reward, _done, _truncated, _info = battery_env.step(3)

    # 10%充電されているはず
    assert abs(battery_env.battery_percentage - 60.0) < 0.1
    assert battery_env.is_charging is True


def test_battery_depletion_penalty(battery_env):
    """バッテリー切れ時に特大ペナルティが付与されることを確認"""
    battery_env.reset()

    # バッテリーを強制的に0%に設定
    battery_env.battery_percentage = 0.001  # ほぼ0

    # 1ステップ実行してバッテリー切れを発生させる
    battery_env.robot_x = 0
    battery_env.robot_y = 0
    _obs, reward, done, _truncated, _info = battery_env.step(0)

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

    # チャンネル3に充電ステーションが記録されている
    assert obs[station_x][station_y][3] == 1.0

    # チャンネル4にバッテリー残量（正規化済み）が記録されている
    assert obs[0][0][4] == 1.0  # 100% = 1.0


def test_battery_in_info_dict(battery_env):
    """info辞書にバッテリー情報が含まれることを確認"""
    _obs, info = battery_env.reset()

    assert "battery_percentage" in info
    assert "is_charging" in info
    assert "distance_to_charging_station" in info
    assert "charging_station_position" in info

    assert 0.0 <= info["battery_percentage"] <= 100.0
    assert isinstance(info["is_charging"], bool)
    assert isinstance(info["distance_to_charging_station"], (int, float))
    assert isinstance(info["charging_station_position"], tuple)


def test_charging_stops_when_moving_away(battery_env):
    """充電ステーションから離れると充電が停止することを確認"""
    battery_env.reset()

    # バッテリーを50%に設定
    battery_env.battery_percentage = 50.0

    # 充電ステーション上で充電開始
    _obs, _reward, _done, _truncated, _info = battery_env.step(3)
    assert battery_env.is_charging is True

    # 充電ステーションから移動
    battery_env.robot_x = 0
    battery_env.robot_y = 0

    _obs, _reward, _done, _truncated, _info = battery_env.step(0)

    # 充電が停止
    assert battery_env.is_charging is False


def test_partial_charging_strategy(battery_env):
    """部分充電が可能であることを確認（100%まで充電不要）"""
    battery_env.reset()

    # バッテリーを30%に設定
    battery_env.battery_percentage = 30.0

    # 50ステップ充電（100%まで充電しない）
    for _ in range(50):
        _obs, _reward, _done, _truncated, _info = battery_env.step(3)

    # 80%まで充電されている（100%ではない）
    assert abs(battery_env.battery_percentage - 80.0) < 0.1
    assert battery_env.is_charging is True
    assert battery_env.battery_percentage < 100.0

    # さらに10ステップ充電
    for _ in range(10):
        _obs, _reward, _done, _truncated, _info = battery_env.step(3)

    # 90%まで充電されている（依然として100%ではない）
    assert abs(battery_env.battery_percentage - 90.0) < 0.1
    assert battery_env.is_charging is True
    assert battery_env.battery_percentage < 100.0

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

        _obs, reward, done, _truncated, info = battery_env.step(action)
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
    env.battery_percentage = initial_battery

    # 充電ステーションから離れて1ステップ実行
    env.robot_x = 0
    env.robot_y = 0
    _obs, _reward, _done, _truncated, info = env.step(0)

    # バッテリーが微減している
    assert expected_range[0] <= info["battery_percentage"] <= expected_range[1]
