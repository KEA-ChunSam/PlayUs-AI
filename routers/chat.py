from fastapi import APIRouter, Depends
from utils.jwt import get_current_user
from services.chat_service import ask_question_service
from models import ChatRequest, ChatResponse

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, user: dict = Depends(get_current_user)):
    answer = ask_question_service(req.question)
    return ChatResponse(answer=answer) 