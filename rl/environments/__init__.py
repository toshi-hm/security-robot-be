"""Environment registry exposing available simulation definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable

from .enhanced_env import EnhancedSecurityEnvironment
from .security_env import SecurityEnvironment


EnvironmentFactory = Callable[..., SecurityEnvironment]


@dataclass(frozen=True, slots=True)
class EnvironmentSpec:
    """Registry entry describing an environment implementation."""

    id: str
    name: str
    description: str
    factory: EnvironmentFactory
    default_config: Dict[str, Any] = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    observation_channels: list[str] = field(default_factory=list)
    action_space: Dict[str, Any] = field(default_factory=dict)

    def create(self, **overrides: Any) -> SecurityEnvironment:
        config = {**self.default_config, **overrides}
        return self.factory(**config)


_REGISTRY: Dict[str, EnvironmentSpec] = {
    "base": EnvironmentSpec(
        id="base",
        name="Security Patrol Environment",
        description="基本的な脅威検知と巡回パトロールを学習するグリッド環境",
        factory=SecurityEnvironment,
        default_config={"width": 20, "height": 20, "robot_vision_range": 2},
        features=[
            "脅威度の時間推移",
            "ランダムな不審物生成",
            "障害物を含む巡回経路",
        ],
        observation_channels=["threat_levels", "obstacles", "robot_heading"],
        action_space={
            "type": "discrete",
            "actions": ["forward", "turn_left", "turn_right", "guard"],
        },
    ),
    "enhanced": EnvironmentSpec(
        id="enhanced",
        name="Enhanced Security Patrol Environment",
        description="探索・カバー率・多様性を強化した改良版の巡回環境",
        factory=EnhancedSecurityEnvironment,
        default_config={
            "width": 20,
            "height": 20,
            "robot_vision_range": 2,
            "coverage_weight": 1.0,
            "exploration_weight": 2.0,
            "diversity_weight": 1.5,
        },
        features=[
            "セル訪問状況の追跡",
            "探索・多様性重視の報酬設計",
            "カバー率の履歴トラッキング",
        ],
        observation_channels=["threat_levels", "obstacles", "robot_heading"],
        action_space={
            "type": "discrete",
            "actions": ["forward", "turn_left", "turn_right", "guard"],
        },
    ),
}


def available_environments() -> Iterable[EnvironmentSpec]:
    return _REGISTRY.values()


def get_environment_spec(environment_id: str) -> EnvironmentSpec:
    try:
        return _REGISTRY[environment_id]
    except KeyError as exc:  # pragma: no cover - trivial error handling
        raise KeyError(f"Unknown environment id: {environment_id}") from exc


__all__ = [
    "EnvironmentSpec",
    "available_environments",
    "get_environment_spec",
    "SecurityEnvironment",
    "EnhancedSecurityEnvironment",
]

