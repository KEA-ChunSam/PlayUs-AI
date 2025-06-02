from utils.db import get_pitchers_by_team_id, get_hitters_by_team_id

def get_team_players(team_id: int):

    pitchers = get_pitchers_by_team_id(team_id) or []
    hitters = get_hitters_by_team_id(team_id) or []

    pitcher_ids = {p['id'] for p in pitchers}
    filtered_hitters = [h for h in hitters if h['id'] not in pitcher_ids]

    return {
        'pitchers': pitchers,
        'hitters': filtered_hitters
    }
