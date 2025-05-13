import logging
import re
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pymysql
import time
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 팀 코드 매핑
teams = {
    "HT": "KIA", "SS": "삼성", "LG": "LG", "OB": "두산",
    "KT": "KT", "SK": "SSG", "LT": "롯데", "HH": "한화",
    "NC": "NC", "WO": "키움"
}

season = "2025"

def extract_players(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", {"class": "tData01 tt"})
    tbody = table.find("tbody")
    players = []

    for row in tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 19:  # 컬럼 개수 확인
            continue

        try:
            # 선수 ID 추출
            profile_link = cols[1].find("a")["href"]
            player_id = int(re.search(r'(\d+)$', profile_link).group(1))

            # 기본 정보 추출
            name = cols[1].text.strip()
            era = float(cols[3].text.strip()) if cols[3].text.strip() != '-' else None
            ip = convert_ip(cols[10].text.strip())
            
            # 숫자 데이터 추출
            def _safe_int(text: str) -> int:
                t = text.strip().replace(",", "")
                return int(t) if t.isdigit() else 0

            data = [_safe_int(cols[i].text) for i in
            [4, 5, 6, 8, 11, 12, 13, 14, 15, 16, 17]]
            
            # WHIP 처리
            whip = float(cols[18].text.strip()) if cols[18].text.strip() != '-' else None

            players.append((player_id, name, era, ip, whip, *data))
            
        except Exception as e:
            logging.error(f"행 처리 오류: {str(e)}")
            continue

    return players

def convert_ip(ip_str):
    """이닝(IP) 값을 소수로 변환 (예: 19 1/3 → 19.333)"""
    if not ip_str or ip_str == '-':
        return 0.0
    parts = ip_str.split()
    total = 0.0
    for part in parts:
        if '/' in part:
            numerator, denominator = map(int, part.split('/'))
            total += numerator / denominator
        else:
            total += float(part)
    return round(total, 3)

# DB 연결
conn = pymysql.connect(
	    host=os.getenv("DB_URL"),
	    user=os.getenv("DB_USER"),
	    password=os.getenv("DB_PASSWORD"),
	    db=os.getenv("DB_NAME"),
	    charset='utf8'
	)
cursor = conn.cursor()

# 크롬 설정
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

driver.get("https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx")
time.sleep(2)

# 팀별 크롤링
for team_id, (code, team_name) in enumerate(teams.items(), start=1):
    logging.info(f"크롤링 중: {team_name} (teamID: {team_id})")

    # 시즌 선택
    season_select = Select(driver.find_element(By.ID, "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"))
    season_select.select_by_value(season)
    time.sleep(3)

    # 팀 선택
    team_select = Select(driver.find_element(By.ID, "cphContents_cphContents_cphContents_ddlTeam_ddlTeam"))
    team_select.select_by_value(code)
    time.sleep(3)

    # 데이터 추출
    pitchers = extract_players(driver)

    # 2페이지 처리
    try:
        page2_btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "cphContents_cphContents_cphContents_ucPager_btnNo2")))
        page2_btn.click()
        time.sleep(3)
        pitchers += extract_players(driver)
    except Exception as e:
        logging.warning(f"페이지 2 처리 실패: {str(e)}")

    # DB 저장
    for p in pitchers:
        try:
            cursor.execute("""
                INSERT INTO pitcher_info (
                    id, name, era, ip, whip,
                    g, w, l, hld, h, hr, bb, hbp, so, r, er,
                    team_id, season
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    era=VALUES(era),
                    ip=VALUES(ip),
                    whip=VALUES(whip),
                    g=VALUES(g),
                    w=VALUES(w),
                    l=VALUES(l),
                    hld=VALUES(hld),
                    h=VALUES(h),
                    hr=VALUES(hr),
                    bb=VALUES(bb),
                    hbp=VALUES(hbp),
                    so=VALUES(so),
                    r=VALUES(r),
                    er=VALUES(er)
            """, (*p, team_id, season))
        except Exception as e:
            logging.error(f"DB 저장 실패: {str(e)}")

    conn.commit()

driver.quit()
conn.close()
logging.info("크롤링 및 저장 완료!")
