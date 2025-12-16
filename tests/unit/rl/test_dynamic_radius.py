from rl.environments.security_env import SecurityEnvironment


class TestDynamicPatrolRadius:
  def test_low_threat_extended_radius(self):
    """Test that radius extends to 3 when average threat is low (<0.2)."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    # Ensure low threat (reset sets it to 0 initially, but let's be sure)
    env.threat_levels = [[0.0 for _ in range(10)] for _ in range(10)]

    # Place robot at (5, 5)
    env.robot_positions = [(5, 5)]

    # Place a threat at distance 3 (e.g., 5+3=8, 5)
    # With default radius 2, this wouldn't be cleared.
    # With radius 3, it should be.
    env.threat_levels[5][8] = 0.5

    # Action 3: Patrol
    env.step([3])

    # Check if threat at (8, 5) is cleared
    assert env.threat_levels[5][8] == 0.0, (
      "Threat at distance 3 should be cleared in Low Threat mode"
    )

    # Check logs
    assert any("Radius 3" in log or "R3" in log for log in env.last_patrol_info)

  def test_high_threat_normal_radius(self):
    """Test that radius stays normal (2) when average threat is high (>0.2)."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    # Set high threat everywhere to force avg > 0.2
    env.threat_levels = [[0.5 for _ in range(10)] for _ in range(10)]

    # Place robot at (5, 5)
    env.robot_positions = [(5, 5)]

    # Place a threat at distance 3 (8, 5)
    # Should NOT be cleared (Radius 2)
    env.threat_levels[5][8] = 0.9  # Make it distinct

    # Action 3: Patrol
    env.step([3])

    # Check if threat at (8, 5) is still there
    # Note: step() increments threat by 0.01, so 0.9 -> 0.91
    assert env.threat_levels[5][8] >= 0.9, (
      "Threat at distance 3 should NOT be cleared in High Threat mode"
    )

    # Check logs
    assert any("Radius 2" in log or "R2" in log for log in env.last_patrol_info)
