import requests
from typing import List, Dict, Any
from config.config import settings
from utils.db import get_stadium_by_team_name, get_team_id_by_name, get_match_id_by_teams_and_date

base_url = settings.kbo_base_url

def get_match_info_by_date(date: str) -> List[Dict[str, Any]]:
    params = {
        "fields": "basic,schedule,baseball",
        "upperCategoryId": "kbaseball",
        "fromDate": date,
        "toDate": date,
        "size": 500
    }
    
    response = requests.get(base_url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        games = data.get('result', {}).get('games', [])
        return [
            _process_game_info(game)
            for game in games
            if game.get('categoryName') == 'KBO리그'
        ]
    
    response.raise_for_status()
    
def _process_game_info(game: Dict[str, Any]) -> Dict[str, Any]:
    # 게임 정보를 처리하여 필요한 형태로 변환
    home_team_name = game.get('homeTeamName')
    away_team_name = game.get('awayTeamName')
    game_date_time = game.get('gameDateTime')
    
    # 데이터베이스에서 추가 정보 조회
    stadium = get_stadium_by_team_name(home_team_name)
    home_team_id = get_team_id_by_name(home_team_name)
    away_team_id = get_team_id_by_name(away_team_name)
    
    # None 값 체크 및 경기 ID 조회
    match_id = None
    if home_team_id and away_team_id and game_date_time:
        match_id = get_match_id_by_teams_and_date(
            home_team_id, away_team_id, game_date_time
        )
    
    return {
        'match_id': match_id,
        'game_id': game.get('gameId'),
        'game_date_time': game_date_time,
        'stadium': stadium,
        'home_team_id': home_team_id,
        'home_team_name': home_team_name,
        'home_team_score': game.get('homeTeamScore'),
        'away_team_id': away_team_id,
        'away_team_name': away_team_name,
        'away_team_score': game.get('awayTeamScore'),
        'status_code': game.get('statusCode'),
        'winner': game.get('winner'),
    }

def get_match_preview_info(game_id):
    url = f"{base_url}/{game_id}/preview"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        preview = data.get("result", {}).get("previewData", {})

        # 최근 경기 전적(승/무/패) 계산 함수
        def get_recent_record(games):
            win = sum(1 for g in games if g.get("result") == "승")
            draw = sum(1 for g in games if g.get("result") == "무")
            lose = sum(1 for g in games if g.get("result") == "패")
            return {"win": win, "draw": draw, "lose": lose}

        # 홈팀
        home_recent_games = preview.get("homeTeamPreviousGames", [])
        home_recent_record = get_recent_record(home_recent_games)
        home_standings = preview.get("homeStandings", {})
        home_recent_ba = home_standings.get("hra")
        home_recent_era = home_standings.get("era")
        home_team_name = home_standings.get("name")
        home_team_id = get_team_id_by_name(home_team_name)
        home_starter = preview.get("homeStarter", {}).get("playerInfo", {}).get("name")

        # 어웨이팀
        away_recent_games = preview.get("awayTeamPreviousGames", [])
        away_recent_record = get_recent_record(away_recent_games)
        away_standings = preview.get("awayStandings", {})
        away_recent_ba = away_standings.get("hra")
        away_recent_era = away_standings.get("era")
        away_team_name = away_standings.get("name")
        away_team_id = get_team_id_by_name(away_team_name)
        away_starter = preview.get("awayStarter", {}).get("playerInfo", {}).get("name")

        # 상대 전적
        season_vs = preview.get("seasonVsResult", {})
        season_vs_result = {
            "home_win": season_vs.get("hw"),
            "home_draw": season_vs.get("hd"),
            "home_lose": season_vs.get("hl"),
            "away_win": season_vs.get("aw"),
            "away_draw": season_vs.get("ad"),
            "away_lose": season_vs.get("al"),
        }

        return {
            "home": {
                "team_id": home_team_id,
                "team_name": home_team_name,
                "recent_record": home_recent_record,
                "recent_batting_average": home_recent_ba,
                "recent_era": home_recent_era,
                "starter": home_starter,
            },
            "away": {
                "team_id": away_team_id,
                "team_name": away_team_name,
                "recent_record": away_recent_record,
                "recent_batting_average": away_recent_ba,
                "recent_era": away_recent_era,
                "starter": away_starter,
            },
            "season_vs_result": season_vs_result
        }
    else:
        response.raise_for_status()
