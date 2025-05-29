# db.py
import pymysql
import logging
from sqlalchemy import create_engine
from sqlalchemy import text
from config.config import settings

# 환경변수 기반 연결 설정
def get_db_config():
    return {
        'host': settings.db_host,
        'port': settings.db_port,
        'user': settings.db_user,
        'password': settings.db_password,
        'database': settings.db_database,
        'charset': settings.db_charset
    }

def get_sqlalchemy_engine():
    config = get_db_config()
    return create_engine(
        f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}?charset={config['charset']}"
    )

def run_sql_query(query: str) -> list[dict]:
    config = get_db_config()
    conn = pymysql.connect(
        host=config['host'],
        port=config['port'],
        user=config['user'],
        password=config['password'],
        db=config['database'],
        charset=config['charset'],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        logging.error(f"SQL 쿼리 실행 오류: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_connection():
    """연결 풀 방식으로 개선"""
    try:
        config = get_db_config()
        return pymysql.connect(
            **config,
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        logging.error(f"DB 연결 생성 실패: {e}")
        return None

def get_hitter_info_by_id(player_id: int):
    connection = get_connection()
    if not connection:
        return None
        
    try:
        with connection:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM hitter_info WHERE id = %s"
                cursor.execute(sql, (player_id,))
                return cursor.fetchone()
    except Exception as e:
        logging.error(f"타자 정보 조회 실패: {e}")
        return None

def get_pitcher_info_by_id(player_id: int):
    connection = get_connection()
    if not connection:
        return None
        
    try:
        with connection:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM pitcher_info WHERE id = %s"
                cursor.execute(sql, (player_id,))
                return cursor.fetchone()
    except Exception as e:
        logging.error(f"투수 정보 조회 실패: {e}")
        return None
