import json
from pathlib import Path
from app.agents.policy_plugin import evaluate_advisor_response
from app.tools.sustainability_tools import (
    request_infrastructure_remediation_approval,
    scan_idle_compute_instances,
)


def test_golden_dataset_regressions():
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(cases) >= 2

    for case in cases:
        out = scan_idle_compute_instances(
            project_id=case["project_id"],
            region=case["region"],
            min_idle_days=case["min_idle_days"],
        )
        assert out["total_potential_monthly_savings_usd"] >= case["expected_min_savings_usd"]
        assert out["total_potential_monthly_kg_co2e_reduction"] >= case["expected_min_co2e_kg"]

        approval = request_infrastructure_remediation_approval(
            resource_name=out["findings"][0]["resource_name"],
            proposed_action=out["findings"][0]["recommended_action"],
            estimated_monthly_cost_usd=out["findings"][0]["estimated_monthly_cost_usd"],
            estimated_monthly_kg_co2e_reduction=out["findings"][0]["estimated_monthly_kg_co2e"],
        )
        summary = (
            f"Projected savings: ${out['total_potential_monthly_savings_usd']} USD and "
            f"{out['total_potential_monthly_kg_co2e_reduction']} kg CO2e. Status: {approval['status']}."
        )
        verdict = evaluate_advisor_response(
            response_text=summary,
            proposes_mutation=True,
            has_hitl_approval_request=True,
        )
        assert verdict.passed is True
