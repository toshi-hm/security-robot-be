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
  save_frames: bool = Field(
    default=False,
    description="各ステップのフレームデータを保存してレスポンスへ含めるかどうか",
  )
  execution_id: str | None = Field(
    default=None,
    min_length=1,
    description="リアルタイム進捗配信用の実行ID（省略時はサーバーが自動生成）",
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
          "save_frames": True,
          "execution_id": "templ-exec-1234",
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


class TemplateAgentFrameData(BaseModel):
  """単一ステップのフレームデータ"""

  timestep: int = Field(..., ge=0, description="ステップ番号 (0-index)")
  robot_x: int = Field(..., ge=0, description="ロボットのX座標")
  robot_y: int = Field(..., ge=0, description="ロボットのY座標")
  robot_orientation: int = Field(..., ge=0, le=3, description="ロボットの向き (0=N,1=E,2=S,3=W)")
  action: int = Field(..., ge=0, le=3, description="実行したアクション")
  reward: float = Field(..., description="そのステップで得た報酬")
  battery_percentage: float = Field(..., ge=0.0, le=100.0, description="ステップ後のバッテリー残量")
  is_charging: bool = Field(..., description="充電中かどうか")
  coverage_map: list[list[int]] = Field(..., description="累積カバレッジマップ")
  timestamp: str = Field(..., description="ISO8601形式のタイムスタンプ")


class TemplateAgentEpisodePlayback(BaseModel):
  """単一エピソードのPlaybackデータ"""

  episode: int = Field(..., ge=1, description="エピソード番号")
  frames: list[TemplateAgentFrameData] = Field(..., description="ステップごとのフレームデータ")
  total_reward: float = Field(..., description="エピソード合計報酬")
  final_coverage: float = Field(..., ge=0.0, le=1.0, description="エピソード終了時のカバレッジ率")
  episode_length: int = Field(..., ge=0, description="ステップ数")


class TemplateAgentEnvironmentInfo(BaseModel):
  """環境全体の静的情報"""

  width: int = Field(..., ge=1, description="環境の幅")
  height: int = Field(..., ge=1, description="環境の高さ")
  threat_grid: list[list[float]] = Field(..., description="脅威度マップ")
  average_threat_level: float = Field(
    ...,
    ge=0.0,
    description="脅威度の平均値",
  )
  max_threat_level: float = Field(
    ...,
    ge=0.0,
    description="脅威度の最大値",
  )
  min_threat_level: float = Field(
    ...,
    ge=0.0,
    description="脅威度の最小値",
  )
  threat_histogram: list[int] = Field(
    ...,
    description="脅威度分布ヒストグラム（固定ビン: 0-0.2, ..., 0.8-1.0）",
  )
  high_threat_tiles: list[dict] = Field(
    default_factory=list,
    description="危険度の高いタイル座標（x, y, threat）上位5件",
  )
  obstacles: list[list[bool]] = Field(..., description="障害物マップ")
  charging_station: dict = Field(..., description="充電ステーション座標 (x, y)")
  suspicious_objects: list[dict] = Field(
    default_factory=list,
    description="検知された不審物情報のリスト",
  )


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
  execution_id: str = Field(
    ...,
    description="この実行を識別するID（WebSocket進捗通知と連携）",
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
  environment_info: TemplateAgentEnvironmentInfo = Field(
    ...,
    description="実行時の環境情報（脅威度・障害物等）",
  )
  episode_playbacks: list[TemplateAgentEpisodePlayback] = Field(
    ...,
    description="各エピソードのPlaybackデータ (save_frames=Falseのときは空)",
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "agent_type": "horizontal_scan",
          "agent_name": "HorizontalScanAgent",
          "execution_id": "templ-exec-1234",
          "environment": {"width": 10, "height": 10},
          "episodes": 10,
          "average_reward": 125.5,
          "std_reward": 15.2,
          "average_coverage": 0.85,
          "average_episode_length": 950.0,
          "average_patrol_count": 80.5,
          "average_min_battery": 45.0,
          "total_battery_deaths": 0,
          "environment_info": {
            "width": 10,
            "height": 10,
            "threat_grid": [[0.1, 0.2], [0.3, 0.4]],
            "average_threat_level": 0.25,
            "max_threat_level": 0.4,
            "min_threat_level": 0.1,
            "threat_histogram": [2, 1, 1, 0, 0],
            "high_threat_tiles": [{"x": 1, "y": 1, "threat": 0.4}],
            "obstacles": [[False, False], [True, False]],
            "charging_station": {"x": 5, "y": 5},
            "suspicious_objects": [{"x": 3, "y": 4, "spawn_time": 12}],
          },
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
          "episode_playbacks": [
            {
              "episode": 1,
              "total_reward": 120.0,
              "final_coverage": 0.82,
              "episode_length": 1000,
              "frames": [
                {
                  "timestep": 0,
                  "robot_x": 0,
                  "robot_y": 0,
                  "robot_orientation": 0,
                  "action": 0,
                  "reward": 0.5,
                  "battery_percentage": 100.0,
                  "is_charging": False,
                  "coverage_map": [[0, 0], [0, 0]],
                  "timestamp": "2025-11-18T14:30:00Z",
                }
              ],
            }
          ],
        }
    ]
    }
  }


class TemplateAgentExecutionInitResponse(BaseModel):
  """WebSocket進捗購読のための実行ID生成レスポンス"""

  execution_id: str = Field(..., description="サーバーが発行した実行ID")
  websocket_url: str = Field(..., description="進捗購読用WebSocketパス")


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
