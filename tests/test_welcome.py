def test_index_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert b"English AI Tutor" in response.content


def test_topics_returns_list(client):
    response = client.get("/api/topics")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 4
    assert data[0]["id"] == "small-talk"
    assert data[0]["name"] == "Small Talk"


def test_progress_returns_defaults(client):
    response = client.get("/api/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["last_topic"] == "small-talk"
    assert data["last_level"] == "A2"


def test_create_session(client):
    response = client.post(
        "/api/sessions",
        json={"topic": "travel", "level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 10


def test_create_session_persists_progress(client):
    client.post("/api/sessions", json={"topic": "restaurant", "level": "C1"})
    progress = client.get("/api/progress").json()
    assert progress["last_topic"] == "restaurant"
    assert progress["last_level"] == "C1"


def test_static_css_served(client):
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_static_js_served(client):
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
