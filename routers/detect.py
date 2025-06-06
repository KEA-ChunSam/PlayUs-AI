from fastapi import APIRouter, Depends
from utils.jwt import get_current_user
from services.detect_service import detect_profanity_service
from models import Sentence

router = APIRouter()

@router.post("/detect")
async def detect(req: Sentence, user: dict = Depends(get_current_user)):
    return detect_profanity_service(req.sentence) 