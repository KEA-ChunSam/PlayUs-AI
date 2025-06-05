from fastapi import APIRouter, Depends
from services.simulation_service import simulate_game
from utils.jwt import get_current_user
from models import PlayerInput, SimulationRequest, SimulationResponse

router = APIRouter()

@router.post("/simulate", response_model=SimulationResponse)
async def simulate(req: SimulationRequest, user: dict = Depends(get_current_user)):
    return simulate_game(req, user) 