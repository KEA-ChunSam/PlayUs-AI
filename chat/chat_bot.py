# chat_bot_langgraph.py
import logging
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from utils.model import tokenizer, model
from utils.db import get_sqlalchemy_engine
from sqlalchemy import text
import torch
import json
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# DB 연결 설정
engine = get_sqlalchemy_engine()

COLUMN_DESCRIPTIONS = """
테이블 및 컬럼 설명:
- hitter_info : 타자 기록 정보
    - id : 선수 고유번호,
    - name : 선수 이름,
    - teamID : team 테이블을 참조하는 아이디,
    - AVGß : 타율,
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
# KBO 데이터베이스 스키마
KBO_SCHEMA = """
CREATE TABLE hitter_info (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    team_id INT,
    AVG DECIMAL(4,3),
    G INT,
    PA INT,
    AB INT,
    R INT,
    H INT,
    2B INT,
    3B INT,
    HR INT,
    RBI INT,
    SAC INT,
    SF INT,
    season INT
);

CREATE TABLE pitcher_info (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    team_id INT,
    ERA DECIMAL(4,2),
    G INT,
    W INT,
    L INT,
    HLD INT,
    WPCT DECIMAL(4,3),
    IP DECIMAL(5,1),
    H INT,
    HR INT,
    BB INT,
    HBP INT,
    SO INT,
    R INT,
    ER INT,
    WHIP DECIMAL(4,2),
    season INT
);

CREATE TABLE team (
    id INT PRIMARY KEY,
    team_name VARCHAR(50),
    stadium VARCHAR(100)
);

CREATE TABLE matches (
    id INT PRIMARY KEY,
    home_team_id INT,
    away_team_id INT,
    match_date DATE,
    home_score INT,
    away_score INT,
    start_time TIME
);


"""

# Few-shot 예제들
FEW_SHOT_EXAMPLES = """
Examples:
Q: 홈런을 가장 많이 친 선수는 누구야?
A: SELECT name, HR FROM hitter_info ORDER BY HR DESC LIMIT 1;

Q: 김하성의 타율은?
A: SELECT name, AVG FROM hitter_info WHERE name = '김하성';

Q: ERA가 가장 낮은 투수는?
A: SELECT name, ERA FROM pitcher_info ORDER BY ERA ASC LIMIT 1;

Q: 한화 이글스 선수들의 평균 타율은?
A: SELECT AVG(h.AVG) FROM hitter_info h JOIN team t ON h.team_id = t.id WHERE t.team_name = '한화';

Q: 승수가 10승 이상인 투수는?
A: SELECT name, W FROM pitcher_info WHERE W >= 10;

Q: 홈런 20개 이상인 선수들은?
A: SELECT name, HR FROM hitter_info WHERE HR >= 20;

Q: 2025년 5월 27일 경기 정보를 알려줘.
A: SELECT * FROM matches where match_date = '2025-05-27';

