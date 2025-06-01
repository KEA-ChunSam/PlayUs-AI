import requests
from utils.db import get_stadium_by_team_name, get_team_id_by_name, get_match_id_by_teams_and_date

def get_match_info_by_date(date: str):
    url = f"https://api-gw.sports.naver.com/schedule/games?fields=basic%2Cschedule%2Cbaseball&upperCategoryId=kbaseball&fromDate={date}&toDate={date}&size=500"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        games = data.get('result', {}).get('games', [])
        result = []
        for game in games:
            if game.get('categoryName') == 'KBO리그':
                game_date_time =  game.get('gameDateTime')
                home_team_name = game.get('homeTeamName')
                away_team_name = game.get('awayTeamName')
                stadium = get_stadium_by_team_name(home_team_name)
                home_team_id = get_team_id_by_name(home_team_name)
                away_team_id = get_team_id_by_name(away_team_name)
                match_id = get_match_id_by_teams_and_date(home_team_id, away_team_id, game_date_time)
                naver_game_id = game.get('gameId')
                home_team_score = game.get('homeTeamScore')
                away_team_score = game.get('awayTeamScore')
                status_code = game.get('statusCode')
                winner = game.get('winner')

                result.append({
                    'match_id': match_id,
                    'naver_game_id': naver_game_id,
                    'game_date_time': game_date_time,
                    'stadium': stadium,
                    'home_team_id': home_team_id,
                    'home_team_name': home_team_name,
                    'home_team_score': home_team_score,
                    'away_team_id': away_team_id,
                    'away_team_name': away_team_name,
                    'away_team_score': away_team_score,
                    'status_code': status_code,
                    'winner': winner,
                })
        return result
    else:
        response.raise_for_status()
