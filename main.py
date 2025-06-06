import json
import os
import re
from typing import List

import sentry_sdk
import torch

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from fastapi.openapi.utils import get_openapi

from config.config import settings
from utils.slack import send_slack_message
from routers import simulation, detect, chat, match, team

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
    "http://localhost:3000",
    "https://web.playus.o-r.kr"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Swagger에서 JWT Bearer 인증을 사용할 수 있도록 설정
bearer_scheme = HTTPBearer()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method.setdefault("security", []).append({"bearerAuth": []})
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


@app.exception_handler(Exception)
async def unicorn_exception_handler(request: Request, exc: Exception):
    print(exc)
    if settings.sentry_environment in ["prod", "dev"]:
        send_slack_message(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

app.include_router(simulation.router)
app.include_router(detect.router)
app.include_router(chat.router)
app.include_router(match.router)
app.include_router(team.router)
