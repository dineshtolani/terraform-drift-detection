import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from fastapi.testclient import TestClient
from synthetic_data import generate_plan
from app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_detect_endpoint_returns_200(client):
    plan = generate_plan("security", seed=1)
    resp = client.post("/detect", json=plan)
    assert resp.status_code == 200


def test_detect_endpoint_returns_drift_type(client):
    plan = generate_plan("config", seed=2)
    resp = client.post("/detect", json=plan)
    data = resp.json()
    assert "drift_type" in data
    assert "confidence" in data
    assert "severity" in data
    assert "changes" in data
    assert "event_id" in data


def test_detect_all_drift_types_return_valid(client):
    for dtype in ["security", "config", "tag", "deletion", "no_drift"]:
        plan = generate_plan(dtype, seed=3)
        resp = client.post("/detect", json=plan)
        assert resp.status_code == 200
        data = resp.json()
        assert data["drift_type"] in ["security", "config", "tag", "deletion", "no_drift"]
        assert 0 <= data["confidence"] <= 1
        assert data["severity"] in ["critical", "high", "low", "none"]


def test_history_endpoint(client):
    resp = client.get("/history?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_alerts_endpoint(client):
    resp = client.get("/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "drift_detections" in resp.text


def test_summary_endpoint(client):
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "repeat_alerts" in data


def test_dashboard_ui_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Drift Detector" in resp.text


def test_detect_with_empty_plan(client):
    resp = client.post("/detect", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["drift_type"] == "no_drift"
    assert data["changes"] == 0
