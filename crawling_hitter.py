from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pymysql
import time

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
            name = cols[1].text.strip()

            # AVG가 비어있을 경우 None으로 처리
            avgText = cols[3].text.strip()
            avg = float(0) if avgText == '-' else float(0)

            data = list(map(lambda x: int(x.replace(",", "")) if x.strip() else 0, [
                cols[4].text, cols[5].text, cols[6].text, cols[7].text,
                cols[8].text, cols[9].text, cols[10].text, cols[11].text,
                cols[13].text, cols[14].text, cols[15].text
            ]))

            players.append((name, avg, *data))
        except Exception as e:
            print(f"에러 발생: {e}")
            continue

    return players


# DB 연결
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='crw10209',
    db='kbo',
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
    print(f"크롤링 중: {teamName} (teamID: {teamId})")
    # 시즌 선택
    seasonSelect = Select(driver.find_element(By.ID, "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"))
    seasonSelect.select_by_value("2024")
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
    except:
        pass
    
    # DB 저장
    for p in players:
        cursor.execute("""
            INSERT INTO hitter_info (name, avg, G, PA, AB, R, H, `2B`, `3B`, HR, RBI, SAC, SF, teamID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (*p, teamId))

    conn.commit()

    # 페이지 1로 돌아가기
    page1Btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "cphContents_cphContents_cphContents_ucPager_btnNo1")))
    page1Btn.click()
    time.sleep(5)


driver.quit()
conn.close()
print("크롤링 및 저장 완료!")
