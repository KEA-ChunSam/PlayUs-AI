# simulate.py
from typing import List, Dict, Any
import re
import random
from utils.model import generate_simulation_result
from utils.db import run_sql_query
import json
import traceback

def get_player_stats_by_ids(player_ids: List[int], position: str) -> List[Dict[str, Any]]:
    if not player_ids:
        return []
    
    if position == "투수":
        sql = f"SELECT * FROM pitcher_info WHERE id IN ({', '.join(map(str, player_ids))});"
    else:
        sql = f"SELECT * FROM hitter_info WHERE id IN ({', '.join(map(str, player_ids))});"
    return run_sql_query(sql)

def calculate_realistic_probabilities(player_stats, position):
    """선수 성적을 기반으로 현실적인 확률 계산"""
    if position == "타자":
        avg = float(player_stats.get('avg', 0.250))
        hr = int(player_stats.get('HR', 0))
        
        # 현실적인 확률 조정
        hit_prob = min(avg * 0.8, 0.400)  # 최대 40% 안타율
        hr_prob = min(hr / 600, 0.050)    # 최대 5% 홈런율
        walk_prob = 0.08                  # 8% 볼넷율
        out_prob = 1 - hit_prob - hr_prob - walk_prob
        
        return {
            "hit": hit_prob,
            "homerun": hr_prob,
            "walk": walk_prob,
            "out": max(out_prob, 0.5)  # 최소 50% 아웃율
        }
    else:  # 투수
        era = float(player_stats.get('ERA', 4.00))
        
        # ERA가 낮을수록 상대 타율 감소
        era_factor = min(era / 3.0, 2.0)  # ERA 조정 팩터
        
        return {"era_factor": era_factor}

def determine_pitcher_change(current_pitcher, pitching_team_stats, inning, runs_allowed_this_game, outs_pitched):
    """투수 교체 여부 결정"""
    
    # 기본 교체 조건들
    era = float(current_pitcher.get('ERA', 4.00))
    
    # 교체 확률 계산
    change_prob = 0.0
    
    # 이닝별 교체 확률
    if inning >= 7:
        change_prob += 0.3
    if inning >= 8:
        change_prob += 0.4
    
    # 실점에 따른 교체 확률
    if runs_allowed_this_game >= 4:
        change_prob += 0.5
    elif runs_allowed_this_game >= 2:
        change_prob += 0.2
    
    # ERA에 따른 교체 확률
    if era > 5.0:
        change_prob += 0.3
    
    # 투구 수 (대략적 계산)
    estimated_pitches = outs_pitched * 15  # 아웃당 평균 15구
    if estimated_pitches > 100:
        change_prob += 0.4
    
    return random.random() < min(change_prob, 0.8)

def select_relief_pitcher(pitching_team_stats, used_pitchers, inning, situation):
    """상황에 맞는 구원투수 선택"""
    available_pitchers = [p for p in pitching_team_stats if p.get('name') not in used_pitchers]
    
    if not available_pitchers:
        return None
    
    # 상황별 투수 선택 로직
    if inning >= 9:
        # 9회: 마무리 투수 (ERA가 가장 낮은 투수)
        return min(available_pitchers, key=lambda p: float(p.get('ERA', 4.00)))
    elif inning >= 7:
        # 7-8회: 셋업맨 (ERA 기준 상위 투수)
        sorted_pitchers = sorted(available_pitchers, key=lambda p: float(p.get('ERA', 4.00)))
        return sorted_pitchers[0] if sorted_pitchers else None
    else:
        # 중간계투: 랜덤 선택
        return random.choice(available_pitchers)

def simulate_at_bat(hitter_stats, pitcher_era_factor=1.0):
    """현실적인 타석 결과 시뮬레이션"""
    probs = calculate_realistic_probabilities(hitter_stats, "타자")
    
    # 투수 능력에 따른 확률 조정
    adjusted_hit_prob = probs["hit"] / pitcher_era_factor
    adjusted_hr_prob = probs["homerun"] / pitcher_era_factor
    
    random_val = random.random()
    
    if random_val < adjusted_hr_prob:
        return "홈런", False
    elif random_val < adjusted_hr_prob + adjusted_hit_prob:
        return "안타", False
    elif random_val < adjusted_hr_prob + adjusted_hit_prob + probs["walk"]:
        return "볼넷", False
    else:
        out_types = ["삼진", "플라이아웃", "땅볼아웃", "스트라이크 아웃"]
        return random.choice(out_types), True

