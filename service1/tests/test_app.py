import pytest
from unittest.mock import patch
from service1.app import app  


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


# --------------------------
# Test /status endpoint
# --------------------------
@patch("service1.app.requests.post")   # <-- also patch correctly
@patch("service1.app.requests.get")    # <-- patch inside the module where it's used
def test_status(mock_get, mock_post, client):

    mock_post.return_value.status_code = 200

    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "Service2 OK"

    response = client.get("/status")

    assert response.status_code == 200
    assert "uptime" in response.data.decode()
    assert "Service2 OK" in response.data.decode()


# --------------------------
# Test /log endpoint
# --------------------------
@patch("service1.app.requests.get")  # <-- correct patch path
def test_get_log(mock_get, client):
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "LOG DATA"

    response = client.get("/log")

    assert response.status_code == 200
    assert "LOG DATA" in response.data.decode()
