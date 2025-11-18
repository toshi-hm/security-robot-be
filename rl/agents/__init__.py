"""
Template-based patrol agents for comparison with RL agents.

These agents follow predetermined patrol patterns and serve as baselines
for evaluating reinforcement learning approaches.
"""

from rl.agents.template_agents import (BaseTemplateAgent, HorizontalScanAgent,
                                       RandomWalkAgent, SpiralAgent,
                                       VerticalScanAgent)

__all__ = [
    "BaseTemplateAgent",
    "HorizontalScanAgent",
    "RandomWalkAgent",
    "SpiralAgent",
    "VerticalScanAgent",
]
