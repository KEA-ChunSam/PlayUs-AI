from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re


years = [2022, 2023, 2024]


url = "https://www.koreabaseball.com/Schedule/Schedule.aspx"

# Selenium WebDriver 실행 (Chrome 사용)
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # 브라우저 창 없이 실행 가능
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

data = []

for year in years:
    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.ID, "ddlYear")))

        
        year_dropdown = Select(driver.find_element(By.ID, "ddlYear"))
        year_dropdown.select_by_value(str(year))
        time.sleep(2)  

        
        month_dropdown = Select(driver.find_element(By.ID, "ddlMonth"))
        available_months = [option.get_attribute("value") for option in month_dropdown.options if option.get_attribute("value").isdigit()]

        print(f" {year}년 사용 가능한 월: {available_months}")  

        for month in available_months:
            try:
                month_dropdown.select_by_value(str(month))
                time.sleep(2)  

                
                rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#tblScheduleList > tbody > tr")))

                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 5:
                        continue  

                    date = f"{year}.{cols[0].text.strip()}"  # 날짜
                    time_info = cols[1].text.strip()  # 시간
                    match_info = cols[2].text.strip() # 경기 정보
                    stadium = cols[7].text.strip()  # 구장
                    
                   
                    match_pattern = re.match(r"(.+?)(\d+)vs(\d+)(.+)", match_info)
                    if match_pattern:
                        away_team = match_pattern.group(1).strip()  # 원정팀
                        home_team = match_pattern.group(4).strip()  # 홈팀
                        away_score = int(match_pattern.group(2))  # 원정팀 점수
                        home_score = int(match_pattern.group(3))  # 홈팀 점수
                        
                        
                        if(away_score > home_score):
                            winner = away_team
                        elif(away_score == home_score):
                            winner = "무승부"   # 무승부 처리
                        else:
                            winner = home_team


                        data.append([date, time_info, away_team, home_team, away_score, home_score, winner, stadium])

            except Exception as e:
                print(f"[{year}년 {month}월] 데이터 가져오기 실패: {e}")

    except Exception as e:
        print(f"[{year}년] 연도 변경 실패: {e}")

driver.quit()


df = pd.DataFrame(data, columns=["날짜", "시간", "원정팀", "홈팀", "원정팀 점수", "홈팀 점수", "승리팀", "구장"])

df.to_csv("KBO_schedule.csv", index=False, encoding="utf-8-sig")

print(" 크롤링 완료! 데이터가 KBO_schedule.csv에 저장되었습니다.")