def simulate_realistic_inning_with_pitcher_management(batting_team_stats, pitching_team_stats, inning_name, game_state):
    """투수 교체를 포함한 현실적인 이닝 시뮬레이션"""
    plays = []
    outs = 0
    runners = {"1루": False, "2루": False, "3루": False}
    runs_scored = 0
    
    # 현재 투수 정보
    current_pitcher = game_state.get('current_pitcher')
    if not current_pitcher and pitching_team_stats:
        current_pitcher = pitching_team_stats[0]  # 선발투수
        game_state['current_pitcher'] = current_pitcher
        game_state['used_pitchers'] = {current_pitcher.get('name')}
        game_state['pitcher_runs_allowed'] = 0
        game_state['pitcher_outs'] = 0
    
    # 투수 교체 검토
    inning_num = int(inning_name.split('회')[0])
    if (inning_num >= 6 and 
        determine_pitcher_change(
            current_pitcher, 
            pitching_team_stats, 
            inning_num, 
            game_state.get('pitcher_runs_allowed', 0),
            game_state.get('pitcher_outs', 0)
        )):
        
        # 새 투수 선택
        new_pitcher = select_relief_pitcher(
            pitching_team_stats, 
            game_state.get('used_pitchers', set()), 
            inning_num, 
            'normal'
        )
        
        if new_pitcher:
            old_pitcher_name = current_pitcher.get('name', '투수')
            new_pitcher_name = new_pitcher.get('name', '투수')
            plays.append(f"투수교체: {old_pitcher_name} → {new_pitcher_name}")
            
            current_pitcher = new_pitcher
            game_state['current_pitcher'] = current_pitcher
            game_state['used_pitchers'].add(new_pitcher_name)
            game_state['pitcher_runs_allowed'] = 0
            game_state['pitcher_outs'] = 0
    
    # 투수 ERA 팩터 계산
    pitcher_era_factor = 1.0
    if current_pitcher:
        pitcher_probs = calculate_realistic_probabilities(current_pitcher, "투수")
        pitcher_era_factor = pitcher_probs["era_factor"]
    
    batter_index = 0
    max_batters = min(len(batting_team_stats), 15)
    
    while outs < 3 and batter_index < max_batters:
        if not batting_team_stats:
            break
            
        batter = batting_team_stats[batter_index % len(batting_team_stats)]
        batter_name = batter.get('name', f'선수{batter_index+1}')
        
        result, is_out = simulate_at_bat(batter, pitcher_era_factor)
        
        if is_out:
            outs += 1
            game_state['pitcher_outs'] += 1
            plays.append(f"{batter_name}: {result} ({outs}아웃)")
        else:
            if result == "홈런":
                runs_this_play = 1 + sum(runners.values())
                runs_scored += runs_this_play
                game_state['pitcher_runs_allowed'] += runs_this_play
                runners = {"1루": False, "2루": False, "3루": False}
                plays.append(f"{batter_name}: {result} ({outs}아웃)")
            elif result == "안타":
                runs_this_play = 0
                if runners["3루"]:
                    runs_this_play += 1
                if runners["2루"] and random.random() < 0.7:
                    runs_this_play += 1
                    runners["2루"] = False
                if runners["1루"]:
                    runners["2루"] = True
                    runners["1루"] = False
                runners["1루"] = True
                
                runs_scored += runs_this_play
                game_state['pitcher_runs_allowed'] += runs_this_play
                plays.append(f"{batter_name}: {result} ({outs}아웃)")
            elif result == "볼넷":
                runs_this_play = 0
                if runners["3루"] and runners["2루"] and runners["1루"]:
                    runs_this_play += 1
                if runners["2루"] and runners["1루"]:
                    runners["3루"] = True
                if runners["1루"]:
                    runners["2루"] = True
                runners["1루"] = True
                
                runs_scored += runs_this_play
                game_state['pitcher_runs_allowed'] += runs_this_play
                plays.append(f"{batter_name}: {result} ({outs}아웃)")
        
        batter_index += 1
    
    return plays, runs_scored

def generate_realistic_simulation_with_pitcher_management(home_hitter_stats, home_pitcher_stats, away_hitter_stats, away_pitcher_stats):
    """투수 교체를 포함한 현실적인 9이닝 경기 시뮬레이션"""
    game_result = []
    home_score = 0
    away_score = 0
    
    # 각 팀의 투수 상태 관리
    home_pitcher_state = {}
    away_pitcher_state = {}
    
    for inning in range(1, 10):
        # 초 (원정팀 공격)
        plays, runs = simulate_realistic_inning_with_pitcher_management(
            away_hitter_stats, home_pitcher_stats, f"{inning}회초", home_pitcher_state
        )
        away_score += runs
        
        game_result.append({
            "title": f"{inning}회초",
            "plays": plays,
            "score": f"{away_score}-{home_score}"
        })
        
        # 말 (홈팀 공격)
        plays, runs = simulate_realistic_inning_with_pitcher_management(
            home_hitter_stats, away_pitcher_stats, f"{inning}회말", away_pitcher_state
        )
        home_score += runs
        
        game_result.append({
            "title": f"{inning}회말",
            "plays": plays,
            "score": f"{away_score}-{home_score}"
        })
    
    return game_result

