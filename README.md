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

## Quick Start

```bash
# 1. Virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Generate training data (100 samples, 20 per drift type)
python scripts/generate_training_data.py --samples 20

# 3. Train Random Forest classifier
python src/train.py --mlflow

# 4. Start FastAPI app
python src/app.py

# 5. Start MLflow UI (separate terminal)
mlflow ui --host 0.0.0.0 --port 5050 \
  --backend-store-uri sqlite:///mlruns/mlflow.db

# 6. (Optional) Start monitoring stack
docker compose up -d prometheus grafana
```

## Services

| Port | Service   | URL                          | Credentials       |
|------|-----------|------------------------------|-------------------|
| 8001 | FastAPI   | http://localhost:8001        | —                 |
| 5050 | MLflow    | http://localhost:5050        | —                 |
| 4566 | FloCI     | http://localhost:4566        | test/test         |
| 9090 | Prometheus| http://localhost:9090        | —                 |
| 3000 | Grafana   | http://localhost:3000        | admin/admin       |

---

## API

| Method | Path          | Description                            |
|--------|---------------|----------------------------------------|
| POST   | `/detect`     | Submit terraform plan JSON → drift classification |
| GET    | `/history`    | Recent drift events                    |
| GET    | `/alerts`     | Alerts with repeat incident detection  |
| GET    | `/api/summary`| Summary statistics                     |
| GET    | `/metrics`    | Prometheus metrics                     |
| GET    | `/docs`       | Swagger/OpenAPI docs                   |
| GET    | `/`           | HTML dashboard                         |

### Detect Drift

