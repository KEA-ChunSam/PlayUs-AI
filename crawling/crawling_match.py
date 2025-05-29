from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pymysql
import time
import datetime
import logging
import os
import datetime
from utils.db import get_db_config
# 로깅 설정
logging.basicConfig(
    filename='kbo_crawler12.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

years = [2025]

url = "https://www.koreabaseball.com/Schedule/Schedule.aspx"

options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

config = get_db_config()
conn = pymysql.connect(
    host=config['host'],
    port=config['port'],
    user=config['user'],
    password=config['password'],
    db=config['database'],  # 'database' 키 사용 (db 대신)
    charset=config['charset']
)

cursor = conn.cursor()

team_map = {
    'KIA': 1, '삼성': 2, 'LG': 3, '두산': 4, 'KT': 5,
    'SSG': 6, '롯데': 7, '한화': 8, 'NC': 9, '키움': 10
}

for year in years:
    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.ID, "ddlYear")))

        year_dropdown = Select(driver.find_element(By.ID, "ddlYear"))
        year_dropdown.select_by_value(str(year))
        time.sleep(2)

        month_dropdown = Select(driver.find_element(By.ID, "ddlMonth"))
        available_months = [opt.get_attribute("value") for opt in month_dropdown.options if opt.get_attribute("value").isdigit()]

        for month in available_months:
            try:
                month_dropdown.select_by_value(month)
                time.sleep(2)
                rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#tblScheduleList > tbody > tr")))

                current_date = None

                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 8:
                        continue

                    if any("데이터가 없습니다" in c.text for c in cols):
                        continue

                    if 'day' in cols[0].get_attribute("class"):
                        raw_date = cols[0].text.strip()  # 예: 04.01(화)
                        date_str = f"{year}-{raw_date.split('(')[0].replace('.', '-')}"
                        try:
                            current_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        except Exception as e:
                            logging.warning(f"날짜 파싱 오류: {date_str}, {e}")
                            continue
                        time_col_idx = 1
                        play_col_idx = 2
                    else:
                        time_col_idx = 0
                        play_col_idx = 1

                    # 시간 포맷 맞추기
                    time_info = cols[time_col_idx].text.strip()
                    if len(time_info) == 5: 
                        time_info += ":00"
                    elif len(time_info) == 0:
                        time_info = "00:00:00"

                    # start_time을 datetime으로 합치기
                    try:
                        start_time = datetime.datetime.combine(
                            current_date.date(),
                            datetime.datetime.strptime(time_info, "%H:%M:%S").time()
                        )
                    except Exception as e:
                        logging.warning(f"start_time 파싱 오류: {current_date} {time_info}, {e}")
                        start_time = None

                    # 경기 정보 추출
                    play_td = cols[play_col_idx]
                    play_spans = play_td.find_elements(By.TAG_NAME, "span")

                    if len(play_spans) < 3:
                        continue

                    away_team = play_spans[0].text.strip()
                    home_team = play_spans[-1].text.strip()

                    away_score, home_score = None, None
                    if len(play_spans) >= 5:
                        try:
                            away_score = int(play_spans[1].text.strip())
                            home_score = int(play_spans[3].text.strip())
                        except Exception as e:
                            logging.warning(f"점수 파싱 오류: {[span.text for span in play_spans]}, {e}")
                            away_score = None
                            home_score = None

                    home_team_id = team_map.get(home_team)
                    away_team_id = team_map.get(away_team)
                    if home_team_id is None or away_team_id is None:
                        logging.warning(f"팀 매핑 실패: away_team={away_team}, home_team={home_team}")
                        continue

                    try:
                        cursor.execute("""
                            INSERT INTO matches 
                                (home_team_id, away_team_id, match_date, created_at, home_score, away_score, start_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            home_team_id,
                            away_team_id,
                            current_date,  # datetime 객체
                            datetime.datetime.now(),  # datetime 객체
                            home_score,
                            away_score,
                            start_time  # datetime 객체
                        ))

                        conn.commit()
                        logging.info(f"경기 저장 완료: {current_date} {time_info} {away_team} vs {home_team} ({away_score}, {home_score})")
                    except Exception as e:
                        logging.error(f"[{year}년 {month}월] DB 오류: {e}", exc_info=True)

            except Exception as e:
                logging.error(f"[{year}년 {month}월] 오류: {e}", exc_info=True)

    except Exception as e:
        logging.critical(f"[{year}년] 연도 변경 실패: {e}", exc_info=True)

driver.quit()
conn.close()
logging.info("데이터 삽입 완료")
