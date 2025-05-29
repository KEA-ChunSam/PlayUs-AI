import re
import logging
from utils.model import text_gen_pipeline
from langchain_huggingface import HuggingFacePipeline
from utils.db import get_sqlalchemy_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 1. DB 엔진 및 LLM 래핑
engine = get_sqlalchemy_engine()
llm = HuggingFacePipeline(pipeline=text_gen_pipeline)

COLUMN_DESCRIPTIONS = """
테이블 및 컬럼 설명:
- hitter_info : 타자 기록 정보
    - id : 선수 고유번호,
    - name : 선수 이름,
    - teamID : team 테이블을 참조하는 아이디,
    - avg : 타율,
    - G : 경기 수,
    - PA : 타석,
    - AB : 타수,
    - R : 득점,
    - H : 안타,
    - 2B : 2루타,
    - 3B : 3루타,
    - HR : 홈런,
    - RBI : 타점,
    - SAC : 희생번트,
    - SF : 희생플라이,
    - season : 년도(시즌),

- pitcher_info : 투수 기록 정보
    - id : 선수 고유번호,
    - name : 선수 이름,
    - teamID : team 테이블을 참조하는 아이디,
    - ERA : 평균 자책점,
    - G : 경기 수,
    - W : 승리 수,
    - L : 패배 수,
    - HLD : 홀드,
    - WPCT : 승률,
    - IP : 이닝,
    - H : 피안타,
    - HR : 피홈런,
    - BB : 볼넷,
    - HBP : 사구,
    - SO : 삼진,
    - R : 실점,
    - ER : 자책점,
    - WHIP : 이닝당 출루허용률,
    - season : 년도(시즌),

- matches : 경기 일정 정보
    - id : 경기 고유번호,
    - home_team_id : 홈 팀 고유번호,
    - away_team_id : 원정 팀 고유번호,
    - match_date : 경기 날짜,
    - home_score : 홈팀 점수,
    - away_score : 원정팀 점수,
    - start_time : 경기 시작 시간

- team : 팀 정보
    - id : 팀 고유번호,
    - team_name : 팀 이름,
    - stadium : 팀 구장
"""


# 2. 질문 → SQL 쿼리만 생성 (LLM에 쿼리만 요청)
def get_sql_query_from_llm(question: str) -> str:
    prompt = f"""
당신은 KBO 리그 선수 및 팀 기록에 대한 SQL 데이터베이스 전문가입니다.
아래는 데이터베이스의 스키마와 컬럼 설명입니다.
**반드시 여기에 명시된 테이블과 컬럼명만 정확히 사용하세요.**

{COLUMN_DESCRIPTIONS}


아래 질문에 대해 MySQL 쿼리만 출력하세요. 쿼리 외에는 아무것도 출력하지 마세요.
질문: {question}
쿼리:
"""
    result = llm(prompt)
    if isinstance(result, list):
        sql = result[0]['generated_text'] if isinstance(result[0], dict) else str(result[0])
    elif isinstance(result, dict):
        sql = result.get('generated_text', str(result))
    else:
        sql = str(result)
    match = re.search(r"(SELECT[\s\S]+?;)", sql, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return sql.strip()


# 3. 쿼리 실행 (결과는 문자열로 반환)
def run_sql(sql: str) -> str:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql)).fetchall()
        if not result:
            return "결과 없음"
        # 여러 row 처리 (첫 컬럼만 반환)
        values = []
        for row in result:
            if isinstance(row, (tuple, list)):
                values.append(str(row[0]))
            else:
                values.append(str(row))
        return ", ".join(values)
    except Exception as e:
        return f"[SQL 실행 오류] {e}"

# 4. 질문+쿼리+결과로 자연어 답변 생성
def get_natural_answer_from_llm(question: str, sql: str, result: str) -> str:
    prompt = f"""
아래는 사용자의 질문, 생성된 SQL 쿼리, 그리고 쿼리 실행 결과입니다.
이 정보를 바탕으로 자연스럽고 간결한 한 문장으로 답변만 출력하세요.

질문: {question}
SQL 쿼리: {sql}
쿼리 결과: {result}
답변:
"""
    answer = llm(prompt)
    if isinstance(answer, list):
        answer = answer[0]['generated_text'] if isinstance(answer[0], dict) else str(answer[0])
    elif isinstance(answer, dict):
        answer = answer.get('generated_text', str(answer))
    else:
        answer = str(answer)
    # 프롬프트 부분 잘라내기
    answer = answer[len(prompt):].strip() if answer.startswith(prompt) else answer.strip()
    return answer

# 5. 전체 파이프라인 함수
def ask_question(question: str) -> str:
    sql = get_sql_query_from_llm(question)
    logger.debug("LLM이 만든 쿼리: %s", sql)
    result = run_sql(sql)
    logger.debug("쿼리 결과: %s", result)
    answer = get_natural_answer_from_llm(question, sql, result)
    return answer

