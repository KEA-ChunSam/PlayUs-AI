from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from utils.jwt import get_current_user
from api.match import get_match_info_by_date, get_match_preview_info
from datetime import datetime
from fastapi import HTTPException

router = APIRouter()

@router.get("/matches")
def get_matches(
    date: str = Query(..., description="경기 날짜(YYYY-MM-DD)"),
    user: dict = Depends(get_current_user),
):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
        )
    result = get_match_info_by_date(date)
    return JSONResponse(content=result)
    
@router.get("/match/{game_id}")
def get_match_preview(game_id: str, user: dict = Depends(get_current_user)):
    result = get_match_preview_info(game_id)
    return JSONResponse(content=result)