```bash
curl -X POST http://localhost:8001/detect -H "Content-Type: application/json" -d '{
  "resource_changes": [
    {
      "type": "aws_s3_bucket_public_access_block",
      "name": "data",
      "change": { "actions": ["update"] }
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

---

## ML Pipeline

### 5 Drift Types

| Type       | Description                    | Severity  | Example Change                      |
|------------|--------------------------------|-----------|-------------------------------------|
| `no_drift` | No changes detected            | none      | All resources no-op                 |
| `security` | Public access settings changed | critical  | S3 public access block disabled     |
| `config`   | Encryption/versioning changed  | high      | SSE disabled, versioning suspended  |
| `deletion` | IAM resources removed          | high      | Role policy attachment detached     |
| `tag`      | Tag metadata changed           | low       | Bucket tags modified                |

### 15 Features

| # | Feature                   | Description                          |
|---|---------------------------|--------------------------------------|
| 1 | `total_changes`           | Resources with non-no-op actions     |
| 2 | `creates`                 | Resources being created              |
| 3 | `updates`                 | Resources being modified             |
| 4 | `deletes`                 | Resources being deleted              |
| 5 | `s3_changes`              | Count of S3 resources changing       |
| 6 | `iam_changes`             | Count of IAM resources changing      |
| 7 | `has_public_access_change`| Public access block modified?        |
| 8 | `has_encryption_change`   | Encryption settings modified?        |
| 9 | `has_versioning_change`   | Versioning settings modified?        |
| 10| `has_tag_change`          | Tag changes detected?                |
| 11| `has_policy_change`       | Bucket/IAM policy changes?           |
| 12| `has_iam_change`          | Any IAM resource changes?            |
| 13| `has_sg_change`           | Security group changes?              |
| 14| `severity_score`          | Heuristic severity (0-10)            |
| 15| `unique_resource_types`   | Distinct resource types affected     |

### Model Performance

- **Algorithm**: Random Forest (100 estimators, max_depth=10, class_weight=balanced)
- **Cross-validation**: 99.0% ± 2.0% (5-fold stratified)
- **Top features**: `total_changes` (13.5%), `deletes` (12.6%), `s3_changes` (12.2%)

---

## Real AWS vs FloCI

This project was developed entirely on **FloCI** (a free local AWS emulator). Here's what would change on real AWS.

### Provider Config Comparison

| Aspect | FloCI (current) | Real AWS |
|--------|-----------------|----------|
| **Backend** | Local files | S3 bucket + DynamoDB lock table |
| **Auth** | `test/test`, `skip_creds=true` | IAM user/role with proper permissions |
| **API coverage** | ~60-70% of AWS APIs | 100% — every API works |
| **Cost** | Free | Each `terraform apply` costs real money |
| **Speed** | `terraform apply` in 5-10s | 30-60s per apply |
| **Data generation** | 100 samples in ~2 min | Hours + real API costs |
| **Label quality** | Perfect (synthetic, known ground truth) | Noisy (needs human labeling) |
| **Reset** | `docker compose down` | Must track and destroy every resource |

### provider.tf on Real AWS

```hcl
terraform {
  backend "s3" {
    bucket         = "drift-detector-tfstate"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "drift-detector-tf-locks"
  }
}
provider "aws" {
  region = "us-east-1"
  # Credentials from IAM role or env vars
}
```

### What Works on FloCI ✅

| Service | Notes |
|---------|-------|
| S3 buckets | Full CRUD, lifecycle, policies |
| S3 public access block | Fully functional |
| S3 bucket policies | Put/get bucket policies |
| IAM roles | Full CRUD |
| IAM policies | Full CRUD |
| IAM role-policy attachments | Attach/detach works |

### What Doesn't Work on FloCI ❌

| Feature | Symptom | Workaround |
|---------|---------|------------|
| S3 versioning | Accepts but ignores — status never reflects changes | Synthetic data generator |
| S3 encryption | Accepts but ignores — SSE config not persisted | Same |
| Bucket tagging | Tags not returned on subsequent reads | Same |
| EC2 instances | Not implemented | Removed from config |
| RDS subnet groups | Not implemented | Removed from config |

### The Interview Answer

> **"For development, FloCI was the right choice — fast iteration, zero cost, perfect labels for ML training. In production, I'd deploy to real AWS with SageMaker or ECS. The drift detection logic is identical; only the provider config changes. The synthetic data generator is actually superior to real drift collection because it guarantees correct labels — real drift data is noisy and would need expensive human labeling."**

---

## Repeat Incident Detection

Automatically flags repeat drift on the same resource:

```sql
SELECT resource, drift_type, COUNT(*) as times
FROM drift_events
GROUP BY resource, drift_type
HAVING COUNT(*) > 1;
```

When a repeat is detected, an alert is created with `is_repeat=True` and `repeat_count = N-1`. This distinguishes chronic drift issues from one-time changes.

---

## Monitoring

Grafana dashboard at http://localhost:3000 (admin/admin) auto-provisions with:

| Panel | Type | PromQL |
|-------|------|--------|
| Drift Detection Rate | Stat | `sum(drift_detections_total)` |
| Repeat Incidents | Stat | `sum(drift_detections_total{drift_type=~"security\|config\|deletion"})` |
| Avg Confidence | Stat | `drift_confidence_sum / drift_confidence_count` |
| Active Drift Types | Stat | `count(drift_detections_total > 0)` |
| Drift by Type | Bar chart | `sum by(drift_type) (drift_detections_total)` |
| Confidence Distribution | Histogram | `drift_confidence_bucket` |
| Drift Rate Over Time | Time series | `rate(drift_detections_total[5m])` |

---

## Testing

```bash
# Run all 21 tests
pytest tests/ -v

# Quick feature extraction test
PYTHONPATH=src python3 -c "
from synthetic_data import generate_plan
from features import extract_features, features_to_list
plan = generate_plan('security', seed=42)
features = extract_features(plan)
print(features_to_list(features))
"
```

---

## Interview Talking Points

### Why Random Forest over LightGBM/XGBoost?
- Small dataset (~100 samples): RF resists overfitting better
- Interpretability: built-in feature importance, decision paths
- LightGBM needs 10K+ rows to outperform RF
- RF handles non-linear boundaries well with low variance

### Why SQLite over PostgreSQL?
- Zero setup, single file, perfect for a prototype
- Sufficient for single-user or small-team use (WAL mode)
- Easy to migrate to Postgres later (same SQL)
- Demonstrates pragmatic tool selection

### Why Synthetic Data?
- Real drift data is rare — terraform either applies cleanly or fails
- Perfect labels: every sample has known ground truth
- Reproducible: same seed → same dataset
- Standard ML practice when real labels are scarce

### Architecture Decisions
- **FastAPI**: async, auto OpenAPI docs, Python-native
- **Decoupled features → classifier**: swap models without changing pipeline
- **Prometheus + Grafana**: industry standard, shows SRE/DevOps skills
- **MLflow**: model versioning, experiment tracking, production deployment path
- **Docker**: reproducible environment, resource limits, easy deploy
