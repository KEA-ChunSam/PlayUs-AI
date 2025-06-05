import base64
import jwt
import requests

from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Header
from config.config import settings

# JWT 토큰 검증 함수 (만료/유효성)
def verify_token(token: str):
    try:
        key = base64.b64decode(settings.jwt_secret)
        payload = jwt.decode(token, key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Expired token") # 만료된 토큰
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None # 잘못된 토큰

# 외부 유저 서비스에 블랙리스트 체크 요청
def is_token_blacklisted(token: str) -> bool:
    url = f"{settings.user_service_url}/user/api/token/blacklist-check"
    try:
        resp = requests.post(url, json={"token": token}, timeout=2, verify=False)
        if resp.status_code == 200:
            return resp.json().get("blacklisted", False)
    except Exception:
        pass
    return True  # 실패 시 안전하게 막음

# 헤더에서 토큰 추출
def get_token_from_header(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token in Authorization header")
    token = auth_header.split(" ", 1)[1]
    return token

# FastAPI Dependency: 토큰 검증 및 블랙리스트 체크
def get_current_user(request: Request):
    token = get_token_from_header(request)
    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Blacklisted token")
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
