# config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 데이터베이스 설정
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_database: str
    db_charset: str = "utf8mb4"
    
    # 기타 설정
    hf_token: str
    
    model_config = { 
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }

# 전역 설정 인스턴스
settings = Settings()
