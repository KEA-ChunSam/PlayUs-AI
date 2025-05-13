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
import os
import time

# 로깅 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

season = "2025"

# 팀 코드 매핑
teams = {
    "HT": "KIA", "SS": "삼성", "LG": "LG", "OB": "두산",
    "KT": "KT", "SK": "SSG", "LT": "롯데", "HH": "한화",
    "NC": "NC", "WO": "키움"
}

def extractPlayers(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", {"class": "tData01 tt"})
    tbody = table.find("tbody")
    players = []

    for row in tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 16:
            continue

        try:
            # 선수 ID 추출 (프로필 링크에서 추출)
            profile_link = cols[1].find("a")["href"]
            player_id = int(re.search(r'(\d+)', profile_link).group(1))

            name = cols[1].text.strip()
            avgText = cols[3].text.strip()
            avg = None if avgText == '-' else float(avgText)

            data = list(map(lambda x: int(x.replace(",", "")) if x.strip() else 0, [
                cols[4].text, cols[5].text, cols[6].text, cols[7].text,
                cols[8].text, cols[9].text, cols[10].text, cols[11].text,
                cols[13].text, cols[14].text, cols[15].text
            ]))

            players.append((player_id, name, avg, *data))
        except Exception as e:
            logging.error(f"에러 발생: {e}")
            continue

    return players

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

driver.get("https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx")
time.sleep(2)

# 팀별 크롤링
for teamId, (code, teamName) in enumerate(teams.items(), start=1):
    logging.info(f"크롤링 중: {teamName} (teamID: {teamId})")
    
    # 시즌 선택
    seasonSelect = Select(driver.find_element(By.ID, "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"))
    seasonSelect.select_by_value(season)
    time.sleep(5)
    
    # 팀 선택
    teamSelect = Select(driver.find_element(By.ID, "cphContents_cphContents_cphContents_ddlTeam_ddlTeam"))
    teamSelect.select_by_value(code)
    time.sleep(5)

    # 페이지 1
    players = extractPlayers(driver)

    # 페이지 2 (있다면)
    try:
        page2Btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "cphContents_cphContents_cphContents_ucPager_btnNo2")))
        page2Btn.click()
        time.sleep(5)
        players += extractPlayers(driver)
    except Exception as e:
        logging.warning(f"페이지 2 없음 또는 클릭 실패: {e}")
        pass
    
    # DB 저장
    for p in players:
        try:
            cursor.execute("""
                INSERT INTO hitter_info
                    (id, name, avg, G, PA, AB, R, H, `2B`, `3B`, HR, RBI, SAC, SF, team_id, season)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    avg=VALUES(avg), G=VALUES(G), PA=VALUES(PA), AB=VALUES(AB), R=VALUES(R),
                    H=VALUES(H), `2B`=VALUES(`2B`), `3B`=VALUES(`3B`), HR=VALUES(HR),
                    RBI=VALUES(RBI), SAC=VALUES(SAC), SF=VALUES(SF)
            """, (p[0], p[1], p[2], *p[3:], teamId, int(season)))
        except Exception as e:
            logging.error(f"DB 저장 에러: {e}")

    conn.commit()

    # 페이지 1로 돌아가기
    try:
        page1Btn = wait.until(EC.element_to_be_clickable(
                (By.ID, "cphContents_cphContents_cphContents_ucPager_btnNo1")))
        page1Btn.click()
        time.sleep(5)
    except Exception as e:
        logging.warning(f"페이지 1로 돌아가기 실패: {e}")

driver.quit()
conn.close()
logging.info("크롤링 및 저장 완료!")
