from typing import Literal
from pydantic import BaseModel, Field


class ScanComputeInput(BaseModel):
    project_id: str = Field(..., description="GCP project ID to inspect for idle or overprovisioned resources.")
    region: str = Field(default="us-central1", description="GCP region to filter compute inventory.")
    min_idle_days: int = Field(default=7, ge=1, le=90, description="Minimum days of low utilization to flag.")


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
        project_id: Target GCP project ID (non-empty string).
        region: Target GCP region such as us-central1 or us-east1.
        min_idle_days: Number of consecutive low-usage days (1-90) required to flag a resource.

    Returns:
        A dictionary matching ScanComputeOutput with findings and cost/carbon savings estimates.
    """
    if not project_id or not project_id.strip():
        return {
            "error": "INVALID_PROJECT_ID",
            "message": "project_id cannot be empty.",
            "recovery_hint": "Provide a valid GCP project ID such as 'ctsal200' and retry scan_idle_compute_instances.",
        }
    if min_idle_days < 1 or min_idle_days > 90:
        return {
            "error": "INVALID_IDLE_WINDOW",
            "message": f"min_idle_days={min_idle_days} is outside the supported range of 1 to 90.",
            "recovery_hint": "Set min_idle_days between 1 and 90 (for example, 7 or 14) and call the tool again.",
        }

    # Sample telemetry dataset for deterministic local/lab verification
    sample_findings = [
        ResourceFinding(
            resource_name="dev-ml-gpu-worker-01",
            resource_type="compute_instance",
            region=region,
            avg_cpu_percent=3.2,
            estimated_monthly_cost_usd=285.00,
            estimated_monthly_kg_co2e=42.4,
            recommended_action="Downsize machine type or schedule off-hours shutdown",
        ),
        ResourceFinding(
            resource_name="unattached-staging-pd-200gb",
            resource_type="persistent_disk",
            region=region,
            avg_cpu_percent=0.0,
            estimated_monthly_cost_usd=34.00,
            estimated_monthly_kg_co2e=5.1,
            recommended_action="Snapshot and delete unattached persistent disk",
        ),
    ]

    output = ScanComputeOutput(
        project_id=project_id.strip(),
        region=region.strip() or "us-central1",
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
    """Pauses execution for human-in-the-loop approval before mutating or deleting cloud resources.

    Args:
        resource_name: Exact identifier of the cloud resource to modify or stop.
        proposed_action: Specific remediation action (e.g., stop instance, downsize, delete disk).
        estimated_monthly_cost_usd: Estimated monthly dollar savings if approved.
        estimated_monthly_kg_co2e_reduction: Estimated monthly carbon emissions reduction in kg CO2e.

    Returns:
        A structured approval payload requiring explicit human confirmation before any state change.
    """
    if not resource_name.strip() or not proposed_action.strip():
        return {
            "error": "MISSING_REMEDIATION_DETAILS",
            "message": "Both resource_name and proposed_action are required.",
            "recovery_hint": "Pass a non-empty resource_name and a concrete proposed_action before requesting approval.",
        }

    payload = RemediationApprovalRequest(
        approval_id=f"APR-{abs(hash((resource_name, proposed_action))) % 100000:05d}",
        resource_name=resource_name.strip(),
        proposed_action=proposed_action.strip(),
        estimated_monthly_cost_usd=max(0.0, round(estimated_monthly_cost_usd, 2)),
        estimated_monthly_kg_co2e_reduction=max(0.0, round(estimated_monthly_kg_co2e_reduction, 2)),
        status="PENDING_HUMAN_APPROVAL",
        required_confirmation="Human operator must explicitly approve before applying any infrastructure change.",
    )
    return payload.model_dump()