Q: "디아즈의 기록을 알려줘"
Query Result: [["54400", "디아즈", "0.304", "52", "222", "204", "31", "62", "12", "0", "18", "55", "0", "2", "2", "2025"]]
A: "디아즈의 2025시즌 타격 기록: 타율 0.304, 52경기 출장, 222타석, 204타수, 31득점, 62안타, 12개 2루타, 0개 3루타, 18홈런, 55타점을 기록했습니다."
"""

# State 정의
class AgentState(TypedDict):
    question: str
    sql_query: Optional[str]
    cleaned_sql: Optional[str]
    query_result: Optional[str]
    final_answer: str
    error_message: Optional[str]
    retry_count: int

# Agent 노드들
class SQLAgent:
    def __init__(self):
        self.max_retries = 3
    
    def sql_generation_node(self, state: AgentState) -> AgentState:
        """SQL 쿼리 생성 노드"""
        print(f"[SQL 생성] 질문: {state['question']}")
        
        try:
            sql_query = self._generate_sql_with_llama(state['question'])
            print(f"[SQL 생성] 생성된 쿼리: {sql_query}")
            
            return {
                **state,
                "sql_query": sql_query,
                "error_message": None
            }
        except Exception as e:
            print(f"[SQL 생성] 오류: {e}")
            return {
                **state,
                "error_message": f"SQL 생성 오류: {str(e)}"
            }
    
    def extract_sql_from_llm_output(self, llm_output: str) -> str:
        """LLM 출력에서 SQL 추출 (검색 결과 기반)"""
        
        # "assistant" 이후에 나오는 쿼리만 추출
        if "assistant" in llm_output:
            parts = llm_output.split("assistant")
            candidate = parts[-1].strip()
        else:
            candidate = llm_output.strip()
        
        # SELECT 문으로 시작하는 부분 찾기
        match = re.search(r'(SELECT\s+.*?;)', candidate, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(1)
        else:
            # SELECT 문이 없으면 전체 반환
            sql = candidate
            if not sql.endswith(';'):
                sql += ';'
        
        # 불필요한 공백 정리
        sql = ' '.join(sql.split())
        
        return sql

# sql_validation_node에서 사용
    def sql_validation_node(self, state: AgentState) -> AgentState:
        """SQL 검증 및 정리 노드"""
        print(f"[SQL 검증] 원본 쿼리: {state['sql_query']}")
        
        try:
            # 새로운 추출 방법 사용
            cleaned_sql = self.extract_sql_from_llm_output(state['sql_query'])
            
            if not cleaned_sql or not cleaned_sql.upper().strip().startswith('SELECT'):
                return {
                    **state,
                    "error_message": "유효하지 않은 SQL 쿼리"
                }
            
            print(f"[SQL 검증] 정리된 쿼리: {cleaned_sql}")
            
            return {
                **state,
                "cleaned_sql": cleaned_sql,
                "error_message": None
            }
        except Exception as e:
            print(f"[SQL 검증] 오류: {e}")
            return {
                **state,
                "error_message": f"SQL 검증 오류: {str(e)}"
            }

    
    def sql_execution_node(self, state: AgentState) -> AgentState:
        """SQL 실행 노드"""
        print(f"[SQL 실행] 쿼리: {state['cleaned_sql']}")
        
        try:
            result = self._execute_sql_safely(state['cleaned_sql'])
            print(f"[SQL 실행] 결과: {result}")
            
            return {
                **state,
                "query_result": result,
                "error_message": None
            }
        except Exception as e:
            print(f"[SQL 실행] 오류: {e}")
            return {
                **state,
                "error_message": f"SQL 실행 오류: {str(e)}"
            }
    
    def answer_generation_node(self, state: AgentState) -> AgentState:
        """자연어 답변 생성 노드 (폴백 강화)"""
        print(f"[답변 생성] 시작")
        
        try:
            # 결과 검증
            if state['query_result'] == "NO_RESULTS":
                return {
                    **state,
                    "final_answer": "해당 조건에 맞는 데이터를 찾을 수 없습니다."
                }
            
            if state['query_result'].startswith("SQL_ERROR"):
                return {
                    **state,
                    "final_answer": "데이터 조회 중 오류가 발생했습니다."
                }
            
            # 먼저 간단한 답변 생성 시도
            
            # LLM 답변 시도
            try:
                llm_answer = self._generate_natural_answer_with_llm(
                    state['question'], 
                    state['cleaned_sql'], 
                    state['query_result']
                )
                
                # LLM 답변이 유효하면 사용, 아니면 간단한 답변 사용
                final_answer = llm_answer.strip() 
                
            except Exception as e:
                print(f"[답변 생성] LLM 오류, 폴백 사용: {e}")
            
            
            print(f"[답변 생성] 최종 답변: {final_answer}")
            
            return {
                **state,
                "final_answer": final_answer,
                "error_message": None
            }
            
        except Exception as e:
            print(f"[답변 생성] 오류: {e}")
            return {
                **state,
                "final_answer": "답변 생성 중 오류가 발생했습니다.",
                "error_message": f"답변 생성 오류: {str(e)}"
            }

    
    def error_handling_node(self, state: AgentState) -> AgentState:
        """에러 처리 및 재시도 노드"""
        print(f"[에러 처리] 재시도 횟수: {state['retry_count']}")
        
        retry_count = state.get('retry_count', 0) + 1
        
        if retry_count >= self.max_retries:
            return {
                **state,
                "final_answer": "죄송합니다. 여러 번 시도했지만 적절한 답변을 생성할 수 없습니다.",
                "retry_count": retry_count
            }
        
        # 재시도를 위한 상태 초기화
        return {
            "question": state['question'],
            # "sql_query": None,
            # "cleaned_sql": None,
            # "query_result": None,
            # "final_answer": "",
            # "error_message": None,
            # "retry_count": retry_count
        }
    
    # 조건부 라우팅 함수들
    def should_validate_sql(self, state: AgentState) -> str:
        """SQL 검증 필요 여부 판단"""
        if state.get('error_message'):
            return "error_handling"
        return "sql_validation"
    
    def should_execute_sql(self, state: AgentState) -> str:
        """SQL 실행 필요 여부 판단"""
        if state.get('error_message'):
            return "error_handling"
        return "sql_execution"
    
    def should_generate_answer(self, state: AgentState) -> str:
        """답변 생성 필요 여부 판단"""
        if state.get('error_message'):
            return "error_handling"
        return "answer_generation"
    
    def should_retry_or_end(self, state: AgentState) -> str:
        """재시도 또는 종료 판단"""
        if state.get('error_message') and state.get('retry_count', 0) < self.max_retries:
            return "sql_generation"
        return END
    
    def is_final_answer_ready(self, state: AgentState) -> str:
        """최종 답변 준비 여부 판단"""
        if state.get('final_answer') and not state.get('error_message'):
            return END
        return "error_handling"
    
    # 헬퍼 메서드들 (기존 코드와 동일)
    def _create_llama_text_to_sql_prompt(self, question: str) -> str:
        """Llama-3.1-8B용 Text-to-SQL 프롬프트 생성"""
        
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert SQL developer for KBO (Korean Baseball Organization) database. Convert natural language questions to MySQL SELECT queries.

Database Schema:
{KBO_SCHEMA}

Column Description:
{COLUMN_DESCRIPTIONS}

{FEW_SHOT_EXAMPLES}

Rules:
	1.	Generate only valid MySQL SELECT statements
	2.	Use proper table and column names from the schema
	3.	End queries with semicolon
	4.	For team-related queries, use JOIN with team table
	5.	Use Korean names exactly as provided
	6.	No explanations, just the SQL query
	7.	Please refer to the Column Description for questions about player statistics.
	8.	All questions and answers must use the Database Schema.
    9. When answering player statistics questions, interpret query results using Column Descriptions to provide meaningful explanations rather than just stating raw values.

<|eot_id|><|start_header_id|>user<|end_header_id|>

Question: {question}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>

SELECT"""
        
        return prompt
    
    def _generate_sql_with_llama(self, question: str) -> str:
        """Llama-3.1-8B로 SQL 쿼리 생성"""
        
        prompt = self._create_llama_text_to_sql_prompt(question)
        
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        generation_config = {
            "max_new_tokens": 150,
            "temperature": 0.1,
            "top_p": 0.9,
            "do_sample": True,
            "pad_token_id": tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
            "repetition_penalty": 1.1
        }
        
        with torch.no_grad():
            outputs = model.generate(**inputs, **generation_config)
        
        full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return full_output
    
    def _clean_and_validate_sql(self, sql: str) -> str:
        """생성된 SQL 정리 및 검증"""
        
        print(f"원본 SQL: {sql}")
        
        sql = re.sub(r'<\|.*?\|>', '', sql)
        sql = re.sub(r'``````', '', sql, flags=re.DOTALL)
        sql = sql.strip()
        
        if not sql.upper().startswith('assistant\n\n'):
            select_match = re.search(r'(assistant\n\n\s+.*)', sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                sql = select_match.group(1)
            else:
                return None
        
        if not sql.endswith(';'):
            sql += ';'
        
        if not re.match(r'^\s*SELECT\s+', sql, re.IGNORECASE):
            return None

        
        return sql
    
    def _execute_sql_safely(self, sql: str) -> str:
        """SQL을 안전하게 실행하고 결과 반환"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql)).fetchall()
            
            if not result:
                return "NO_RESULTS"
            
            formatted_results = []
            for row in result:
                formatted_results.append([str(value) for value in row])
            
            return json.dumps(formatted_results, ensure_ascii=False)
                
        except Exception as e:
            return f"SQL_ERROR: {str(e)}"
    
    def _generate_natural_answer_with_llm(self, question: str, sql: str, result: str) -> str:
        
        answer_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

        You are a helpful assistant that converts database query results into natural Korean answers.

        <|eot_id|><|start_header_id|>user<|end_header_id|>

        사용자 질문: {question}
        컬럼 설명: {COLUMN_DESCRIPTIONS}
        만약 matches 테이블을 이용해서 결과를 받아오면
            -team_id
            "1": "KIA", 
            "2": "삼성", 
            "3": "LG", 
            "4": "두산",
            "5": "KT", 
            "6": "SSG", 
            "7": "롯데", 
            "8": "한화",
            "9": "NC", 
            "10": "키움"
        를 참고해주세요.
        쿼리 결과: {result}

        Based on the above information, please write a natural and accurate Korean response to the user’s question.
        If the question is about player statistics, please use the column names in your answer.
        The column names are in the same order as the query results, so please refer to them when creating responses about player statistics.

        
        

        <|eot_id|><|start_header_id|>assistant<|end_header_id|>

        """
        
        try:
            inputs = tokenizer(answer_prompt, return_tensors="pt", truncation=True, max_length=1024)
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=150,
                    temperature=0.4,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id
                )
            
            full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(f"[LLM 답변] 전체 출력: {repr(full_output[-200:])}")  # 마지막 200자만
            
            # SQL 추출과 동일한 방식으로 "assistant" 이후 추출
            if "assistant" in full_output:
                parts = full_output.split("assistant")
                answer = parts[-1].strip()
            else:
                answer = full_output[len(answer_prompt):].strip()
            
            # 특수 토큰 제거
            answer = re.sub(r'<\|.*?\|>', '', answer)
            answer = answer.strip()
            
            print(f"[LLM 답변] 추출된 답변: {repr(answer)}")
            
            # 답변이 비어있지 않으면 반환
            if answer:
                return answer
            else:
                print("[LLM 답변] 빈 답변, None 반환")
                return ""
                
        except Exception as e:
            print(f"[LLM 답변] 생성 오류: {e}")
            return ""


