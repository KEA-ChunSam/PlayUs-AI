from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from utils.jwt import get_current_user
from api.match import get_match_info_by_date, get_match_preview_info

router = APIRouter()

@router.get("/matches")
def get_matches(date: str = Query(..., description="경기 날짜(YYYY-MM-DD)"), user: dict = Depends(get_current_user)):
    result = get_match_info_by_date(date)
    return JSONResponse(content=result)

@router.get("/match/{game_id}")
async def get_match_preview(game_id: str, user: dict = Depends(get_current_user)):
    result = get_match_preview_info(game_id)
    return JSONResponse(content=result) 