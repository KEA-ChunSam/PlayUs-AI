import json
import os
import re
from typing import List

import sentry_sdk
import torch

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.match import get_match_info_by_date, get_match_preview_info
from chat.chat_bot import ask_question
from config.config import settings
from simulation.simulate import simulate_game_rag
from utils.model import detect_profanity
from utils.slack import send_slack_message


class UnicornException(Exception):
    def __init__(self, name: str):
        self.name = name


torch.cuda.empty_cache()  
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
os.environ["TORCH_USE_CUDA_DSA"] = "1"

if settings.sentry_environment in ["prod", "dev"]:
    sentry_sdk.init(
        dsn=settings.sentry_repository_dsn,
        environment=settings.sentry_environment,
        send_default_pii=True,
    )

app = FastAPI()

origins = [
    "http://localhost:3000",  # 로컬 React 앱
    # "https://yourfrontend.com"  # 배포 후 실제 주소도 추가 가능
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,              # 허용할 origin 목록
    allow_credentials=True,
    allow_methods=["*"],                # GET, POST 등 모두 허용
    allow_headers=["*"],                # 모든 헤더 허용
)


class PlayerInput(BaseModel):
    id: int
    position: str  # "타자" 또는 "투수"


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


@app.exception_handler(Exception)
async def unicorn_exception_handler(request: Request, exc: Exception):
    print(exc)

    if settings.sentry_environment in ["prod", "dev"]:
        send_slack_message(exc)

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


@app.post("/simulate", response_model=SimulationResponse)
async def simulate(req: SimulationRequest):
    home_players = [player.dict() for player in req.home_players]
    away_players = [player.dict() for player in req.away_players]

    result = simulate_game_rag(
        req.home_team_name,
        home_players,
        req.away_team_name,
        away_players
    )
    return result


@app.post("/detect")
async def detect(req: Sentence):
    sentence = req.sentence

    # 포괄적인 욕설 탐지 정규표현식
    profanity_pattern = r'[시씨씪슈쓔쉬쉽쒸쓉](?:[0-9]*|[0-9]+ *)[바발벌빠빡빨뻘파팔펄]|[섊좆좇졷좄좃좉졽썅춍봊]|[ㅈ조][0-9]*까|ㅅㅣㅂㅏㄹ?|ㅂ[0-9]*ㅅ|[ㅄᄲᇪᄺᄡᄣᄦᇠ]|[ㅅㅆᄴ][0-9]*[ㄲㅅㅆᄴㅂ]|[존좉좇][0-9 ]*나|[자보][0-9]+지|보빨|[봊봋봇봈볻봁봍] *[빨이]|[후훚훐훛훋훗훘훟훝훑][장앙]|[엠앰]창|애[미비]|애자|[가-탏탑-힣]색기|(?:[샊샛세쉐쉑쉨쉒객갞갟갯갰갴겍겎겏겤곅곆곇곗곘곜걕걖걗걧걨걬] *[끼키퀴])|새 *[키퀴]|[병븅][0-9]*[신딱딲]|미친[가-닣닥-힣]|[믿밑]힌|[염옘][0-9]*병|[샊샛샜샠섹섺셋셌셐셱솃솄솈섁섂섓섔섘]기|[섹섺섻쎅쎆쎇쎽쎾쎿섁섂섃썍썎썏][스쓰]|[지야][0-9]*랄|니[애에]미|갈[0-9]*보[^가-힣]|[뻐뻑뻒뻙뻨][0-9]*[뀨큐킹낑)|꼬[0-9]*추|곧[0-9]*휴|[가-힣]슬아치|자[0-9]*박꼼|빨통|[사싸](?:이코|가지|[0-9]*까시)|육[0-9]*시[랄럴]|육[0-9]*실[알얼할헐]|즐[^가-힣]|찌[0-9]*(?:질이|랭이)|찐[0-9]*따|찐[0-9]*찌버거|창[녀놈]|[가-힣]{2,}충[^가-힣]|[가-힣]{2,}츙|부녀자|화냥년|환[양향]년|호[0-9]*[구모]|조[선센][징]|조센|[쪼쪽쪾](?:[발빨]이|[바빠]리)|盧|무현|찌끄[레래]기|(?:하악){2,}|하[앍앜]|[낭당랑앙항남담람암함][ ]?[가-힣]+[띠찌]|느[금급]마|文在|在寅|(?<=[^\n])[家哥]|속냐|[tT]l[qQ]kf|Wls|[ㅂ]신|[ㅅ]발|[ㅈ]밥'

    # 정규표현식으로 욕설 탐지
    matches = re.findall(profanity_pattern, sentence, re.IGNORECASE)

    # 매칭된 욕설이 있으면 바로 반환
    if matches:
        # 중복 제거
        found_words = list(set(matches))
        return {"isCurse": True, "words": found_words}

    # 정규표현식으로도 못 잡은 경우만 LLM 사용 (매우 보수적으로 탐지)
    prompt = f"""
    문장: "{sentence}"
    100% 확실한 욕설만 탐지하세요. 의심스러우면 false.
    {{"isCurse": false, "words": []}}
    """

    result = detect_profanity(prompt)

    # 백틱 제거
    result = re.sub(r'```\s*', '', result)

    # JSON 추출
    json_match = re.search(r'\{[^}]*\}', result)
    if json_match:
        try:
            json_str = json_match.group()
            parsed = json.loads(json_str)
            clean_result = {
                "isCurse": parsed.get("isCurse", False),
                "words": parsed.get("words", [])
            }
        except:
            clean_result = {"isCurse": False, "words": []}
    else:
        clean_result = {"isCurse": False, "words": []}

    return clean_result


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    answer = ask_question(req.question)
    return ChatResponse(answer=answer)

@app.get("/matches")
def get_matches(date: str = Query(..., description="경기 날짜(YYYY-MM-DD)")):
    result = get_match_info_by_date(date)
    return JSONResponse(content=result)

@app.get("/match/{match-id}")
def get_match_preview(game_id: str = Query(..., description="네이버 경기 ID (예: 20250601HHNC02025)")):
    result = get_match_preview_info(game_id)
    return JSONResponse(content=result)
