from pydantic import BaseModel
from typing import List

class PlayerInput(BaseModel):
    id: int
    position: str

class SimulationRequest(BaseModel):
    home_team_name: str
    home_players: List[PlayerInput]
    away_team_name: str
    away_players: List[PlayerInput]

class SimulationResponse(BaseModel):
    prompt: str
    result: str

class Sentence(BaseModel):
    sentence: str

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str 