"""テンプレートエージェント実行・比較APIエンドポイント"""

from app.schemas.template_agents import (
    TemplateAgentCompareRequest,
    TemplateAgentCompareResponse,
    TemplateAgentExecuteRequest,
    TemplateAgentExecuteResponse,
    TemplateAgentType,
)
from app.services.template_agent_service import (
    compare_template_agents,
    execute_template_agent,
)
from fastapi import APIRouter

router = APIRouter(prefix="/template-agents", tags=["template-agents"])


@router.get("/types", response_model=list[dict])
def list_agent_types() -> list[dict]:
    """
    利用可能なテンプレートエージェント種別一覧を取得

    各エージェント種別の名前と説明を含むリストを返します。
    """
    return [
        {
            "type": TemplateAgentType.HORIZONTAL_SCAN.value,
            "name": "HorizontalScanAgent",
            "description": "水平方向に行ごとジグザグスキャン",
        },
        {
            "type": TemplateAgentType.VERTICAL_SCAN.value,
            "name": "VerticalScanAgent",
            "description": "垂直方向に列ごとジグザグスキャン",
        },
        {
            "type": TemplateAgentType.SPIRAL.value,
            "name": "SpiralAgent",
            "description": "外側から中心へ時計回りに渦巻きスキャン",
        },
        {
            "type": TemplateAgentType.RANDOM_WALK.value,
            "name": "RandomWalkAgent",
            "description": "ランダムウォーク（比較用ベースライン）",
        },
    ]


@router.post("/execute", response_model=TemplateAgentExecuteResponse)
def execute_agent(request: TemplateAgentExecuteRequest) -> TemplateAgentExecuteResponse:
    """
    単一のテンプレートエージェントを実行してパフォーマンスメトリクスを取得

    指定されたテンプレートエージェントをセキュリティ環境で実行し、
    指定されたエピソード数分の詳細なパフォーマンスメトリクスを返します。

    エージェントは事前定義された巡回パターンに従い、カバレッジ率、
    バッテリー管理、報酬などのメトリクスが追跡されます。
    """
    return execute_template_agent(request)


@router.post("/compare", response_model=TemplateAgentCompareResponse)
def compare_agents(request: TemplateAgentCompareRequest) -> TemplateAgentCompareResponse:
    """
    複数のテンプレートエージェントを同一環境で比較

    同じ環境設定で複数のテンプレートエージェントを評価し、
    パフォーマンスのランキング付き比較結果を返します。

    結果は平均報酬の降順でソートされ、最高性能のエージェントが1位になります。
    """
    return compare_template_agents(request)