# LangGraph 워크플로우 생성
def create_sql_agent_workflow():
    """SQL Agent 워크플로우 생성"""
    
    agent = SQLAgent()
    
    # StateGraph 생성
    workflow = StateGraph(AgentState)
    
    # 노드 추가
    workflow.add_node("sql_generation", agent.sql_generation_node)
    workflow.add_node("sql_validation", agent.sql_validation_node)
    workflow.add_node("sql_execution", agent.sql_execution_node)
    workflow.add_node("answer_generation", agent.answer_generation_node)
    workflow.add_node("error_handling", agent.error_handling_node)
    
    # 엣지 추가 (조건부 라우팅)
    workflow.add_conditional_edges(
        "sql_generation",
        agent.should_validate_sql,
        {
            "sql_validation": "sql_validation",
            "error_handling": "error_handling"
        }
    )
    
    workflow.add_conditional_edges(
        "sql_validation",
        agent.should_execute_sql,
        {
            "sql_execution": "sql_execution",
            "error_handling": "error_handling"
        }
    )
    
    workflow.add_conditional_edges(
        "sql_execution",
        agent.should_generate_answer,
        {
            "answer_generation": "answer_generation",
            "error_handling": "error_handling"
        }
    )
    
    workflow.add_conditional_edges(
        "answer_generation",
        agent.is_final_answer_ready,
        {
            END: END,
            "error_handling": "error_handling"
        }
    )
    
    workflow.add_conditional_edges(
        "error_handling",
        agent.should_retry_or_end,
        {
            "sql_generation": "sql_generation",
            END: END
        }
    )
    
    # 시작점 설정
    workflow.set_entry_point("sql_generation")
    
    return workflow.compile()

# 메인 인터페이스
def ask_question(question: str) -> str:
    """메인 질문 처리 함수"""
    
    print(f"질문 처리 시작: {question}")
    
    # 워크플로우 생성
    app = create_sql_agent_workflow()
    
    # 초기 상태 설정
    initial_state = {
        "question": question,
        "sql_query": None,
        "cleaned_sql": None,
        "query_result": None,
        "final_answer": "",
        "error_message": None,
        "retry_count": 0
    }
    
    try:
        # 워크플로우 실행
        final_state = app.invoke(initial_state)
        
        print(f"최종 상태: {final_state}")
        return final_state.get("final_answer", "죄송합니다. 답변을 생성할 수 없습니다.")
        
    except Exception as e:
        print(f"워크플로우 실행 오류: {e}")
        return "죄송합니다. 질문 처리 중 오류가 발생했습니다."

