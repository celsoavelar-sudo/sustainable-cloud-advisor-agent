import os
from typing import Optional
from app.observability.telemetry import log_structured_event, redact_pii

try:
    from google.cloud import secretmanager  # type: ignore
except Exception:  # pragma: no cover
    secretmanager = None


def load_secret_value(
    secret_id: str,
    project_id: Optional[str] = None,
    version: str = "latest",
    env_fallback: Optional[str] = None,
) -> Optional[str]:
    """Fetches a secret from Google Cloud Secret Manager, falling back to an env var if needed."""
    resolved_project = project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or "ctsal200"
    if env_fallback and os.getenv(env_fallback):
        return os.getenv(env_fallback)

    if secretmanager is not None and resolved_project:
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{resolved_project}/secrets/{secret_id}/versions/{version}"
            response = client.access_secret_version(request={"name": name})
            value = response.payload.data.decode("UTF-8")
            log_structured_event(
                event_type="secret_manager_access",
                intent=f"Load secret {secret_id} from Secret Manager for {resolved_project}",
                outcome="Secret version retrieved cleanly",
                metadata={"secret_id": secret_id, "project_id": resolved_project},
            )
            return value
        except Exception as exc:
            log_structured_event(
                event_type="secret_manager_access",
                intent=f"Load secret {secret_id} from Secret Manager for {resolved_project}",
                outcome=f"Fallback used due to client/lookup condition: {redact_pii(str(exc))}",
                status="fallback",
                metadata={"secret_id": secret_id, "project_id": resolved_project},
            )
    return None
