import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_detect():
    response = client.post("/detect", json={"sentence": "이건 욕이 아니다."})
    assert response.status_code == 200
    data = response.json()
    assert "isCurse" in data
    assert "words" in data

def test_simulate():
    req = {
        "home_team_name": "홈팀",
        "home_players": [{"id": 1, "position": "타자"}],
        "away_team_name": "어웨이팀",
        "away_players": [{"id": 2, "position": "투수"}]
    }
    response = client.post("/simulate", json=req)
    assert response.status_code == 200
    data = response.json()
    assert "prompt" in data
    assert "result" in data

def test_chat():
    response = client.post("/chat", json={"question": "안녕?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data 