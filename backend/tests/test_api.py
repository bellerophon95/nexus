import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check_endpoint():
    """
    Verify the /api/health endpoint returns 200 and correct status.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "timestamp" in data

def test_query_endpoint_connectivity():
    """
    Verify the /api/query endpoint is reachable (not necessarily full logic).
    We test the 422 if no query is provided (FastAPI default).
    """
    response = client.get("/api/query")
    # Should fail with 422 because 'q' is missing
    assert response.status_code == 422
