# Sustainable Cloud Advisor Agent

## Problem Statement
Organizations waste cloud resources due to idle infrastructure and overprovisioned workloads. Identifying inefficiencies and opportunities for optimization requires time-consuming manual analysis.

## Solution Statement
A Sustainable Cloud Advisor AI Agent built with Google ADK that analyzes Google Cloud resource utilization, identifies inefficiencies, quantifies cost and carbon (`kg CO2e`) savings, and routes high-impact infrastructure changes through human-in-the-loop approval.

## Key Capabilities
- **Multi-Agent Orchestration**: Coordinator agent (`sustainable_cloud_advisor`) paired with a specialized `efficiency_analyst` sub-agent and a human-in-the-loop approval gate (`request_infrastructure_remediation_approval`).
- **Schema-Validated Tools**: Pydantic input/output models, clear docstrings, and recovery hints on invalid inputs.
- **Context, Memory & Observability**: Sliding-window history compaction, async memory consolidation, PII redaction, OpenTelemetry span wrappers, and structured JSON logs capturing intent vs. outcome.
- **Infrastructure & CI/CD**: Terraform configuration for APIs, runtime service account, and Secret Manager access (`infra/`), automated `pytest` workflow (`.github/workflows/ci.yml`), and `uv.lock` dependency locking.

## Run Tests
```bash
PYTHONPATH=. uv run pytest -v
cat <<'EOF' >> README.md
