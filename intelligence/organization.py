"""Shared organization taxonomy for content selection, generation, and QA."""

CONNECTED_CAR_TEAM = "커넥티드카사업팀"
AI_INFO_TEAM = "AI인포사업팀"
FMS_SOLUTION_TEAM = "FMS솔루션사업팀"
COMMON_TEAM = "공통"

ORGANIZATION_TEAMS = (
    CONNECTED_CAR_TEAM,
    AI_INFO_TEAM,
    FMS_SOLUTION_TEAM,
)

ALL_TEAM_TAGS = (*ORGANIZATION_TEAMS, COMMON_TEAM)

TEAM_DESCRIPTIONS = {
    CONNECTED_CAR_TEAM: "통신 사업, DCM 개발, DCM 운영",
    AI_INFO_TEAM: "차량 인포테인먼트 및 AI 기반 차량 경험 사업",
    FMS_SOLUTION_TEAM: "초정밀측위, 차량 관제 및 운영 솔루션 사업",
    COMMON_TEAM: "세 조직에 공통으로 영향을 주는 모빌리티 시장 변화",
}

TEAM_ALIASES = {
    CONNECTED_CAR_TEAM: ("커넥티드카사업팀", "커넥티드카", "connected car", "dcm"),
    AI_INFO_TEAM: ("ai인포사업팀", "ai인포", "인포테인먼트", "infotainment", "ivi"),
    FMS_SOLUTION_TEAM: ("fms솔루션사업팀", "fms솔루션", "fms", "초정밀측위", "관제"),
    COMMON_TEAM: ("전사 공통", "조직 공통", "공통", "전체 조직"),
}


def normalize_related_teams(text: str) -> list[str]:
    """Map free-form team labels to canonical names in display order."""
    normalized = text.lower()
    return [
        team
        for team in ALL_TEAM_TAGS
        if any(alias in normalized for alias in TEAM_ALIASES[team])
    ]
