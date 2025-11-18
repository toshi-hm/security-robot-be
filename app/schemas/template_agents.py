"""テンプレートエージェント実行API用スキーマ"""

from enum import Enum

from pydantic import BaseModel, Field


class TemplateAgentType(str, Enum):
  """利用可能なテンプレートエージェント種別"""

  HORIZONTAL_SCAN = "horizontal_scan"
  VERTICAL_SCAN = "vertical_scan"
  SPIRAL = "spiral"
  RANDOM_WALK = "random_walk"


class TemplateAgentExecuteRequest(BaseModel):
  """テンプレートエージェント実行リクエストスキーマ"""

  agent_type: TemplateAgentType = Field(
    ...,
    description="実行するテンプレートエージェントの種別",
  )
  width: int = Field(
    default=10,
    ge=3,
    le=100,
    description="環境グリッドの幅",
  )
  height: int = Field(
    default=10,
    ge=3,
    le=100,
    description="環境グリッドの高さ",
  )
  episodes: int = Field(
    default=10,
    ge=1,
    le=100,
    description="実行するエピソード数",
  )
  max_steps: int = Field(
    default=1000,
    ge=10,
    le=10000,
    description="エピソードあたりの最大ステップ数",
  )
  seed: int | None = Field(
    default=None,
    description="再現性のための乱数シード",
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "agent_type": "horizontal_scan",
          "width": 10,
          "height": 10,
          "episodes": 10,
          "max_steps": 1000,
          "seed": 42,
        }
      ]
    }
  }


class TemplateAgentEpisodeMetrics(BaseModel):
  """単一エピソードのメトリクス"""

  episode: int = Field(..., description="エピソード番号")
  total_reward: float = Field(..., description="エピソードの合計報酬")
  episode_length: int = Field(..., description="エピソードのステップ数")
  coverage_ratio: float = Field(..., ge=0.0, description="巡回済みセルの割合")
  patrol_count: int = Field(..., ge=0, description="パトロールアクション回数")
  move_count: int = Field(..., ge=0, description="前進アクション回数")
  turn_count: int = Field(..., ge=0, description="回転アクション回数")
  min_battery: float = Field(..., ge=0.0, le=100.0, description="最小バッテリー残量（%）")
  battery_deaths: int = Field(..., ge=0, description="バッテリー切れ回数")
  charging_events: int = Field(..., ge=0, description="充電イベント回数")


class TemplateAgentExecuteResponse(BaseModel):
  """テンプレートエージェント実行レスポンススキーマ"""

  agent_type: TemplateAgentType = Field(
    ...,
    description="実行されたテンプレートエージェントの種別",
  )
  agent_name: str = Field(
    ...,
    description="エージェントのクラス名",
  )
  environment: dict = Field(
    ...,
    description="環境設定",
  )
  episodes: int = Field(
    ...,
    description="実行されたエピソード数",
  )
  average_reward: float = Field(
    ...,
    description="エピソード間の平均合計報酬",
  )
  std_reward: float = Field(
    ...,
    ge=0.0,
    description="報酬の標準偏差",
  )
  average_coverage: float = Field(
    ...,
    ge=0.0,
    description="平均カバレッジ率",
  )
  average_episode_length: float = Field(
    ...,
    gt=0,
    description="平均エピソード長",
  )
  average_patrol_count: float = Field(
    ...,
    ge=0.0,
    description="平均パトロールアクション回数",
  )
  average_min_battery: float = Field(
    ...,
    ge=0.0,
    le=100.0,
    description="平均最小バッテリー残量（%）",
  )
  total_battery_deaths: int = Field(
    ...,
    ge=0,
    description="全エピソードでのバッテリー切れ合計回数",
  )
  episode_metrics: list[TemplateAgentEpisodeMetrics] = Field(
    ...,
    description="各エピソードの詳細メトリクス",
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "agent_type": "horizontal_scan",
          "agent_name": "HorizontalScanAgent",
          "environment": {"width": 10, "height": 10},
          "episodes": 10,
          "average_reward": 125.5,
          "std_reward": 15.2,
          "average_coverage": 0.85,
          "average_episode_length": 950.0,
          "average_patrol_count": 80.5,
          "average_min_battery": 45.0,
          "total_battery_deaths": 0,
          "episode_metrics": [
            {
              "episode": 1,
              "total_reward": 120.0,
              "episode_length": 1000,
              "coverage_ratio": 0.82,
              "patrol_count": 78,
              "move_count": 750,
              "turn_count": 172,
              "min_battery": 42.5,
              "battery_deaths": 0,
              "charging_events": 3,
            }
          ],
        }
      ]
    }
  }


class TemplateAgentCompareRequest(BaseModel):
  """複数テンプレートエージェント比較リクエストスキーマ"""

  agent_types: list[TemplateAgentType] = Field(
    default=[
      TemplateAgentType.HORIZONTAL_SCAN,
      TemplateAgentType.VERTICAL_SCAN,
      TemplateAgentType.SPIRAL,
    ],
    min_length=1,
    max_length=4,
    description="比較するエージェント種別のリスト",
  )
  width: int = Field(
    default=10,
    ge=3,
    le=100,
    description="環境グリッドの幅",
  )
  height: int = Field(
    default=10,
    ge=3,
    le=100,
    description="環境グリッドの高さ",
  )
  episodes: int = Field(
    default=10,
    ge=1,
    le=100,
    description="エージェントごとのエピソード数",
  )
  max_steps: int = Field(
    default=1000,
    ge=10,
    le=10000,
    description="エピソードあたりの最大ステップ数",
  )
  seed: int | None = Field(
    default=None,
    description="再現性のための乱数シード",
  )


class TemplateAgentComparisonSummary(BaseModel):
  """比較における単一エージェントの性能サマリー"""

  agent_type: TemplateAgentType = Field(..., description="エージェント種別")
  agent_name: str = Field(..., description="エージェントのクラス名")
  rank: int = Field(..., ge=1, description="平均報酬によるランク")
  average_reward: float = Field(..., description="平均合計報酬")
  std_reward: float = Field(..., ge=0.0, description="報酬の標準偏差")
  average_coverage: float = Field(..., ge=0.0, description="平均カバレッジ率")
  average_episode_length: float = Field(..., gt=0, description="平均エピソード長")
  average_patrol_count: float = Field(..., ge=0.0, description="平均パトロール回数")
  average_min_battery: float = Field(..., ge=0.0, le=100.0, description="平均最小バッテリー残量")
  total_battery_deaths: int = Field(..., ge=0, description="バッテリー切れ合計回数")


class TemplateAgentCompareResponse(BaseModel):
  """複数テンプレートエージェント比較レスポンススキーマ"""

  environment: dict = Field(..., description="環境設定")
  episodes: int = Field(..., description="エージェントごとのエピソード数")
  max_steps: int = Field(..., description="エピソードあたりの最大ステップ数")
  results: list[TemplateAgentComparisonSummary] = Field(
    ...,
    description="ランク順にソートされた比較結果",
  )
  best_agent: str = Field(..., description="最高性能エージェントの名前")
  worst_agent: str = Field(..., description="最低性能エージェントの名前")
  performance_gap: float = Field(
    ...,
    description="最高と最低の平均報酬の差",
  )
