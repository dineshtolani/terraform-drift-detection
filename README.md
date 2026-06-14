# Terraform Drift Detector

ML-powered infrastructure drift detection using Random Forest classification.

```
Terraform (FloCI/AWS) → Synthetic Data Generator → Feature Extraction
→ Random Forest Classifier (99% CV) → FastAPI → SQLite → Prometheus → Grafana → MLflow
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline / User                        │
└──────────┬──────────────────────────────────────────────────────────┘
           │ terraform plan JSON
           ▼
┌──────────────────────┐    ┌──────────────────┐    ┌───────────────┐
│    FastAPI (8001)     │───▶│ Feature Extractor │───▶│ RF Classifier │
│  /detect  POST       │    │  (15 features)   │    │  (99% acc)    │
│  /history GET        │    └──────────────────┘    └───────┬───────┘
│  /alerts  GET        │                                    │
│  /metrics GET        │                                    ▼
│  /docs    GET        │                           ┌───────────────┐
│  /        UI         │                           │  Drift Type   │
└──────────┬───────────┘                           │ + Confidence  │
           │                                       └───────┬───────┘
           ▼                                               │
┌──────────────────┐                              ┌───────▼───────┐
│    Prometheus     │◀───── scrape /metrics       │  SQLite DB    │
│    (9090)         │                              │  drift_events │
└────────┬─────────┘                              │  drift_alerts │
         │ query                                  │  training_data│
         ▼                                        └───────────────┘
┌──────────────────┐    ┌──────────────────┐
│     Grafana       │    │     MLflow       │
│    (3000)         │    │    (5050)        │
│  Drift Dashboard  │    │  Model Registry  │
└──────────────────┘    └──────────────────┘
```

---


