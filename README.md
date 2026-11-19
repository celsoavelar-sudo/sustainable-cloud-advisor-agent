# Sustainable Cloud Advisor Agent

## Problem Statement
Organizations waste cloud resources due to idle infrastructure and overprovisioned workloads.

## Solution Statement
A Google ADK multi-agent system that scans cloud compute and storage utilization, estimates cost (`USD`) and carbon (`kg CO2e`) savings, and routes mutations through human-in-the-loop approval.

## Infrastructure as Code & Agent CLI Deployment
- **Terraform (`infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf`)**: Enables GCP APIs, creates `sustainable-cloud-advisor-sa`, and provisions `sustainable-cloud-advisor-config` in Secret Manager with IAM access.
- **Agent CLI (`agents-cli`)**:
```bash
terraform -chdir=infra init -input=false
terraform -chdir=infra validate
agents-cli deploy --agent-name sustainable-cloud-advisor-agent --project ctsal200 --region us-central1 --no-confirm-project
```

## Run Tests
```bash
PYTHONPATH=. uv run pytest -v
```
