# Terraform Drift Detector

ML-powered infrastructure drift detection using Random Forest classification.

**Architecture**: Terraform (FloCI) → Synthetic Data Generator → Feature Extraction → Random Forest Classifier → FastAPI → SQLite → Prometheus → Grafana → MLflow

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User / CI Pipeline                          │
└──────────┬──────────────────────────────────────────────────────────┘
           │ terraform plan JSON
           ▼
┌──────────────────────┐    ┌──────────────────┐    ┌───────────────┐
│    FastAPI (8001)     │───▶│ Feature Extractor │───▶│ RF Classifier │
│  ┌──────────────────┐ │    │  (15 features)   │    │  (99% acc)    │
│  │  /detect  POST   │ │    └──────────────────┘    └───────┬───────┘
│  │  /history GET    │ │                                    │
│  │  /alerts  GET    │ │                                    ▼
│  │  /metrics GET    │ │                           ┌───────────────┐
│  │  /docs    GET    │ │                           │  Drift Type   │
│  │  /        UI     │ │                           │ + Confidence  │
│  └──────────────────┘ │                           └───────┬───────┘
└──────────┬────────────┘                                   │
           │                                                ▼
           │                                      ┌──────────────────┐
           ▼                                      │     SQLite DB    │
┌──────────────────┐                              │  drift_events    │
│    Prometheus     │◀───── scrape /metrics       │  drift_alerts    │
│    (9090)         │                              │  training_data   │
└────────┬─────────┘                              └──────────────────┘
         │ query
         ▼
┌──────────────────┐    ┌──────────────────┐
│     Grafana       │    │     MLflow       │
│    (3000)         │    │    (5050)        │
│  Drift Dashboard  │    │  Model Registry  │
└──────────────────┘    └──────────────────┘
```

## Quick Start

```bash
# 1. Virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Generate training data (100 samples, 20 per drift type)
python scripts/generate_training_data.py --samples 20

# 3. Train Random Forest classifier
python src/train.py --mlflow

# 4. Start FastAPI app
python src/app.py

# 5. Start MLflow UI (separate terminal)
mlflow ui --host 0.0.0.0 --port 5050 --backend-store-uri sqlite:///mlruns/mlflow.db

# 6. (Optional) Start monitoring stack
docker compose up -d prometheus grafana
```

## Services

| Service  | Port | URL                     |
|----------|------|-------------------------|
| FastAPI  | 8001 | http://localhost:8001   |
| MLflow   | 5050 | http://localhost:5050   |
| FloCI    | 4566 | http://localhost:4566   |
| Grafana  | 3000 | http://localhost:3000   |
| Prometheus| 9090 | http://localhost:9090  |

## API Endpoints

| Method | Path          | Description                      |
|--------|---------------|----------------------------------|
| POST   | /detect       | Submit terraform plan JSON, get drift classification |
| GET    | /history      | Recent drift events              |
| GET    | /alerts       | Alerts with repeat incident detection |
| GET    | /api/summary  | Summary statistics                |
| GET    | /metrics      | Prometheus metrics                |
| GET    | /docs         | Swagger/OpenAPI docs              |
| GET    | /             | HTML dashboard                    |

### Detect Drift Example

```bash
curl -X POST http://localhost:8001/detect \
  -H "Content-Type: application/json" \
  -d '{
    "resource_changes": [
      {
        "type": "aws_s3_bucket_public_access_block",
        "name": "data",
        "change": { "actions": ["update"] }
      },
      {
        "type": "aws_s3_bucket",
        "name": "data",
        "change": { "actions": ["no-op"] }
      }
    ]
  }'
