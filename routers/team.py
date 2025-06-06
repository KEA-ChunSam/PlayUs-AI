from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from utils.jwt import get_current_user
from api.player import get_team_players

router = APIRouter()

@router.get("/team_players")
def team_players(team_id: int = Query(..., description="팀 ID"), user: dict = Depends(get_current_user)):
    try:
        result = get_team_players(team_id)
        if result is None:
            raise HTTPException(status_code=404, detail="팀 정보를 찾을 수 없습니다.")
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e 