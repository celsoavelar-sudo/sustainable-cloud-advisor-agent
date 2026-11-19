from typing import Literal
from pydantic import BaseModel, Field, ValidationError
from app.observability.telemetry import trace_span


class ScanComputeInput(BaseModel):
    project_id: str = Field(..., min_length=1, description="GCP project ID to inspect.")
    region: str = Field(default="us-central1", min_length=1, description="GCP region.")
    min_idle_days: int = Field(default=7, ge=1, le=90, description="Idle window in days.")


class RemediationApprovalInput(BaseModel):
    resource_name: str = Field(..., min_length=1, description="Target resource name.")
    proposed_action: str = Field(..., min_length=1, description="Proposed remediation action.")
    estimated_monthly_cost_usd: float = Field(..., ge=0.0, description="Monthly savings USD.")
    estimated_monthly_kg_co2e_reduction: float = Field(..., ge=0.0, description="Monthly kg CO2e.")


class ResourceFinding(BaseModel):
    resource_name: str
    resource_type: Literal["compute_instance", "persistent_disk", "cloud_run_service"]
    region: str
    avg_cpu_percent: float
    estimated_monthly_cost_usd: float
    estimated_monthly_kg_co2e: float
    recommended_action: str


class ScanComputeOutput(BaseModel):
    project_id: str
    region: str
    findings: list[ResourceFinding]
    total_potential_monthly_savings_usd: float
    total_potential_monthly_kg_co2e_reduction: float


class RemediationApprovalRequest(BaseModel):
    approval_id: str
    resource_name: str
    proposed_action: str
    estimated_monthly_cost_usd: float
    estimated_monthly_kg_co2e_reduction: float
    status: Literal["PENDING_HUMAN_APPROVAL"]
    required_confirmation: str


def scan_idle_compute_instances(
    project_id: str,
    region: str = "us-central1",
    min_idle_days: int = 7,
) -> dict:
    """Scans cloud compute and storage workloads for idle or overprovisioned capacity.

    Args:
        project_id: Target GCP project ID to inspect (non-empty string, e.g., 'ctsal200').
        region: Target GCP region to filter inventory (e.g., 'us-central1' or 'us-east1').
        min_idle_days: Minimum consecutive low-utilization days between 1 and 90.

    Returns:
        Dictionary containing validated findings and estimated monthly cost/carbon savings.
    """
    with trace_span("scan_idle_compute_instances", {"project_id": project_id, "region": region}):
        try:
            validated = ScanComputeInput(
                project_id=project_id.strip() if isinstance(project_id, str) else "",
                region=region.strip() if isinstance(region, str) else "us-central1",
                min_idle_days=min_idle_days,
            )
        except ValidationError as exc:
            return {
                "error": "INVALID_PROJECT_ID",
                "message": str(exc.errors()[0]["msg"]) if exc.errors() else "Invalid scan input.",
                "recovery_hint": "Pass a non-empty project_id (e.g. 'ctsal200') and min_idle_days between 1 and 90.",
            }

        sample_findings = [
            ResourceFinding(
                resource_name="dev-ml-gpu-worker-01",
                resource_type="compute_instance",
                region=validated.region,
                avg_cpu_percent=3.2,
                estimated_monthly_cost_usd=285.00,
                estimated_monthly_kg_co2e=42.4,
                recommended_action="Downsize machine type or schedule off-hours shutdown",
            ),
            ResourceFinding(
                resource_name="unattached-staging-pd-200gb",
                resource_type="persistent_disk",
                region=validated.region,
                avg_cpu_percent=0.0,
                estimated_monthly_cost_usd=34.00,
                estimated_monthly_kg_co2e=5.1,
                recommended_action="Snapshot and delete unattached persistent disk",
            ),
        ]
        output = ScanComputeOutput(
            project_id=validated.project_id,
            region=validated.region,
            findings=sample_findings,
            total_potential_monthly_savings_usd=round(
                sum(f.estimated_monthly_cost_usd for f in sample_findings), 2
            ),
            total_potential_monthly_kg_co2e_reduction=round(
                sum(f.estimated_monthly_kg_co2e for f in sample_findings), 2
            ),
        )
        return output.model_dump()


def request_infrastructure_remediation_approval(
    resource_name: str,
    proposed_action: str,
    estimated_monthly_cost_usd: float,
    estimated_monthly_kg_co2e_reduction: float,
) -> dict:
    """Pauses execution for human-in-the-loop approval before mutating cloud resources.

    Args:
        resource_name: Exact identifier of the target cloud resource to modify or stop.
        proposed_action: Concrete remediation action such as stopping or downsizing the resource.
        estimated_monthly_cost_usd: Estimated monthly cost savings in USD (>= 0.0).
        estimated_monthly_kg_co2e_reduction: Estimated monthly carbon savings in kg CO2e (>= 0.0).

    Returns:
        Structured approval payload requiring explicit human confirmation before mutation.
    """
    with trace_span("request_infrastructure_remediation_approval", {"resource_name": resource_name}):
        try:
            validated = RemediationApprovalInput(
                resource_name=resource_name.strip() if isinstance(resource_name, str) else "",
                proposed_action=proposed_action.strip() if isinstance(proposed_action, str) else "",
                estimated_monthly_cost_usd=estimated_monthly_cost_usd,
                estimated_monthly_kg_co2e_reduction=estimated_monthly_kg_co2e_reduction,
            )
        except ValidationError:
            return {
                "error": "MISSING_REMEDIATION_DETAILS",
                "message": "Both resource_name and proposed_action are required.",
                "recovery_hint": "Provide non-empty resource_name and proposed_action values.",
            }

        payload = RemediationApprovalRequest(
            approval_id=f"APR-{abs(hash((validated.resource_name, validated.proposed_action))) % 100000:05d}",
            resource_name=validated.resource_name,
            proposed_action=validated.proposed_action,
            estimated_monthly_cost_usd=round(validated.estimated_monthly_cost_usd, 2),
            estimated_monthly_kg_co2e_reduction=round(validated.estimated_monthly_kg_co2e_reduction, 2),
            status="PENDING_HUMAN_APPROVAL",
            required_confirmation="Human operator must explicitly approve before applying any change.",
        )
        return payload.model_dump()
