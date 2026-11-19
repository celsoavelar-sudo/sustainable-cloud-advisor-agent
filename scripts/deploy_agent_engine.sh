#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-ctsal200}"
REGION="${2:-us-central1}"
AGENT_NAME="sustainable-cloud-advisor-agent"

if command -v terraform >/dev/null 2>&1; then
  terraform -chdir=infra init -input=false
  terraform -chdir=infra validate
fi

if command -v agents-cli >/dev/null 2>&1; then
  agents-cli deploy \
    --agent-name "${AGENT_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --no-confirm-project
fi
