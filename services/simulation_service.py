from simulation.simulate import simulate_game_rag

def simulate_game(req, user):
    home_players = [player.dict() for player in req.home_players]
    away_players = [player.dict() for player in req.away_players]
    result = simulate_game_rag(
        req.home_team_name,
        home_players,
        req.away_team_name,
        away_players
    )
    return result 