```

Response:
```json
{
  "event_id": 1,
  "drift_type": "security",
  "confidence": 0.993,
  "severity": "critical",
  "changes": 1,
  "features": { ... }
}
```

## ML Pipeline

### 5 Drift Types Classified

| Type       | Description                    | Severity  | Example Changes                  |
|------------|--------------------------------|-----------|----------------------------------|
| no_drift   | No changes detected            | none      | All resources no-op              |
| security   | Public access settings changed | critical  | S3 public access block disabled  |
| config     | Encryption/versioning changed  | high      | SSE disabled, versioning off     |
| deletion   | IAM resources removed          | high      | Role policy attachment detached  |
| tag        | Tag metadata changed           | low       | Bucket tags modified             |

### 15 Features Extracted

| # | Feature                   | Description                          |
|---|---------------------------|--------------------------------------|
| 1 | total_changes             | Resources with non-no-op actions     |
| 2 | creates                   | Resources being created              |
| 3 | updates                   | Resources being modified             |
| 4 | deletes                   | Resources being deleted              |
| 5 | s3_changes                | Count of S3 resources changing       |
| 6 | iam_changes               | Count of IAM resources changing      |
| 7 | has_public_access_change  | Public access block modified         |
| 8 | has_encryption_change     | Encryption settings modified         |
| 9 | has_versioning_change     | Versioning settings modified         |
| 10 | has_tag_change            | Tag changes detected                 |
| 11 | has_policy_change         | Bucket/IAM policy changes            |
| 12 | has_iam_change            | Any IAM resource changes             |
| 13 | has_sg_change             | Security group changes               |
| 14 | severity_score            | Heuristic severity (0-10)            |
| 15 | unique_resource_types     | Distinct resource types affected     |

### Model Performance

- **Algorithm**: Random Forest (100 estimators, max_depth=10)
- **Cross-validation**: 99.0% ± 2.0% (5-fold stratified)
- **Top features**: total_changes, deletes, s3_changes, unique_resource_types

## FloCI Experience

### What Worked ✅

| Service                | Notes                                    |
|------------------------|------------------------------------------|
| S3 buckets             | Full CRUD, lifecycle, policies           |
| S3 public access block | Put/get public access block config       |
| IAM roles              | Create, read, update, delete             |
| IAM policies           | Create, read, update, delete             |
| IAM role-policy attachments | Attach/detach policies to roles     |
| S3 bucket policies     | Put/get bucket policies                  |

### What Didn't Work ❌

| Feature                | Symptom                                  | Workaround                              |
|------------------------|------------------------------------------|-----------------------------------------|
| S3 bucket versioning   | FloCI accepts but ignores — versioning status stays "Suspended" or "
Enabled" never reflects changes | Synthetic data generator bypasses FloCI |
| S3 bucket encryption   | FloCI accepts but ignores — SSE config not persisted | Same as above |
| Bucket tagging         | Tags accepted but not returned on drift check | Same as above |
| EC2 instances          | Not implemented in FloCI                 | Removed from Terraform config           |
| RDS subnet groups      | Unsupported API                          | Removed from Terraform config           |

**Key Learning**: Local AWS emulators (FloCI/LocalStack) implement ~60-70% of AWS APIs. For ML training data, synthetic generation is more reliable than depending on emulator behavior.

## Repeat Incident Detection

The system automatically flags repeat drift on the same resource:

```sql
SELECT resource, drift_type, COUNT(*) as times
FROM drift_events
GROUP BY resource, drift_type
HAVING COUNT(*) > 1;
```

When a repeat incident is detected, an alert is created with `is_repeat=True` and `repeat_count = N-1`. This enables teams to identify chronic drift issues vs one-time changes.

## Interview Talking Points

### Why Random Forest instead of LightGBM/XGBoost?
- Small dataset (~100 samples): RF is more robust against overfitting
- Interpretability: feature importance, decision paths
- LightGBM needs 10K+ rows to show advantage over RF
- RF handles non-linear boundaries well with low variance

### Why SQLite instead of PostgreSQL?
- Zero setup, single file, sufficient for prototype
- SQLite handles concurrent reads well (WAL mode)
- Easy to back up and migrate later
- Shows pragmatic tool selection for the problem scale

### Why synthetic data instead of real drift data?
- Real drift data is rare — terraform either applies cleanly or fails
- Controlled labels — each sample has known ground truth
- Reproducible — same seed produces same dataset
- This is standard practice in ML: generate training data when real labels are scarce

### Architecture decisions
- **FastAPI**: async by default, auto OpenAPI docs, Python-native
- **Feature extraction decoupled from model**: swap classifier without changing pipeline
- **Prometheus + Grafana**: industry-standard monitoring, shows SRE/DevOps skills
- **MLflow**: model versioning, experiment tracking, production deployment path
- **FloCI**: free, no auth tokens, MIT license, same port 4566 as LocalStack

## Monitoring

Access Grafana at http://localhost:3000 (admin/admin), then open the **Terraform Drift Detector** dashboard showing:
- Drift detection rate (counter)
- Confidence distribution (histogram)
- Drift type breakdown (bar chart)
- Drift rate over time (time series)
- Repeat incident count

Prometheus metrics are auto-discovered via the `/metrics` endpoint.

## Testing

```bash
# Test drift detection
PYTHONPATH=src python3 -c "
from synthetic_data import generate_plan
from features import extract_features, features_to_list

plan = generate_plan('security', seed=42)
features = extract_features(plan)
print(features_to_list(features))
"
```