def generate_prompt(
    home_team_name: str,
    away_team_name: str,
    home_pitcher_stats: list,
    home_hitter_stats: list,
    away_pitcher_stats: list,
    away_hitter_stats: list
) -> str:
    
    # 입력값 안전성 확보
    home_pitcher_stats = home_pitcher_stats if isinstance(home_pitcher_stats, list) else []
    home_hitter_stats = home_hitter_stats if isinstance(home_hitter_stats, list) else []
    away_pitcher_stats = away_pitcher_stats if isinstance(away_pitcher_stats, list) else []
    away_hitter_stats = away_hitter_stats if isinstance(away_hitter_stats, list) else []
    
    # 홈팀 타자 정보
    home_hitter_info = []
    for player in home_hitter_stats:
        if isinstance(player, dict):
            name = player.get('name', '홈선수')
            avg = player.get('avg', 0.000)
            hr = player.get('HR', 0)
            rbi = player.get('RBI', 0)
            home_hitter_info.append(f"{name}(타율:{avg:.3f}, 홈런:{hr}, 타점:{rbi})")
        else:
            home_hitter_info.append(f"홈선수{len(home_hitter_info)+1}")
    
    # 원정팀 타자 정보
    away_hitter_info = []
    for player in away_hitter_stats:
        if isinstance(player, dict):
            name = player.get('name', '원정선수')
            avg = player.get('avg', 0.000)
            hr = player.get('HR', 0)
            rbi = player.get('RBI', 0)
            away_hitter_info.append(f"{name}(타율:{avg:.3f}, 홈런:{hr}, 타점:{rbi})")
        else:
            away_hitter_info.append(f"원정선수{len(away_hitter_info)+1}")
    
    # 홈팀 투수 정보
    home_pitcher_info = []
    for player in home_pitcher_stats:
        if isinstance(player, dict):
            name = player.get('name', '홈투수')
            era = player.get('ERA', 0.00)
            wins = player.get('W', 0)
            losses = player.get('L', 0)
            home_pitcher_info.append(f"{name}(평균자책점:{era:.2f}, {wins}승{losses}패)")
        else:
            home_pitcher_info.append(f"홈투수{len(home_pitcher_info)+1}")
    
    # 원정팀 투수 정보
    away_pitcher_info = []
    for player in away_pitcher_stats:
        if isinstance(player, dict):
            name = player.get('name', '원정투수')
            era = player.get('ERA', 0.00)
            wins = player.get('W', 0)
            losses = player.get('L', 0)
            away_pitcher_info.append(f"{name}(평균자책점:{era:.2f}, {wins}승{losses}패)")
        else:
            away_pitcher_info.append(f"원정투수{len(away_pitcher_info)+1}")
    
    # 선수 이름만 추출 (안전한 방식으로 수정)
    all_names = []
    for stats_list in [home_hitter_stats, away_hitter_stats, home_pitcher_stats, away_pitcher_stats]:
        for player in stats_list:
            if isinstance(player, dict) and player.get('name'):
                all_names.append(player['name'])
    
    prompt = f"""
야구 시뮬레이션을 해주세요.

팀 정보:
홈팀 {home_team_name}:
- 타자: {', '.join(home_hitter_info)}
- 투수: {', '.join(home_pitcher_info)}

원정팀 {away_team_name}:
- 타자: {', '.join(away_hitter_info)}
- 투수: {', '.join(away_pitcher_info)}

**중요: 현실적인 야구 경기를 시뮬레이션해주세요.**
**일반적인 야구 경기는 3-5점 정도의 점수로 끝납니다.**
**타율이 높아도 30% 정도이고, 대부분의 타석은 아웃입니다.**
**각 이닝에서 3아웃이 되면 반드시 공격이 끝납니다.**
**평균자책점이 낮은 투수는 실점을 적게 허용합니다.**

사용할 선수 이름: {', '.join(all_names)}

다음 JSON 형태로 9이닝 경기 결과를 작성해주세요:
[
    {{
        "title": "1회초",
        "plays": [
            "선수명: 삼진 (1아웃)",
            "선수명: 플라이아웃 (2아웃)",
            "선수명: 땅볼아웃 (3아웃)"
        ],
        "score": "0-0"
    }}
]

규칙:
- 경기는 0:0 부터 시작
- 각 이닝마다 정확히 3아웃이 되면 공격 종료
- 대부분의 타석은 아웃 (삼진, 플라이아웃, 땅볼아웃)
- 안타나 홈런은 가끔씩만 발생
- 최종 점수는 10점을 넘지 않도록 현실적으로
- 아웃카운트를 정확히 추적하여 3아웃 시 이닝 종료
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

        # 3. 투수 교체를 포함한 현실적인 시뮬레이션 생성
        realistic_result = generate_realistic_simulation_with_pitcher_management(
            home_hitter_stats, home_pitcher_stats, 
            away_hitter_stats, away_pitcher_stats
        )
        
        # JSON 형태로 변환
        
        realistic_json = json.dumps(realistic_result, ensure_ascii=False, indent=2)

        # 4. 프롬프트 생성 (기존 방식 유지)
        prompt = generate_prompt(
            home_team_name,
            away_team_name,
            home_pitcher_stats,
            home_hitter_stats,
            away_pitcher_stats,
            away_hitter_stats
        )

        # 5. 현실적인 시뮬레이션 결과 반환
        return {"prompt": prompt, "result": realistic_json}
        
    except Exception as e:
        
        error_details = traceback.format_exc()
        print(f"상세 오류: {error_details}")
        return {"prompt": "", "result": f"시뮬레이션 처리 중 오류: {str(e)}"}
