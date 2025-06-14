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
        with connection, connection.cursor() as cursor:
            sql = "SELECT * FROM hitter_info WHERE id = %s"
            cursor.execute(sql, (player_id,))
            return cursor.fetchone()
    except pymysql.Error as e:
        logging.error("타자 정보 조회 실패: %s", e)
        return None

def get_pitcher_info_by_id(player_id: int):
    connection = get_connection()
    if not connection:
        return None
        
    try:
        with connection, connection.cursor() as cursor:
            sql = "SELECT * FROM pitcher_info WHERE id = %s"
            cursor.execute(sql, (player_id,))
            return cursor.fetchone()
    except pymysql.Error as e:
        logging.error("투수 정보 조회 실패: %s", e)
        return None

def get_stadium_by_team_name(team_name: str):
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection, connection.cursor() as cursor:
            sql = "SELECT stadium FROM team WHERE team_name = %s"
            cursor.execute(sql, (team_name,))
            row = cursor.fetchone()
            return row['stadium'] if row else None
    except pymysql.Error as e:
        logging.error("구장 정보 조회 실패: %s", e)
        return None

def get_team_id_by_name(team_name: str):
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection, connection.cursor() as cursor:
            sql = "SELECT id FROM team WHERE team_name = %s"
            cursor.execute(sql, (team_name,))
            row = cursor.fetchone()
            return row['id'] if row else None
    except pymysql.Error as e:
        logging.error("팀 조회 실패: %s", e)
        return None

def get_match_id_by_teams_and_date(home_team_id: int, away_team_id: int, match_date: str):
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection, connection.cursor() as cursor:
            sql = """
            SELECT id FROM matches
            WHERE home_team_id = %s AND away_team_id = %s AND DATE(match_date) = DATE(%s)
            """
            cursor.execute(sql, (home_team_id, away_team_id, match_date))
            row = cursor.fetchone()
            return row['id'] if row else None
    except pymysql.Error as e:
        logging.error("경기 조회 실패: %s", e)
        return None

def get_pitchers_by_team_id(team_id: int):
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection, connection.cursor() as cursor:
            sql = """
            SELECT id, name, position, back_num FROM pitcher_info
            WHERE team_id = %s
            """
            cursor.execute(sql, (team_id,))
            rows = cursor.fetchall()
            return rows
    except pymysql.Error as e:
        logging.error("투수 선수 정보 조회 실패: %s", e)
        return None

def get_hitters_by_team_id(team_id: int):
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection, connection.cursor() as cursor:
            sql = """
            SELECT id, name, position, back_num FROM hitter_info
            WHERE team_id = %s
            """
            cursor.execute(sql, (team_id,))
            rows = cursor.fetchall()
            return rows
    except pymysql.Error as e:
        logging.error("타자 선수 정보 조회 실패: %s", e)
        return None

