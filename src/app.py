#!/usr/bin/env python3
"""FastAPI app for Terraform Drift Detection."""

import json
import os
import sys
from contextlib import asynccontextmanager

import numpy as np
import joblib
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(__file__))
from features import extract_features, features_to_list, FEATURE_NAMES
from db import (
    init_db, save_drift_event, get_recent_events,
    get_alerts, get_summary,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "drift_classifier.joblib")

model = None


def load_model():
    global model
    if model is None:
        if os.path.exists(MODEL_PATH):
            model = joblib.load(MODEL_PATH)
        else:
            model = None


@asynccontextmanager
async def lifespan(app):
    init_db()
    load_model()
    yield


app = FastAPI(title="Terraform Drift Detector", lifespan=lifespan)


DRIFT_SEVERITY = {
    "no_drift": "none",
    "security": "critical",
    "config": "high",
    "tag": "low",
    "deletion": "high",
}


def predict_drift(features):
    if model is None:
        return "no_drift", 0.0
    vec = np.array([features_to_list(features)])
    probs = model.predict_proba(vec)[0]
    pred = model.predict(vec)[0]
    confidence = float(max(probs))
    return pred, confidence


@app.post("/detect")
def detect_plan(plan: dict):
    features = extract_features(plan)
    drift_type, confidence = predict_drift(features)

    total_changes = features["total_changes"]
    severity = DRIFT_SEVERITY.get(drift_type, "unknown")
    changed_resources = [rc.get("address", "") for rc in plan.get("resource_changes", [])
                         if rc.get("change", {}).get("actions", []) != ["no-op"]]
    resource_str = ", ".join(changed_resources[:5])

    event_id = save_drift_event(
        drift_type=drift_type,
        confidence=confidence,
        severity=severity,
        resource=resource_str or "none",
        changes_count=total_changes,
        features_dict=features,
        plan_dict=plan,
    )

    return {
        "event_id": event_id,
        "drift_type": drift_type,
        "confidence": round(confidence, 3),
        "severity": severity,
        "changes": total_changes,
        "features": features,
    }


@app.get("/history")
def history(limit: int = 20):
    rows = get_recent_events(limit)
    return [
        {
            "id": r[0], "drift_type": r[1], "confidence": r[2],
            "severity": r[3], "resource": r[4], "changes": r[5],
            "detected_at": r[6],
        }
        for r in rows
    ]


@app.get("/alerts")
def alerts(limit: int = 10):
    rows = get_alerts(limit)
    return [
        {
            "id": r[0], "message": r[1], "is_repeat": bool(r[2]),
            "repeat_count": r[3], "created_at": r[4],
            "drift_type": r[5], "resource": r[6],
        }
        for r in rows
    ]


@app.get("/api/summary")
def summary():
    return get_summary()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    s = get_summary()
    events = get_recent_events(10)
    alert_list = get_alerts(10)

    rows_html = ""
    for e in events:
        rows_html += f"""<tr>
            <td>{e[5]}</td>
            <td><span class="badge badge-{e[3]}">{e[1]}</span></td>
            <td>{e[2] or '-'}</td>
            <td><span class="badge badge-{e[3]}">{e[3]}</span></td>
            <td style="font-size:0.85em">{e[4]}</td>
            <td>{e[6]}</td>
        </tr>"""

    alerts_html = ""
    for a in alert_list:
        cls = "repeat" if a[2] else ""
        icon = "🔁" if a[2] else "⚠️"
        alerts_html += f"""<tr class="{cls}">
            <td>{icon}</td>
            <td>{a[1]}</td>
            <td>{a[4]}</td>
        </tr>"""

    by_type_html = ""
    for row in s["by_type"]:
        by_type_html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terraform Drift Detector</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📡</text></svg>">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 1.8em; margin-bottom: 8px; color: #38bdf8; }}
        h2 {{ font-size: 1.2em; margin: 24px 0 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
        .subtitle {{ color: #64748b; margin-bottom: 24px; font-size: 0.9em; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
        .stat-card .value {{ font-size: 2em; font-weight: 700; color: #38bdf8; }}
        .stat-card .label {{ font-size: 0.8em; color: #64748b; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }}
        th {{ background: #334155; padding: 12px 16px; text-align: left; font-size: 0.8em; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; }}
        td {{ padding: 12px 16px; border-bottom: 1px solid #1e293b; font-size: 0.9em; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background: #334155; }}
        .badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }}
        .badge-critical {{ background: #7f1d1d; color: #fca5a5; }}
        .badge-high {{ background: #78350f; color: #fdba74; }}
        .badge-low {{ background: #1e3a5f; color: #93c5fd; }}
        .badge-none {{ background: #166534; color: #86efac; }}
        .badge-unknown {{ background: #3f3f46; color: #a1a1aa; }}
        tr.repeat {{ background: #1e1b0e !important; }}
        tr.repeat td:first-child {{ color: #fbbf24; }}
        .layout {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }}
        @media (max-width: 768px) {{ .layout {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
<div class="container">
    <h1>📡 Terraform Drift Detector</h1>
    <p class="subtitle">ML-powered drift classification · Random Forest · {s["total_events"]} events tracked</p>

    <div class="stats">
        <div class="stat-card"><div class="value">{s["total_events"]}</div><div class="label">Total Events</div></div>
        <div class="stat-card"><div class="value">{s["repeat_alerts"]}</div><div class="label">Repeat Incidents</div></div>
        <div class="stat-card"><div class="value">{len(s["by_type"])}</div><div class="label">Drift Types</div></div>
    </div>

    <div class="layout">
        <div>
            <h2>Recent Events</h2>
            <table>
                <thead><tr><th>Changes</th><th>Type</th><th>Confidence</th><th>Severity</th><th>Resources</th><th>Time</th></tr></thead>
                <tbody>{rows_html or '<tr><td colspan="6" style="text-align:center;color:#64748b">No events yet</td></tr>'}</tbody>
            </table>

            <h2>Drift Type Breakdown</h2>
            <table>
                <thead><tr><th>Type</th><th>Count</th><th>Avg Confidence</th></tr></thead>
                <tbody>{by_type_html or '<tr><td colspan="3" style="text-align:center;color:#64748b">No data</td></tr>'}</tbody>
            </table>
        </div>

        <div>
            <h2>Alerts</h2>
            <table>
                <thead><tr><th></th><th>Message</th><th>Time</th></tr></thead>
                <tbody>{alerts_html or '<tr><td colspan="3" style="text-align:center;color:#64748b">No alerts</td></tr>'}</tbody>
            </table>
        </div>
    </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
