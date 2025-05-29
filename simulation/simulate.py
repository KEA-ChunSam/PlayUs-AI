# simulate.py
from typing import List, Dict, Any
import re
import random
from utils.model import generate_simulation_result
from utils.db import run_sql_query

def get_player_stats_by_ids(player_ids: List[int], position: str) -> List[Dict[str, Any]]:
    if not player_ids:
        return []
    
    if position == "투수":
        sql = f"SELECT * FROM pitcher_info WHERE id IN ({', '.join(map(str, player_ids))});"
    else:
        sql = f"SELECT * FROM hitter_info WHERE id IN ({', '.join(map(str, player_ids))});"
    return run_sql_query(sql)

def generate_prompt(
    home_team_name: str,
    away_team_name: str,
    home_pitcher_stats: dict,
    home_hitter_stats: list,
    away_pitcher_stats: dict,
    away_hitter_stats: list
) -> str:
    
    # 실제 선수 이름만 추출 (최대 5명씩)
    home_names = []
    for i, player in enumerate(home_hitter_stats[:5]):
        name = player.get('name')
        if name:
            home_names.append(name)
        else:
            home_names.append(f'홈선수{i+1}')
    
    away_names = []
    for i, player in enumerate(away_hitter_stats[:5]):
        name = player.get('name')
        if name:
            away_names.append(name)
        else:
            away_names.append(f'원정선수{i+1}')
    
    home_pitcher_name = home_pitcher_stats.get('name', '홈투수')
    away_pitcher_name = away_pitcher_stats.get('name', '원정투수')
    
    prompt = f"""
야구 시뮬레이션을 해주세요.
사용할 선수 이름 (반드시 이 이름들만 사용하세요):
홈팀 {home_team_name}: {', '.join(home_names)} (투수: {home_pitcher_name})
원정팀 {away_team_name}: {', '.join(away_names)} (투수: {away_pitcher_name})

**중요: 위에 명시된 선수 이름만 사용하고, 다른 이름은 절대 사용하지 마세요.**
다음 JSON 형태로 9이닝 경기 결과를 작성해주세요:

[
    {{
        "title": "1회초",
        "plays": [
            "{home_names[0] if home_names else '선수'}: 안타",
            "{home_names[1] if len(home_names) > 1 else '선수'}: 삼진",
            "점수: {home_team_name} 1 - {away_team_name} 0"
        ]
    }},
    {{
        "title": "1회말",
        "plays": [
            "{away_names[0] if away_names else '선수'}: 볼넷",
            "{away_names[1] if len(away_names) > 1 else '선수'}: 홈런",
            "점수: {home_team_name} 1 - {away_team_name} 2"
        ]
    }}
]

규칙:
- 오직 위에 명시된 선수 이름만 사용
- 각 이닝별로 2-4개의 주요 장면 작성
- 매 이닝마다 점수 상황 포함
- 백틱(```
- 코드나 설명 없이 JSON 배열만 작성
"""
    return prompt.strip()

def validate_player_names(result: str, valid_names: list) -> str:
    """결과에서 유효하지 않은 선수 이름을 유효한 이름으로 교체"""
    if not valid_names:
        return result
    
    # 선수 이름 패턴 찾기 (예: "김태연: 안타")
    name_pattern = r'"([^"]+?):\s*([^"]*?)"'
    
    def replace_invalid_name(match):
        name = match.group(1).strip()
        action = match.group(2).strip()
        
        # 유효한 이름인지 확인
        if name in valid_names:
            return f'"{name}: {action}"'
        else:
            # 유효하지 않은 이름을 유효한 이름으로 교체
            replacement_name = random.choice(valid_names)
            return f'"{replacement_name}: {action}"'
    
    # 유효하지 않은 이름 교체
    validated_result = re.sub(name_pattern, replace_invalid_name, result)
    return validated_result

def clean_json_result(result: str) -> str:
    """결과에서 JSON 부분만 추출"""
    # ```
    result = re.sub(r'```json\s*', '', result)
    
    # JSON 배열 부분만 추출
    start_idx = result.find('[')
    end_idx = result.rfind(']')
    
    if start_idx != -1 and end_idx != -1:
        return result[start_idx:end_idx+1]
    else:
        return result


def simulate_game_rag(home_team_name, home_players, away_team_name, away_players):
    try:
        request = {
            "home_team_name": home_team_name,
            "home_players": home_players,
            "away_team_name": away_team_name,
            "away_players": away_players
        }
        
        # 1. 선수 ID 추출
        home_pitcher_ids = [p["id"] for p in request["home_players"] if p["position"] == "투수"]
        home_hitter_ids = [p["id"] for p in request["home_players"] if p["position"] != "투수"]
        away_pitcher_ids = [p["id"] for p in request["away_players"] if p["position"] == "투수"]
        away_hitter_ids = [p["id"] for p in request["away_players"] if p["position"] != "투수"]

        # 2. DB에서 기록 가져오기
        home_pitcher_stats = get_player_stats_by_ids(home_pitcher_ids, "투수")
        home_hitter_stats = get_player_stats_by_ids(home_hitter_ids, "타자")
        away_pitcher_stats = get_player_stats_by_ids(away_pitcher_ids, "투수")
        away_hitter_stats = get_player_stats_by_ids(away_hitter_ids, "타자")

        # 3. 프롬프트 생성
        prompt = generate_prompt(
            home_team_name,
            away_team_name,
            home_pitcher_stats[0] if home_pitcher_stats else {},
            home_hitter_stats,
            away_pitcher_stats[0] if away_pitcher_stats else {},
            away_hitter_stats
        )

        # 4. LLM 호출
        result = generate_simulation_result(prompt)
        
        # 5. JSON 정리
        cleaned_result = clean_json_result(result)
        
        # 6. 유효한 선수 이름 리스트 생성
        all_valid_names = []
        for player in home_hitter_stats:
            if player.get('name'):
                all_valid_names.append(player['name'])
        for player in away_hitter_stats:
            if player.get('name'):
                all_valid_names.append(player['name'])
        if home_pitcher_stats and home_pitcher_stats[0].get('name'):
            all_valid_names.append(home_pitcher_stats[0]['name'])
        if away_pitcher_stats and away_pitcher_stats[0].get('name'):
            all_valid_names.append(away_pitcher_stats[0]['name'])
        
        # 중복 제거
        all_valid_names = list(set(all_valid_names))
        
        # 7. 선수 이름 검증 및 교체
        if all_valid_names:
            validated_result = validate_player_names(cleaned_result, all_valid_names)
        else:
            validated_result = cleaned_result
        
        return {"prompt": prompt, "result": validated_result}
        
    except Exception as e:
        return {"prompt": "", "result": f"시뮬레이션 처리 중 오류: {str(e)}"}
